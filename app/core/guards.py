"""Защитные проверки до и после вызова LLM.

До вызова:
- detect_prompt_injection — эвристики, находящие попытки управлять моделью
  из сообщения клиента (результат — предупреждение менеджеру и модели);
- sanitize_untrusted — вырезает управляющие символы и «теги» разметки
  промпта, чтобы клиент не мог закрыть блок <customer_message> и дописать
  свои инструкции;
- redact_pii — маскирует телефоны, e-mail и номера карт перед отправкой в LLM.

После вызова:
- strip_internal_leaks — удаляет из ответа клиенту фрагменты внутренней
  подсказки (допродажа, служебные поля, упоминания инструкций);
- find_unverified_amounts — ищет суммы и проценты, которых нет ни в базе
  знаний, ни в переписке (защита от выдуманных цен);
- enforce_upsell_rules — допродажа только из базы знаний, при неуместности
  поля рекомендации очищаются.
"""

import re

from app.knowledge.models import KnowledgeBase
from app.schemas import Suggestion

# ---------- Prompt injection ----------

_INJECTION_PATTERNS: dict[str, re.Pattern[str]] = {
    "override_instructions": re.compile(
        r"(игнорир\w*|забуд\w*|не\s+обращай\w*\s+внимани\w*\s+на|отмен\w*|ignore|disregard|forget)"
        r"\s+(?:\S+\s+){0,3}?(инструкц\w*|правил\w*|промпт\w*|указани\w*|ограничени\w*|"
        r"instructions?|prompts?|rules)",
        re.IGNORECASE,
    ),
    "role_change": re.compile(
        r"(ты\s+теперь|теперь\s+ты|вы\s+теперь|притворись|представь,?\s+что\s+ты|веди\s+себя\s+как|"
        r"you\s+are\s+now|act\s+as|pretend\s+to\s+be|developer\s+mode|jailbreak|\bDAN\b)",
        re.IGNORECASE,
    ),
    "prompt_extraction": re.compile(
        r"(покажи|выведи|раскрой|напиши|перескажи|reveal|show|print|repeat)\s+(?:\S+\s+){0,3}?"
        r"(систем\w*|промпт\w*|инструкц\w*|system\s+prompt|instructions|подсказк\w*\s+менеджер\w*|"
        r"рекомендац\w*\s+менеджер\w*|базу\s+знаний)",
        re.IGNORECASE,
    ),
    "system_markup": re.compile(
        r"(</?\s*(system|assistant|developer|customer_message|dialog_history|knowledge_base|catalog)\b|"
        r"\[/?(system|inst)\]|<\|im_start\|>|###\s*(system|instruction))",
        re.IGNORECASE,
    ),
    "output_tampering": re.compile(
        r"(customer_reply|upsell_\w+|suggested_sales_phrase|needs_clarification)", re.IGNORECASE
    ),
}


def detect_prompt_injection(*texts: str) -> list[str]:
    """Возвращает названия сработавших правил (без цитирования текста)."""
    joined = "\n".join(t for t in texts if t)
    return [name for name, pattern in _INJECTION_PATTERNS.items() if pattern.search(joined)]


# ---------- Очистка входа ----------

_CONTROL_CHARS_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f​-‏‪-‮⁦-⁩]")
_PROMPT_TAG_RE = re.compile(
    r"</?\s*(customer_message|dialog_history|knowledge_base|catalog|client_info|system|"
    r"assistant|developer|instructions?)\b[^>]*>",
    re.IGNORECASE,
)


def sanitize_untrusted(text: str, max_chars: int) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = _CONTROL_CHARS_RE.sub("", text)
    text = _PROMPT_TAG_RE.sub("[удалено]", text)
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    if len(text) > max_chars:
        text = text[:max_chars].rstrip() + "…"
    return text


# ---------- Персональные данные ----------

_EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
_PHONE_RE = re.compile(r"(?<!\d)(?:\+7|8)[\s\-(]*\d{3}[\s\-)]*\d{3}[\s\-]*\d{2}[\s\-]*\d{2}(?!\d)")
_CARD_RE = re.compile(r"(?<!\d)(?:\d{4}[ \-]?){3}\d{4}(?!\d)")


def redact_pii(text: str) -> str:
    text = _EMAIL_RE.sub("[email]", text)
    text = _CARD_RE.sub("[номер карты]", text)
    return _PHONE_RE.sub("[телефон]", text)


# ---------- Утечки внутренней информации в ответ клиенту ----------

