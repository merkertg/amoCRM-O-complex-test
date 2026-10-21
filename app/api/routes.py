"""Основной REST API: генерация подсказок, состояние сервиса, база знаний."""

from typing import Any

from fastapi import APIRouter, Request

from app.core.assistant import SalesAssistant
from app.core.dialog import parse_history_text
from app.schemas import DialogContext, ErrorResponse, SuggestRequest, SuggestResponse

router = APIRouter()

# Match FastAPI's response metadata contract, including named status codes.
ERROR_RESPONSES: dict[int | str, dict[str, Any]] = {
    422: {"model": ErrorResponse, "description": "Некорректный запрос"},
    502: {"model": ErrorResponse, "description": "Модель вернула некорректный ответ"},
    503: {"model": ErrorResponse, "description": "LLM или база знаний недоступны"},
    504: {"model": ErrorResponse, "description": "Таймаут LLM"},
}


@router.post(
    "/api/v1/suggest",
    response_model=SuggestResponse,
    responses=ERROR_RESPONSES,
    tags=["assistant"],
    summary="Сгенерировать ответ клиенту и подсказку по допродаже",
)
async def suggest(body: SuggestRequest, request: Request) -> SuggestResponse:
    """Принимает сообщение клиента и историю переписки, возвращает два блока:

    * `customer_reply` — черновик ответа клиенту (менеджер проверяет и отправляет сам);
    * `upsell_*`, `suggested_sales_phrase` — внутренняя подсказка, клиенту не отправляется.

    Историю можно передать списком `history` или текстом `history_text`
    (строки «Клиент: …» / «Менеджер: …»). Если переданы оба — используется `history`.
    """
    assistant: SalesAssistant = request.app.state.assistant
    history = body.history or (parse_history_text(body.history_text) if body.history_text else [])
    context = DialogContext(
        message=body.message,
        history=history,
        client_name=body.client_name,
        source="manual",
    )
    return await assistant.suggest(context)


@router.get("/health", tags=["service"], summary="Состояние сервиса")
async def health(request: Request) -> dict:
    settings = request.app.state.settings
    repo = request.app.state.kb_repo
    kb_status: dict = {"path": repo.path.name}
    try:
        kb = repo.get()
        kb_status.update(products=len(kb.products), faq=len(kb.faq))
    except Exception:  # noqa: BLE001 - /health не должен падать
        kb_status["loaded"] = False
    if repo.loaded_at:
        kb_status["loaded_at"] = repo.loaded_at.isoformat()
    if repo.last_error:
        kb_status["last_error"] = repo.last_error
    return {
        "status": "ok" if "products" in kb_status and not repo.last_error else "degraded",
        "llm": {"model": settings.llm_model, "api_key_set": settings.llm_api_key is not None},
        "knowledge_base": kb_status,
        "amocrm_enabled": settings.amocrm_enabled,
    }


@router.get("/api/v1/knowledge-base", tags=["knowledge base"], summary="Содержимое базы знаний")
async def knowledge_base(request: Request) -> dict:
    """Краткий список позиций — чтобы менеджер видел, на какие факты опирается ассистент."""
    kb = request.app.state.kb_repo.get()
    return {
        "company": kb.company.name,
        "products": [
            {
                "id": p.id,
                "name": p.name,
                "type": p.type,
                "category": p.category,
                "price": p.price.render() if p.price else None,
            }
            for p in kb.products
        ],
        "faq": [{"id": f.id, "topic": f.topic} for f in kb.faq],
    }
