"""Клиент для любого OpenAI-совместимого Chat Completions API.

Используется только HTTPX — без SDK конкретного провайдера, поэтому подходит
OpenAI, OpenRouter, DeepSeek, Ollama, vLLM, LM Studio и другие совместимые API.

Обработка ошибок:
- таймаут и сетевые ошибки, HTTP 429 и 5xx — повтор с экспоненциальной задержкой;
- 401/403 — сразу ошибка авторизации (повтор бессмысленен);
- прочие 4xx — ошибка запроса (неверная модель, неподдерживаемый параметр);
- ответ без choices[0].message.content — некорректный ответ провайдера.
В логи пишутся только статус-коды и типы ошибок: ни промпт, ни ключ туда не попадают.
"""

import asyncio
import logging
from typing import Protocol

import httpx

from app.errors import AppError

logger = logging.getLogger(__name__)


class LLMError(AppError):
    """Базовая ошибка LLM. user_message показывается менеджеру."""

    status_code = 502
    code = "llm_error"
    user_message = "Не удалось получить ответ от модели. Попробуйте ещё раз."


class LLMTimeoutError(LLMError):
    status_code = 504
    code = "llm_timeout"
    user_message = "Модель не ответила вовремя. Попробуйте ещё раз через несколько секунд."


class LLMUnavailableError(LLMError):
    status_code = 503
    code = "llm_unavailable"
    user_message = "Сервис модели временно недоступен. Попробуйте ещё раз позже."


class LLMAuthError(LLMError):
    status_code = 503
    code = "llm_auth"
    user_message = "Ошибка доступа к модели: проверьте LLM_API_KEY."


class LLMRequestError(LLMError):
    status_code = 502
    code = "llm_bad_request"
    user_message = "Модель отклонила запрос: проверьте LLM_MODEL и параметры в .env."


class LLMBadResponseError(LLMError):
    status_code = 502
    code = "llm_bad_response"
    user_message = "Модель вернула некорректный ответ. Попробуйте ещё раз."


class LLMClient(Protocol):
    model: str

    async def complete(self, messages: list[dict[str, str]]) -> str: ...


class OpenAICompatibleClient:
    def __init__(
        self,
        *,
        base_url: str,
        model: str,
        api_key: str | None = None,
        temperature: float | None = 0.2,
        max_tokens: int | None = None,
        json_mode: bool = True,
        timeout_seconds: float = 30.0,
        max_retries: int = 2,
        backoff_seconds: float = 0.5,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.model = model
        self._temperature = temperature
        self._max_tokens = max_tokens
        self._json_mode = json_mode
        self._max_retries = max(0, max_retries)
        self._backoff = backoff_seconds
        headers = {"Content-Type": "application/json"}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        self._http = httpx.AsyncClient(
            base_url=base_url.rstrip("/"),
            headers=headers,
            timeout=httpx.Timeout(timeout_seconds, connect=10.0),
            transport=transport,
        )

    async def aclose(self) -> None:
        await self._http.aclose()

    def _payload(self, messages: list[dict[str, str]]) -> dict:
        payload: dict = {"model": self.model, "messages": messages}
        if self._temperature is not None:
            payload["temperature"] = self._temperature
        if self._max_tokens:
            payload["max_tokens"] = self._max_tokens
        if self._json_mode:
            payload["response_format"] = {"type": "json_object"}
        return payload

    async def complete(self, messages: list[dict[str, str]]) -> str:
        payload = self._payload(messages)
        last_error: LLMError = LLMUnavailableError()
        for attempt in range(self._max_retries + 1):
            if attempt:
                await asyncio.sleep(self._backoff * 2 ** (attempt - 1))
            try:
                response = await self._http.post("/chat/completions", json=payload)
            except httpx.TimeoutException:
                logger.warning("llm timeout (attempt %d)", attempt + 1)
                last_error = LLMTimeoutError()
                continue
            except httpx.TransportError as exc:
                logger.warning("llm network error %s (attempt %d)", type(exc).__name__, attempt + 1)
                last_error = LLMUnavailableError()
                continue

            status = response.status_code
            if status in (401, 403):
                logger.error("llm auth error: HTTP %d", status)
                raise LLMAuthError()
            if status == 429 or status >= 500:
                logger.warning("llm HTTP %d (attempt %d)", status, attempt + 1)
                last_error = LLMUnavailableError()
                continue
            if status >= 400:
                logger.error("llm request rejected: HTTP %d", status)
                raise LLMRequestError()
            return self._extract_content(response)
        raise last_error

    @staticmethod
    def _extract_content(response: httpx.Response) -> str:
        try:
            content = response.json()["choices"][0]["message"]["content"]
        except (ValueError, KeyError, IndexError, TypeError):
            logger.error("llm response has unexpected structure")
            raise LLMBadResponseError() from None
        if not isinstance(content, str) or not content.strip():
            logger.error("llm response content is empty")
            raise LLMBadResponseError()
        return content
