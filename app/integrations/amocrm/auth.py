"""Проверка одноразовых токенов виджета amoCRM.

Метод виджета `this.$authorizedAjax()` добавляет к запросу заголовок
X-Auth-Token — JWT, подписанный секретным ключом интеграции (HS256).
Полезная нагрузка (по документации amoCRM): iss — адрес аккаунта,
aud — адрес из redirect_uri интеграции, jti, iat, nbf, exp, account_id,
user_id, client_uuid — ID интеграции, subdomain.

Так бэкенд узнаёт, что запрос пришёл из интерфейса amoCRM от конкретного
пользователя конкретного аккаунта, не храня паролей и не выдавая своих токенов.
"""

from dataclasses import dataclass
from urllib.parse import urlparse

import jwt

from app.errors import AppError


class WidgetAuthError(AppError):
    status_code = 401
    code = "amocrm_widget_unauthorized"
    user_message = "Запрос не авторизован: откройте ассистента из интерфейса amoCRM."


@dataclass(frozen=True)
class WidgetUser:
    account_id: int
    user_id: int
    subdomain: str | None


def _host(url: str) -> str:
    parsed = urlparse(url if "://" in url else f"https://{url}")
    return (parsed.hostname or "").lower()


def verify_widget_token(
    token: str | None,
    *,
    secret: str,
    client_id: str = "",
    account_base_url: str = "",
    leeway_seconds: int = 30,
) -> WidgetUser:
    if not token:
        raise WidgetAuthError()
    try:
        payload = jwt.decode(
            token,
            secret,
            algorithms=["HS256"],
            options={"require": ["exp", "iat", "account_id", "user_id"], "verify_aud": False},
            leeway=leeway_seconds,
        )
    except jwt.PyJWTError:
        raise WidgetAuthError() from None

    if client_id and payload.get("client_uuid") != client_id:
        raise WidgetAuthError()
    if account_base_url and _host(str(payload.get("iss", ""))) != _host(account_base_url):
        raise WidgetAuthError()
    try:
        return WidgetUser(
            account_id=int(payload["account_id"]),
            user_id=int(payload["user_id"]),
            subdomain=payload.get("subdomain"),
        )
    except (TypeError, ValueError):
        raise WidgetAuthError() from None
