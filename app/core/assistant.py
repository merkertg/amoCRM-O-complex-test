"""Бизнес-логика: pipeline генерации подсказок.

1. Нормализация контекста (очистка, обрезка, маскирование ПДн).
2. Поиск релевантных фактов в базе знаний.
3. Сборка промпта.
4. Вызов LLM.
5. Разбор и валидация JSON (одна попытка «починки» при ошибке формата).
6. Пост-проверки: допродажа только из базы, нет утечек в ответ клиенту,
   нет непроверенных сумм.
"""

import json
import logging
import re
import time
import uuid

from pydantic import ValidationError

from app.config import Settings
from app.core.dialog import format_history
from app.core.guards import (
    collect_known_numbers,
    detect_prompt_injection,
    enforce_upsell_rules,
    find_unverified_amounts,
    redact_pii,
    sanitize_untrusted,
    strip_internal_leaks,
)
from app.core.prompts import REPAIR_PROMPT, build_messages
from app.errors import AppError
from app.knowledge.models import KnowledgeBase
from app.knowledge.repository import KnowledgeBaseRepository
from app.knowledge.search import KnowledgeIndex
from app.llm.client import LLMClient
from app.schemas import (
    DialogContext,
    DialogMessage,
    KnowledgeSource,
    Role,
    Suggestion,
    SuggestionMeta,
    SuggestResponse,
)

logger = logging.getLogger(__name__)


class LLMOutputError(AppError):
    status_code = 502
    code = "llm_invalid_output"
    user_message = "Модель вернула ответ в неверном формате. Попробуйте сгенерировать ещё раз."


class EmptyMessageError(AppError):
    status_code = 422
    code = "empty_message"
    user_message = "Сообщение клиента пустое — вставьте текст сообщения."


class OutputParseError(ValueError):
    def __init__(self, reason: str) -> None:
        self.reason = reason
        super().__init__(reason)


_FENCE_RE = re.compile(r"^```(?:json)?\s*(.*?)\s*```$", re.DOTALL)


def parse_suggestion(raw: str) -> Suggestion:
    """Достаёт JSON из ответа модели и валидирует его схемой Suggestion."""
    text = raw.strip()
    fence = _FENCE_RE.match(text)
    if fence:
        text = fence.group(1)
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        start, end = text.find("{"), text.rfind("}")
        if start == -1 or end <= start:
            raise OutputParseError("ответ не является JSON") from None
        try:
            data = json.loads(text[start : end + 1])
        except json.JSONDecodeError:
            raise OutputParseError("ответ не является JSON") from None
    if not isinstance(data, dict):
        raise OutputParseError("ожидался JSON-объект")
    try:
        return Suggestion.model_validate(data)
    except ValidationError as exc:
        fields = sorted({".".join(str(p) for p in err["loc"]) or "root" for err in exc.errors()})
        raise OutputParseError("ошибки в полях: " + ", ".join(fields)) from None


