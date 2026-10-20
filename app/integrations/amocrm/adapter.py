"""Адаптер amoCRM: собирает DialogContext для бизнес-логики по ID сделки.

Источники данных:
- текущее сообщение: из поля виджета (если менеджер вставил текст) или
  последняя реплика клиента из кэша вебхуков;
- история диалога: из кэша вебхуков (входящие + исходящие сообщения);
- клиент: имя основного контакта сделки через REST API v4.
Телефоны, e-mail и прочие поля контакта не запрашиваются и не передаются в LLM.
"""

import logging
from typing import Literal

from pydantic import BaseModel

from app.core.dialog import parse_history_text
from app.errors import AppError
from app.integrations.amocrm.client import AmoCRMClient, AmoCRMError
from app.integrations.amocrm.message_store import MessageStore, StoredMessage
from app.schemas import DialogContext, DialogMessage, Role

logger = logging.getLogger(__name__)


class LeadNotFoundError(AppError):
    status_code = 404
    code = "amocrm_lead_not_found"
    user_message = "Сделка не найдена в amoCRM."


class NoClientMessageError(AppError):
    status_code = 422
    code = "amocrm_no_message"
    user_message = (
        "В кэше нет сообщений клиента по этой сделке. "
        "Вставьте текст сообщения клиента в поле ассистента."
    )


class AmoContextInfo(BaseModel):
    lead_id: int
    message_source: Literal["manual", "webhook"]
    history_messages: int
    crm_data_loaded: bool


class AmoCRMAdapter:
    def __init__(self, client: AmoCRMClient | None, store: MessageStore, history_limit: int = 20) -> None:
        self._client = client
        self._store = store
        self._history_limit = history_limit

    async def _load_crm(self, lead_id: int) -> tuple[str | None, list[int]]:
        """Возвращает (имя клиента, id контактов сделки)."""
        lead = await self._client.get_lead(lead_id)
        if lead is None:
            raise LeadNotFoundError()
        contacts = (lead.get("_embedded") or {}).get("contacts") or []
        contact_ids = [int(c["id"]) for c in contacts if isinstance(c, dict) and c.get("id")]
        main = next((c for c in contacts if c.get("is_main")), contacts[0] if contacts else None)
        name = None
        if main and main.get("id"):
            contact = await self._client.get_contact(int(main["id"])) or {}
            name = (contact.get("first_name") or "").strip() or (contact.get("name") or "").strip() or None
            if name:
                name = name.split()[0][:50]
        return name, contact_ids

    def _stored_messages(self, lead_id: int, contact_ids: list[int]) -> list[StoredMessage]:
        stored = self._store.for_lead(lead_id)
        for contact_id in contact_ids:
            if stored:
                break
            stored = self._store.for_contact(contact_id)
        return stored[-self._history_limit :]

    async def build_context(
        self,
        lead_id: int,
        message: str | None = None,
        history_text: str | None = None,
    ) -> tuple[DialogContext, AmoContextInfo, list[str]]:
        warnings: list[str] = []
        client_name: str | None = None
        contact_ids: list[int] = []
        crm_loaded = False
        if self._client is not None:
            try:
                client_name, contact_ids = await self._load_crm(lead_id)
                crm_loaded = True
            except LeadNotFoundError:
                raise
            except AmoCRMError:
                warnings.append(
                    "Не удалось загрузить данные сделки из amoCRM — подсказка построена только по переписке."
                )

        if history_text and history_text.strip():
            history = parse_history_text(history_text)
        else:
            history = [
                DialogMessage(role=m.role, text=m.text)
                for m in self._stored_messages(lead_id, contact_ids)
            ]

        if message and message.strip():
            source: Literal["manual", "webhook"] = "manual"
            message = message.strip()
            if history and history[-1].role == Role.CLIENT and history[-1].text.strip() == message:
                history = history[:-1]
        else:
            source = "webhook"
            last_client = next(
                (i for i in range(len(history) - 1, -1, -1) if history[i].role == Role.CLIENT), None
            )
            if last_client is None:
                raise NoClientMessageError()
            if last_client < len(history) - 1:
                warnings.append("На последнее сообщение клиента в чате уже есть ответ.")
            # Несколько сообщений клиента подряд считаем одним обращением.
            first = last_client
            while first > 0 and history[first - 1].role == Role.CLIENT:
                first -= 1
            message = "\n".join(m.text for m in history[first : last_client + 1])
            history = history[:first]

        context = DialogContext(
            message=message,
            history=history,
            client_name=client_name,
            source=f"amocrm:{source}",
        )
        info = AmoContextInfo(
            lead_id=lead_id,
            message_source=source,
            history_messages=len(history),
            crm_data_loaded=crm_loaded,
        )
        return context, info, warnings
