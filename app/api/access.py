"""Защита интерфейса менеджера и ограничение частоты запросов к LLM.

HTTP Basic включается парой UI_BASIC_AUTH_USERNAME / UI_BASIC_AUTH_PASSWORD
и закрывает всё, кроме /health и /api/v1/amocrm/*: у эндпоинтов amoCRM своя
защита — одноразовый JWT виджета и секрет вебхука. Браузер сам показывает
окно входа и затем отправляет заголовок Authorization со всеми запросами
к тому же адресу, поэтому интерфейс менять не нужно.

RateLimiter ограничивает число генераций в минуту на ключ (IP или
пользователь amoCRM): каждая генерация — платный запрос к модели.
"""

import base64
import binascii
import hmac
import logging
import threading
import time
from collections import OrderedDict, deque
from collections.abc import Callable

from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send

from app.errors import AppError

logger = logging.getLogger(__name__)

# Пути без Basic-аутентификации: проверка живости и эндпоинты с собственной защитой.
PUBLIC_PATHS = frozenset({"/health"})
PUBLIC_PREFIXES = ("/api/v1/amocrm/",)


def is_public_path(path: str) -> bool:
    """Нужна ли пути Basic-аутентификация."""
    return path in PUBLIC_PATHS or path.startswith(PUBLIC_PREFIXES)


def credentials_match(header: str | None, username: str, password: str) -> bool:
    """Проверить заголовок «Authorization: Basic …» за постоянное время."""
    if not header or not header.lower().startswith("basic "):
        return False
    try:
        decoded = base64.b64decode(header[6:].strip(), validate=True).decode("utf-8")
    except (binascii.Error, UnicodeDecodeError):
        return False
    given_user, separator, given_password = decoded.partition(":")
    if not separator:
        return False
    # Сравниваем обе части всегда, чтобы время ответа не выдавало верный логин.
    user_ok = hmac.compare_digest(given_user.encode(), username.encode())
    password_ok = hmac.compare_digest(given_password.encode(), password.encode())
    return user_ok and password_ok


class BasicAuthMiddleware:
    """ASGI-middleware: 401 с WWW-Authenticate для закрытых путей без верного логина."""

    def __init__(self, app: ASGIApp, username: str, password: str) -> None:
        self.app = app
        self._username = username
        self._password = password

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or is_public_path(scope["path"]):
            await self.app(scope, receive, send)
            return
        header = None
        for name, value in scope.get("headers", []):
            if name == b"authorization":
                header = value.decode("latin-1")
                break
        if credentials_match(header, self._username, self._password):
            await self.app(scope, receive, send)
            return
        logger.warning("basic auth rejected")
        response = JSONResponse(
            status_code=401,
            content={
                "error": {
                    "code": "unauthorized",
                    "message": "Введите логин и пароль менеджера.",
                }
            },
            headers={"WWW-Authenticate": 'Basic realm="AI Sales Assistant", charset="UTF-8"'},
        )
        await response(scope, receive, send)


class RateLimitedError(AppError):
    status_code = 429
    code = "rate_limited"
    user_message = "Слишком много запросов. Подождите немного и попробуйте снова."


class RateLimiter:
    """Скользящее окно: не больше limit вызовов за window_seconds на один ключ.

    limit = 0 выключает ограничение. Хранится в памяти процесса, число ключей
    ограничено: самые давно не встречавшиеся вытесняются первыми.
    """

    def __init__(
        self,
        limit: int,
        window_seconds: float = 60.0,
        max_keys: int = 10_000,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.limit = limit
        self._window = window_seconds
        self._max_keys = max_keys
        self._clock = clock
        self._lock = threading.Lock()
        self._calls: OrderedDict[str, deque[float]] = OrderedDict()

    def check(self, key: str, scope: str) -> None:
        """Учесть вызов или бросить RateLimitedError с Retry-After.

        scope — тип ключа для лога («ip», «amocrm»); сам ключ не логируется.
        """
        if self.limit <= 0:
            return
        now = self._clock()
        with self._lock:
            calls = self._calls.setdefault(key, deque())
            self._calls.move_to_end(key)
            while calls and now - calls[0] >= self._window:
                calls.popleft()
            if len(calls) >= self.limit:
                retry_after = max(1, int(self._window - (now - calls[0])) + 1)
                logger.warning("rate limit exceeded scope=%s", scope)
                raise RateLimitedError(headers={"Retry-After": str(retry_after)})
            calls.append(now)
            while len(self._calls) > self._max_keys:
                self._calls.popitem(last=False)
