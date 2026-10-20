"""Поиск релевантных фрагментов базы знаний.

Для базы из десятков позиций векторная БД не нужна: используем
взвешенный поиск по ключевым словам (упрощённый BM25) с лёгким
стеммингом для русского языка. Это прозрачно, быстро и детерминированно.

Алгоритм:
1. Текст разбивается на токены, токены приводятся к «основе»
   (отрезаем типичные окончания и обрезаем до 6 символов).
2. Каждое поле документа имеет вес (название и ключевые слова важнее описания).
3. Оценка = Σ по токенам запроса: вес лучшего поля × IDF токена × вес запроса
   (текущее сообщение важнее истории).
4. К найденным товарам добавляются связанные позиции (related) —
   кандидаты для допродажи.
"""

import math
import re
from dataclasses import dataclass, field
from typing import Literal

from app.knowledge.models import KnowledgeBase

_TOKEN_RE = re.compile(r"[a-zа-я0-9]+")
_WORD_NUMBER_RE = re.compile(r"([a-zа-я]{2,})[\s\-]*(\d{1,3})(?![\d,.])")

_STOPWORDS = {
    "и", "в", "во", "на", "с", "со", "к", "ко", "по", "о", "об", "от", "до", "за",
    "из", "у", "а", "но", "или", "ли", "же", "бы", "не", "ни", "да", "нет", "что",
    "как", "это", "этот", "эта", "то", "так", "для", "при", "мне", "меня", "мы",
    "нам", "нас", "вы", "вам", "вас", "ваш", "ваша", "ваши", "есть", "я", "он",
    "она", "они", "его", "ее", "их", "там", "тут", "здесь", "уже", "еще", "очень",
    "можно", "нужно", "надо", "хочу", "хотим", "хотел", "хотела", "подскажите",
    "скажите", "пожалуйста", "здравствуйте", "добрый", "день", "вечер", "утро",
    "привет", "спасибо", "какой", "какая", "какие", "какое", "сколько", "стоит",
    "будет", "стоить", "стоят", "стоимость", "цена", "цену", "цены", "почем",
    "the", "a", "an", "is", "to", "of", "and", "for", "in",
}

# Окончания отсекаются от длинных к коротким, основа — минимум 3 символа.
_ENDINGS = sorted(
    [
        "иями", "ями", "ами", "ией", "иям", "ием", "ого", "его", "ому", "ему", "ыми",
        "ими", "ить", "ать", "ять", "еть", "ая", "яя", "ое", "ее", "ые", "ие", "ый",
        "ий", "ой", "ей", "ов", "ев", "ом", "ем", "ам", "ям", "ах", "ях", "ию", "ью", "ия", "ья",
        "ть", "ся", "сь", "а", "я", "о", "е", "ы", "и", "у", "ю", "ь", "й",
    ],
    key=len,
    reverse=True,
)
_STEM_LENGTH = 6

# Веса полей документа.
_FIELD_WEIGHTS = {
    "name": 3.0,
    "keywords": 3.0,
    "topic": 3.0,
    "category": 2.0,
    "description": 1.0,
    "features": 1.0,
    "terms": 1.0,
    "answer": 1.0,
}


def stem(word: str) -> str:
    if word.isdigit() or len(word) <= 3:
        return word
    for ending in _ENDINGS:
        if word.endswith(ending) and len(word) - len(ending) >= 3:
            word = word[: -len(ending)]
            break
    return word[:_STEM_LENGTH]


def tokenize(text: str) -> list[str]:
    """Токены-основы. Число, стоящее после слова, склеивается с ним:
    «Бриз 18» -> «бриз#18», поэтому «комната 18 м²» не найдёт модель «Бриз 18»."""
    text = text.lower().replace("ё", "е")
    combos = [
        f"{stem(m.group(1))}#{m.group(2)}"
        for m in _WORD_NUMBER_RE.finditer(text)
        if m.group(1) not in _STOPWORDS
    ]
    text = _WORD_NUMBER_RE.sub(lambda m: m.group(1), text)
    words = [stem(t) for t in _TOKEN_RE.findall(text) if len(t) >= 2 and t not in _STOPWORDS]
    return words + combos


@dataclass(frozen=True)
class SearchHit:
    id: str
    kind: Literal["product", "faq"]
    name: str
    score: float
    reason: Literal["match", "related"] = "match"


@dataclass
class _Document:
    id: str
    kind: Literal["product", "faq"]
    name: str
    fields: dict[str, set[str]] = field(default_factory=dict)


class KnowledgeIndex:
    """Индекс строится один раз на версию базы знаний."""

    def __init__(self, kb: KnowledgeBase) -> None:
        self.kb = kb
        self._docs: list[_Document] = []
        for p in kb.products:
            self._docs.append(
                _Document(
                    id=p.id,
                    kind="product",
                    name=p.name,
                    fields={
                        "name": set(tokenize(p.name)),
                        "keywords": set(tokenize(" ".join(p.keywords))),
                        "category": set(tokenize(p.category)),
                        "description": set(tokenize(p.description)),
                        "features": set(tokenize(" ".join(p.features))),
                        "terms": set(tokenize(" ".join(p.terms))),
                    },
                )
            )
        for f in kb.faq:
            self._docs.append(
                _Document(
                    id=f.id,
                    kind="faq",
                    name=f.topic,
                    fields={
                        "topic": set(tokenize(f.topic)),
                        "keywords": set(tokenize(" ".join(f.keywords))),
                        "answer": set(tokenize(f.answer)),
                    },
                )
            )
        doc_freq: dict[str, int] = {}
        for doc in self._docs:
            for token in set().union(*doc.fields.values()):
                doc_freq[token] = doc_freq.get(token, 0) + 1
        total = max(len(self._docs), 1)
        self._idf = {t: math.log(1 + total / df) for t, df in doc_freq.items()}

    def search(
        self,
        query: str,
        context: str = "",
        top_k: int = 4,
        max_related: int = 3,
        context_weight: float = 0.5,
    ) -> list[SearchHit]:
        weights: dict[str, float] = {}
        for token in tokenize(context):
            weights[token] = max(weights.get(token, 0.0), context_weight)
        for token in tokenize(query):
            weights[token] = 1.0
        if not weights:
            return []

        scored: list[SearchHit] = []
        for doc in self._docs:
            score = 0.0
            for token, query_weight in weights.items():
                best_field = max(
                    (_FIELD_WEIGHTS[name] for name, tokens in doc.fields.items() if token in tokens),
                    default=0.0,
                )
                score += best_field * self._idf.get(token, 0.0) * query_weight
            if score > 0:
                scored.append(SearchHit(doc.id, doc.kind, doc.name, round(score, 3)))

        scored.sort(key=lambda h: h.score, reverse=True)
        hits = scored[:top_k]
        return hits + self._related(hits, max_related)

    def _related(self, hits: list[SearchHit], limit: int) -> list[SearchHit]:
        seen = {h.id for h in hits}
        related: list[SearchHit] = []
        for hit in hits:
            product = self.kb.get_product(hit.id) if hit.kind == "product" else None
            for related_id in product.related if product else []:
                if len(related) >= limit:
                    return related
                if related_id in seen:
                    continue
                seen.add(related_id)
                rel = self.kb.get_product(related_id)
                related.append(SearchHit(rel.id, "product", rel.name, 0.0, "related"))
        return related
