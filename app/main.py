"""Точка входа FastAPI: сборка зависимостей, обработчики ошибок, статический UI.

Запуск: uvicorn app.main:app --reload
"""

import logging
import traceback
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app.api import amocrm as amocrm_api
from app.api import routes
from app.api.access import BasicAuthMiddleware, RateLimiter
from app.config import Settings, get_settings
from app.core.assistant import SalesAssistant
from app.errors import AppError
from app.integrations.amocrm.adapter import AmoCRMAdapter
from app.integrations.amocrm.client import AmoCRMClient
from app.integrations.amocrm.message_store import MessageStore
from app.knowledge.repository import KnowledgeBaseRepository
from app.llm.client import LLMClient, OpenAICompatibleClient
from app.logging_setup import setup_logging

logger = logging.getLogger(__name__)
STATIC_DIR = Path(__file__).parent / "static"

DESCRIPTION = """
AI-ассистент менеджера по продажам: по сообщению клиента и истории переписки
готовит **черновик ответа клиенту** и **внутреннюю подсказку по допродаже**.

Ассистент ничего не отправляет клиенту сам — менеджер проверяет текст и отправляет его вручную.
"""


def _error(status: int, code: str, message: str, headers: dict[str, str] | None = None) -> JSONResponse:
    return JSONResponse(
        status_code=status,
        content={"error": {"code": code, "message": message}},
        headers=headers or None,
    )


def build_llm_client(settings: Settings) -> OpenAICompatibleClient:
    return OpenAICompatibleClient(
        base_url=settings.llm_base_url,
        model=settings.llm_model,
        api_key=settings.llm_api_key.get_secret_value() if settings.llm_api_key else None,
        temperature=settings.llm_temperature,
        max_tokens=settings.llm_max_tokens,
        json_mode=settings.llm_json_mode,
        timeout_seconds=settings.llm_timeout_seconds,
        max_retries=settings.llm_max_retries,
    )


def build_amocrm_client(settings: Settings) -> AmoCRMClient | None:
    if not (settings.amocrm_base_url and settings.amocrm_access_token):
        return None
    return AmoCRMClient(
        base_url=settings.amocrm_base_url,
        access_token=settings.amocrm_access_token.get_secret_value(),
        timeout_seconds=settings.amocrm_timeout_seconds,
    )


def create_app(
    settings: Settings | None = None,
    llm_client: LLMClient | None = None,
    amocrm_client: AmoCRMClient | None = None,
) -> FastAPI:
    settings = settings or get_settings()
    setup_logging(settings.log_level)

    kb_repo = KnowledgeBaseRepository(settings.knowledge_base_path)
    try:
        kb_repo.get()
    except AppError:
        raise RuntimeError(f"База знаний не загружена: {kb_repo.last_error}") from None

    llm = llm_client or build_llm_client(settings)
    message_store = MessageStore(
        max_per_key=max(settings.amocrm_history_limit, 1) + 10,
        ttl_seconds=settings.amocrm_message_ttl_hours * 3600,
    )
    adapter = None
    if settings.amocrm_enabled:
        amocrm_client = amocrm_client or build_amocrm_client(settings)
        if amocrm_client is None:
            logger.warning("amoCRM API token is not set: lead/contact data will not be loaded")
        adapter = AmoCRMAdapter(amocrm_client, message_store, settings.amocrm_history_limit)

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        """Close configured external clients when the application shuts down."""
        yield
        for client in (llm, amocrm_client):
            close = getattr(client, "aclose", None)
            if close:
                await close()

    app = FastAPI(
        title="AI-ассистент менеджера amoCRM",
        description=DESCRIPTION,
        version="1.0.0",
        lifespan=lifespan,
    )
    app.state.settings = settings
    app.state.kb_repo = kb_repo
    app.state.assistant = SalesAssistant(kb_repo, llm, settings)
    app.state.message_store = message_store
    app.state.amocrm_adapter = adapter
    app.state.rate_limiter = RateLimiter(settings.rate_limit_per_minute)

    if settings.basic_auth_enabled:
        assert settings.ui_basic_auth_password is not None  # гарантирует basic_auth_enabled
        app.add_middleware(
            BasicAuthMiddleware,
            username=settings.ui_basic_auth_username,
            password=settings.ui_basic_auth_password.get_secret_value(),
        )
    else:
        logger.warning("manager UI and /api/v1/suggest are not protected: set UI_BASIC_AUTH_* outside localhost")

    if settings.cors_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=settings.cors_origins,
            allow_methods=["GET", "POST", "OPTIONS"],
            allow_headers=["Content-Type", "X-Auth-Token"],
        )

    @app.exception_handler(AppError)
    async def app_error_handler(_: Request, exc: AppError) -> JSONResponse:
        return _error(exc.status_code, exc.code, exc.user_message, exc.headers)

    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(_: Request, exc: RequestValidationError) -> JSONResponse:
        # Значения полей не возвращаем и не логируем: в них могут быть персональные данные.
        fields = sorted({".".join(str(p) for p in e["loc"] if p != "body") for e in exc.errors()})
        return _error(422, "validation_error", "Проверьте поля запроса: " + ", ".join(fields))

    @app.exception_handler(Exception)
    async def unhandled_error_handler(request: Request, exc: Exception) -> JSONResponse:
        # Только тип и стек вызовов, без str(exc): сообщение может содержать данные клиента.
        logger.error(
            "unhandled %s on %s\n%s",
            type(exc).__name__,
            request.url.path,
            "".join(traceback.format_tb(exc.__traceback__)),
        )
        return _error(500, "internal_error", AppError.user_message)

    app.include_router(routes.router)
    app.include_router(amocrm_api.router)
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

    @app.get("/", include_in_schema=False)
    async def index() -> FileResponse:
        return FileResponse(STATIC_DIR / "index.html")

    return app


app = create_app()