class SalesAssistant:
    def __init__(self, kb_repo: KnowledgeBaseRepository, llm: LLMClient, settings: Settings) -> None:
        self._kb_repo = kb_repo
        self._llm = llm
        self._settings = settings
        self._index_cache: tuple[KnowledgeBase, KnowledgeIndex] | None = None

    def _index(self, kb: KnowledgeBase) -> KnowledgeIndex:
        if self._index_cache is None or self._index_cache[0] is not kb:
            self._index_cache = (kb, KnowledgeIndex(kb))
        return self._index_cache[1]

    def _prepare_history(self, history: list[DialogMessage]) -> list[DialogMessage]:
        limit = self._settings.max_message_chars
        cleaned = []
        for item in history[-self._settings.max_history_messages :]:
            text = sanitize_untrusted(item.text, limit)
            if text:
                cleaned.append(DialogMessage(role=item.role, text=text))
        return cleaned

    async def suggest(self, ctx: DialogContext) -> SuggestResponse:
        started = time.perf_counter()
        request_id = uuid.uuid4().hex[:12]
        s = self._settings
        kb = self._kb_repo.get()

        # 1. Нормализация контекста
        message = sanitize_untrusted(ctx.message, s.max_message_chars)
        if not message:
            raise EmptyMessageError()
        history = self._prepare_history(ctx.history)
        client_name = sanitize_untrusted(ctx.client_name, 100) if ctx.client_name else None
        client_texts = [m.text for m in history if m.role != Role.MANAGER]
        injection_rules = detect_prompt_injection(ctx.message, *client_texts, client_name or "")

        # 2. Поиск фактов: текущее сообщение + последние реплики клиента как контекст
        hits = self._index(kb).search(message, " ".join(client_texts[-3:]), top_k=s.kb_top_k)

        # 3. Промпт (ПДн маскируются до отправки во внешний API)
        history_text = format_history(history)
        if len(history_text) > s.max_history_chars:
            history_text = "…\n" + history_text[-s.max_history_chars :]
        if s.redact_pii_for_llm:
            message, history_text = redact_pii(message), redact_pii(history_text)
        messages = build_messages(
            kb=kb,
            hits=hits,
            message=message,
            history=history_text,
            client_name=client_name,
            injection_suspected=bool(injection_rules),
        )

        # 4–5. LLM + валидация
        suggestion = await self._generate(messages)

        # 6. Пост-проверки
        suggestion, warnings = enforce_upsell_rules(suggestion, kb)
        reply, leaked = strip_internal_leaks(suggestion)
        if leaked:
            if not reply:
                raise LLMOutputError()
            suggestion = suggestion.model_copy(update={"customer_reply": reply})
            warnings.append("Из ответа клиенту удалён внутренний фрагмент — проверьте текст перед отправкой.")

        known = collect_known_numbers(kb.model_dump_json(), ctx.message, *(m.text for m in history))
        for amount in find_unverified_amounts(suggestion.customer_reply, known):
            warnings.append(f"Сумма «{amount}» в ответе клиенту не найдена в базе знаний — проверьте.")
        for amount in find_unverified_amounts(suggestion.suggested_sales_phrase or "", known):
            warnings.append(f"Сумма «{amount}» во фразе для допродажи не найдена в базе знаний — проверьте.")
        if not any(h.reason == "match" for h in hits):
            warnings.append("По запросу ничего не найдено в базе знаний — ответ не должен содержать конкретных условий.")
        if injection_rules:
            warnings.insert(
                0,
                "В сообщении клиента есть признаки попытки управлять ассистентом (prompt injection). "
                "Проверьте ответ особенно внимательно.",
            )

        latency_ms = int((time.perf_counter() - started) * 1000)
        logger.info(
            "suggestion ready id=%s source=%s latency_ms=%d sources=%s upsell=%s clarification=%s "
            "injection=%s warnings=%d",
            request_id,
            ctx.source,
            latency_ms,
            ",".join(h.id for h in hits) or "-",
            suggestion.upsell_applicable,
            suggestion.needs_clarification,
            ",".join(injection_rules) or "-",
            len(warnings),
        )
        return SuggestResponse(
            suggestion=suggestion,
            meta=SuggestionMeta(
                request_id=request_id,
                model=self._llm.model,
                latency_ms=latency_ms,
                knowledge_sources=[KnowledgeSource(id=h.id, name=h.name) for h in hits],
                injection_suspected=bool(injection_rules),
                warnings=warnings,
            ),
        )

    async def _generate(self, messages: list[dict[str, str]]) -> Suggestion:
        raw = await self._llm.complete(messages)
        try:
            return parse_suggestion(raw)
        except OutputParseError as exc:
            logger.warning("llm output rejected (%s), retrying with repair prompt", exc.reason)
            repair = [
                *messages,
                {"role": "assistant", "content": raw[:4000]},
                {"role": "user", "content": REPAIR_PROMPT.format(reason=exc.reason)},
            ]
        raw = await self._llm.complete(repair)
        try:
            return parse_suggestion(raw)
        except OutputParseError as exc:
            logger.error("llm output rejected after repair (%s)", exc.reason)
            raise LLMOutputError() from None
