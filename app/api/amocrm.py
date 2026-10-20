"""Эндпоинты интеграции с amoCRM: вызов из виджета и приём вебхуков."""

import hmac
import json
import logging
from urllib.parse import parse_qsl

from fastapi import APIRouter, Header, Query, Request
from pydantic import BaseModel, Field

from app.api.routes import ERROR_RESPONSES
from app.errors import AppError
from app.integrations.amocrm.adapter import AmoContextInfo
from app.integrations.amocrm.auth import verify_widget_token
from app.integrations.amocrm.webhooks import extract_chat_messages, parse_nested_form
from app.schemas import ErrorResponse, SuggestResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/amocrm", tags=["amoCRM"])


class AmoCRMDisabledError(AppError):
    status_code = 503
    code = "amocrm_disabled"
    user_message = "Интеграция с amoCRM не настроена на сервере (AMOCRM_ENABLED)."


class WebhookForbiddenError(AppError):
    status_code = 403
    code = "amocrm_webhook_forbidden"
    user_message = "Неверный секрет вебхука."


class InvalidWebhookError(AppError):
    status_code = 400
    code = "amocrm_webhook_invalid"
    user_message = "Не удалось разобрать тело вебхука."


class WidgetSuggestRequest(BaseModel):
    lead_id: int = Field(gt=0, description="ID сделки (APP.data.current_card.id)")
    message: str | None = Field(
        default=None,
        max_length=4000,
        description="Текст сообщения клиента. Если пусто — берётся последнее сообщение из чата",
    )
    history_text: str | None = Field(default=None, max_length=12000)


class WidgetSuggestResponse(SuggestResponse):
    context: AmoContextInfo


def _require_enabled(request: Request) -> None:
    if not request.app.state.settings.amocrm_enabled or request.app.state.amocrm_adapter is None:
        raise AmoCRMDisabledError()


@router.post(
    "/suggest",
    response_model=WidgetSuggestResponse,
    responses={401: {"model": ErrorResponse, "description": "Нет или неверный X-Auth-Token"}, **ERROR_RESPONSES},
    summary="Подсказка для сделки (вызов из виджета amoCRM)",
)
async def widget_suggest(
    body: WidgetSuggestRequest,
    request: Request,
    x_auth_token: str | None = Header(default=None, description="Одноразовый JWT от $authorizedAjax"),
) -> WidgetSuggestResponse:
    """Виджет в карточке сделки вызывает этот метод через `this.$authorizedAjax()`.

    Сервер проверяет подпись одноразового токена секретным ключом интеграции,
    собирает контекст (сообщение, история из вебхуков, имя клиента) и запускает
    тот же pipeline, что и `/api/v1/suggest`.
    """
    _require_enabled(request)
    settings = request.app.state.settings
    if settings.amocrm_client_secret is None:
        raise AmoCRMDisabledError("Не задан AMOCRM_CLIENT_SECRET для проверки токена виджета.")
    user = verify_widget_token(
        x_auth_token,
        secret=settings.amocrm_client_secret.get_secret_value(),
        client_id=settings.amocrm_client_id,
        account_base_url=settings.amocrm_base_url,
    )
    context, info, warnings = await request.app.state.amocrm_adapter.build_context(
        body.lead_id, message=body.message, history_text=body.history_text
    )
    logger.info(
        "amocrm suggest account=%d user=%d lead=%d source=%s history=%d",
        user.account_id,
        user.user_id,
        body.lead_id,
        info.message_source,
        info.history_messages,
    )
    result = await request.app.state.assistant.suggest(context)
    result.meta.warnings = warnings + result.meta.warnings
    return WidgetSuggestResponse(suggestion=result.suggestion, meta=result.meta, context=info)


@router.post(
    "/webhook",
    summary="Приём вебхуков amoCRM о сообщениях в чатах",
    responses={403: {"model": ErrorResponse}, 503: {"model": ErrorResponse}},
)
async def webhook(
    request: Request,
    secret: str = Query(default="", description="Секрет из AMOCRM_WEBHOOK_SECRET"),
) -> dict:
    """Сохраняет входящие (`message[add]`) и исходящие (`outgoing_message[add]`)
    сообщения в кэш, чтобы виджет мог построить историю диалога.

    amoCRM ждёт ответ не дольше 2 секунд, поэтому здесь нет вызова LLM —
    только разбор и сохранение.
    """
    _require_enabled(request)
    expected = request.app.state.settings.amocrm_webhook_secret
    if expected is None or not hmac.compare_digest(secret.encode(), expected.get_secret_value().encode()):
        raise WebhookForbiddenError()

    body = await request.body()
    try:
        if request.headers.get("content-type", "").startswith("application/json"):
            payload = json.loads(body or b"{}")
        else:  # x-www-form-urlencoded — основной формат вебхуков amoCRM
            payload = parse_nested_form(parse_qsl(body.decode("utf-8"), keep_blank_values=True))
    except (UnicodeDecodeError, ValueError):
        raise InvalidWebhookError() from None
    messages = extract_chat_messages(payload if isinstance(payload, dict) else {})
    store = request.app.state.message_store
    stored = sum(store.add(m) for m in messages)
    logger.info("amocrm webhook received=%d stored=%d", len(messages), stored)
    return {"received": len(messages), "stored": stored}
