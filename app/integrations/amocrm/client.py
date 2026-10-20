"""Минимальный клиент amoCRM REST API v4.

Используются только документированные методы:
- GET /api/v4/leads/{id}?with=contacts — сделка и привязанные контакты;
- GET /api/v4/contacts/{id}             — контакт (берём только имя).

Авторизация — заголовок «Authorization: Bearer <token>». Для приватной
интеграции удобно использовать долгосрочный токен из настроек интеграции;
токен OAuth 2.0 передаётся так же.
"""

import logging

import httpx

from app.errors import AppError

logger = logging.getLogger(__name__)


class AmoCRMError(AppError):
    status_code = 502
    code = "amocrm_error"
    user_message = "Не удалось получить данные из amoCRM."


class AmoCRMAuthError(AmoCRMError):
    code = "amocrm_auth"
    user_message = "amoCRM отклонил токен доступа: проверьте AMOCRM_ACCESS_TOKEN."


class AmoCRMClient:
    def __init__(
        self,
        *,
        base_url: str,
        access_token: str,
        timeout_seconds: float = 10.0,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._http = httpx.AsyncClient(
            base_url=base_url.rstrip("/"),
            headers={"Authorization": f"Bearer {access_token}"},
            timeout=timeout_seconds,
            transport=transport,
        )

    async def aclose(self) -> None:
        await self._http.aclose()

    async def _get(self, path: str, params: dict | None = None) -> dict | None:
        try:
            response = await self._http.get(path, params=params)
        except httpx.HTTPError as exc:
            logger.warning("amocrm request failed: %s", type(exc).__name__)
            raise AmoCRMError() from None
        if response.status_code in (204, 404):
            return None
        if response.status_code in (401, 403):
            logger.error("amocrm auth error: HTTP %d", response.status_code)
            raise AmoCRMAuthError()
        if response.status_code >= 400:
            logger.warning("amocrm HTTP %d on %s", response.status_code, path.split("/")[3])
            raise AmoCRMError()
        try:
            return response.json()
        except ValueError:
            raise AmoCRMError() from None

    async def get_lead(self, lead_id: int) -> dict | None:
        return await self._get(f"/api/v4/leads/{lead_id}", params={"with": "contacts"})

    async def get_contact(self, contact_id: int) -> dict | None:
        return await self._get(f"/api/v4/contacts/{contact_id}")