_LEAK_RE = re.compile(
    r"(upsell|cross[\s\-]?sell|допрода\w*|кросс[\s\-]?продаж\w*|перекр[её]стн\w*\s+продаж\w*|"
    r"подсказк\w*\s+(для\s+)?менеджер\w*|рекомендаци\w*\s+(для\s+)?менеджер\w*|"
    r"баз\w*\s+знаний|системн\w*\s+(промпт|инструкц)\w*|system\s+prompt|"
    r"customer_reply|upsell_\w+|suggested_sales_phrase|needs_clarification|"
    r"</?\s*(customer_message|dialog_history|knowledge_base|catalog)\b)",
    re.IGNORECASE,
)
_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?…])\s+")


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip().lower()


def strip_internal_leaks(suggestion: Suggestion) -> tuple[str, bool]:
    """Удаляет из customer_reply предложения с внутренней информацией.

    Возвращает (очищенный текст, были ли удаления).
    """
    internal = [
        _normalize(t)
        for t in (suggestion.upsell_reason, suggestion.suggested_sales_phrase)
        if t and len(t) >= 25
    ]
    removed = False
    kept_lines: list[str] = []
    for line in suggestion.customer_reply.split("\n"):
        kept: list[str] = []
        for sentence in _SENTENCE_SPLIT_RE.split(line):
            norm = _normalize(sentence)
            leaked = bool(_LEAK_RE.search(sentence)) or any(
                norm and (norm in chunk or chunk in norm) for chunk in internal if len(norm) >= 25
            )
            if leaked:
                removed = True
            else:
                kept.append(sentence)
        kept_lines.append(" ".join(kept).rstrip())
    text = re.sub(r"\n{3,}", "\n\n", "\n".join(kept_lines)).strip()
    return text, removed


# ---------- Проверка сумм ----------

_AMOUNT_RE = re.compile(
    r"(\d[\d\s  ]*\d|\d)(?:[.,]\d+)?\s*(₽|руб\w*|р\.|rub|%|процент\w*)",
    re.IGNORECASE,
)
_NUMBER_RE = re.compile(r"\d[\d\s  ]*\d|\d")


def _digits(value: str) -> str:
    return re.sub(r"\D", "", value)


def collect_known_numbers(*texts: str) -> set[str]:
    numbers: set[str] = set()
    for text in texts:
        for match in _NUMBER_RE.finditer(text or ""):
            raw = match.group(0)
            numbers.add(_digits(raw))
            # «42 900» и «42900» — одно число, но «до 3 метров 1 200» не должно склеиться
            numbers.update(_digits(part) for part in re.split(r"\s+", raw))
    return numbers


def find_unverified_amounts(text: str, known_numbers: set[str]) -> list[str]:
    """Суммы/проценты из text, которых нет в известных фактах.

    Сумма двух известных цен (например, «товар + монтаж») считается проверенной.
    """
    prices = {int(n) for n in known_numbers if n and len(n) <= 9 and int(n) >= 1000}
    unverified: list[str] = []
    for match in _AMOUNT_RE.finditer(text or ""):
        digits = _digits(match.group(1))
        if digits in known_numbers:
            continue
        value = int(digits)
        if match.group(2) != "%" and any(value - p in prices for p in prices):
            continue
        unverified.append(re.sub(r"\s+", " ", match.group(0)).strip())
    return unverified


# ---------- Правила допродажи ----------


def enforce_upsell_rules(suggestion: Suggestion, kb: KnowledgeBase) -> tuple[Suggestion, list[str]]:
    warnings: list[str] = []
    data = suggestion.model_dump()

    if data["upsell_applicable"]:
        product = kb.get_product(data["upsell_product_id"]) or kb.find_product_by_name(
            data["upsell_recommendation"]
        )
        if product is None:
            warnings.append(
                "Модель предложила допродажу позиции, которой нет в базе знаний, — рекомендация скрыта."
            )
            data.update(
                upsell_applicable=False,
                upsell_reason="Подходящей позиции для допродажи в базе знаний не найдено.",
            )
        else:
            data["upsell_product_id"] = product.id
            data["upsell_recommendation"] = product.name
            if not data["suggested_sales_phrase"]:
                warnings.append("Модель не предложила фразу для допродажи — сформулируйте её сами.")

    if not data["upsell_applicable"]:
        data.update(upsell_product_id=None, upsell_recommendation=None, suggested_sales_phrase=None)
        if not data["upsell_reason"]:
            data["upsell_reason"] = "Допродажа в этом сообщении неуместна."

    return Suggestion.model_validate(data), warnings
