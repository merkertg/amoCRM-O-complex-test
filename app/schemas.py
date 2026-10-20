"""Pydantic-модели: контракт REST API и структурированный ответ LLM."""

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, ValidationInfo, field_validator


class Role(StrEnum):
    CLIENT = "client"
    MANAGER = "manager"
    UNKNOWN = "unknown"


class DialogMessage(BaseModel):
    role: Role
    text: str = Field(min_length=1, max_length=4000)


class DialogContext(BaseModel):
    """Нормализованный контекст диалога — единый вход для бизнес-логики.

    Его собирает либо REST API (ручной ввод), либо адаптер amoCRM.
    """

    message: str
    history: list[DialogMessage] = Field(default_factory=list)
    client_name: str | None = None
    source: str = "manual"


# ---------- REST API: запрос ----------


class SuggestRequest(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "message": "Сколько стоит установка? Хочу Бриз 09 в спальню",
                    "history_text": "Клиент: Здравствуйте, подбираю кондиционер\n"
                    "Менеджер: Добрый день! Какая площадь комнаты?",
                    "client_name": "Анна",
                }
            ]
        }
    )

    message: str = Field(
        min_length=1, max_length=4000, description="Текущее сообщение клиента"
    )
    history: list[DialogMessage] = Field(
        default_factory=list,
        max_length=50,
        description="История переписки в структурированном виде (необязательно)",
    )
    history_text: str | None = Field(
        default=None,
        max_length=12000,
        description="История одним текстом: строки «Клиент: …» / «Менеджер: …»",
    )
    client_name: str | None = Field(default=None, max_length=100)

    @field_validator("message")
    @classmethod
    def _not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Сообщение клиента не должно быть пустым")
        return value


# ---------- Структурированный ответ ----------


class Suggestion(BaseModel):
    """Два независимых блока: ответ клиенту и внутренняя подсказка менеджеру."""

    customer_reply: str = Field(
        min_length=1, max_length=3000, description="Черновик ответа клиенту"
    )
    needs_clarification: bool = Field(
        default=False, description="Ответ содержит уточняющий вопрос: фактов не хватило"
    )
    upsell_applicable: bool = Field(description="Уместна ли допродажа сейчас")
    upsell_product_id: str | None = Field(
        default=None, description="ID позиции из базы знаний"
    )
    upsell_recommendation: str | None = Field(
        default=None, description="Рекомендуемый товар или услуга"
    )
    upsell_reason: str = Field(
        default="", description="Почему допродажа уместна (или почему нет)"
    )
    suggested_sales_phrase: str | None = Field(
        default=None, description="Пример фразы для менеджера"
    )

    @field_validator(
        "customer_reply",
        "upsell_product_id",
        "upsell_recommendation",
        "upsell_reason",
        "suggested_sales_phrase",
        mode="before",
    )
    @classmethod
    def _strip(cls, value, info: ValidationInfo):
        if value is None and info.field_name == "upsell_reason":
            return ""
        if isinstance(value, str):
            value = value.strip()
            if value.lower() in {"", "null", "none"}:
                return "" if info.field_name == "upsell_reason" else None
        return value


class KnowledgeSource(BaseModel):
    id: str
    name: str


class SuggestionMeta(BaseModel):
    request_id: str
    model: str
    latency_ms: int
    knowledge_sources: list[KnowledgeSource] = Field(
        default_factory=list, description="Позиции базы знаний, переданные модели"
    )
    injection_suspected: bool = Field(
        default=False, description="В сообщении клиента найдены признаки prompt injection"
    )
    warnings: list[str] = Field(
        default_factory=list, description="Что менеджеру стоит перепроверить"
    )


class SuggestResponse(BaseModel):
    suggestion: Suggestion
    meta: SuggestionMeta


class ErrorBody(BaseModel):
    code: str
    message: str


class ErrorResponse(BaseModel):
    error: ErrorBody
