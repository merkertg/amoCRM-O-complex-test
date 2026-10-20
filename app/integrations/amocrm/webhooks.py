"""Разбор вебхуков amoCRM о сообщениях в чатах.

amoCRM отправляет вебхуки как application/x-www-form-urlencoded с вложенными
ключами, например `message[add][0][text]`. Документированные события:
- `message[add]`          — входящее сообщение клиента;
- `outgoing_message[add]` — исходящее сообщение пользователя amoCRM или Salesbot.

Поля сообщения: id, chat_id, talk_id, contact_id, text, created_at,
element_id / element_type (сущность CRM, к которой привязан чат), attachment.
"""

import time
from collections.abc import Iterable
from typing import Any

from app.integrations.amocrm.message_store import StoredMessage
from app.schemas import Role

_ENTITY_ROLES = {"message": Role.CLIENT, "outgoing_message": Role.MANAGER}
# Сделка обозначается кодом «2» (числовые типы amoCRM) или строкой lead/leads.
_LEAD_TYPES = {"2", "lead", "leads"}


def parse_nested_form(items: Iterable[tuple[str, str]]) -> dict[str, Any]:
    """`a[b][0][c]=v` -> {"a": {"b": {"0": {"c": "v"}}}}."""
    result: dict[str, Any] = {}
    for key, value in items:
        parts = key.replace("]", "").split("[")
        node = result
        for part in parts[:-1]:
            child = node.get(part)
            if not isinstance(child, dict):
                child = node[part] = {}
            node = child
        node[parts[-1]] = value
    return result


def _as_list(value: Any) -> list[dict]:
    if isinstance(value, list):
        return [v for v in value if isinstance(v, dict)]
    if isinstance(value, dict):
        return [v for _, v in sorted(value.items(), key=lambda kv: str(kv[0]).zfill(6)) if isinstance(v, dict)]
    return []


def _int(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def extract_chat_messages(payload: dict[str, Any]) -> list[StoredMessage]:
    messages: list[StoredMessage] = []
    for entity, role in _ENTITY_ROLES.items():
        section = payload.get(entity)
        if not isinstance(section, dict):
            continue
        for item in _as_list(section.get("add")):
            text = str(item.get("text") or "").strip()
            if not text and item.get("attachment"):
                text = "[вложение]"
            message_id = str(item.get("id") or "").strip()
            if not text or not message_id:
                continue
            element_type = str(item.get("element_type") or item.get("entity_type") or "").lower()
            element_id = _int(item.get("element_id") or item.get("entity_id"))
            messages.append(
                StoredMessage(
                    message_id=message_id,
                    role=role,
                    text=text[:4000],
                    created_at=_int(item.get("created_at")) or int(time.time()),
                    lead_id=element_id if element_type in _LEAD_TYPES else None,
                    contact_id=_int(item.get("contact_id")),
                    talk_id=_int(item.get("talk_id")),
                )
            )
    return messages
