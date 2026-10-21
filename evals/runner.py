"""Quality evaluations: offline retrieval and live-LLM dialogues.

Retrieval evaluation is deterministic and needs no network: it runs the real
KnowledgeIndex on fixed questions and gates CI on hit@1 and recall.

Dialogue evaluation sends fixed scenarios through the full SalesAssistant
pipeline with the configured LLM and checks the structured answer with
deterministic rules (upsell decision, clarification, forbidden phrases,
unverified amounts). It measures a real model only when a key is configured;
the rules can miss a bad answer that happens to pass them, so the report keeps
every reply for a human review.
"""

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from app.core.assistant import SalesAssistant
from app.core.dialog import parse_history_text
from app.errors import AppError
from app.knowledge.models import KnowledgeBase
from app.knowledge.search import KnowledgeIndex
from app.schemas import DialogContext, SuggestResponse

EVALS_DIR = Path(__file__).resolve().parent
RETRIEVAL_SUITE = EVALS_DIR / "retrieval.json"
DIALOGUE_SUITE = EVALS_DIR / "dialogues.json"

# Warning texts produced by app/core/assistant.py; the checks count them.
UNVERIFIED_MARK = "не найдена в базе знаний"
LEAK_MARK = "удалён внутренний фрагмент"


class EvalDataError(ValueError):
    """An evaluation file is malformed or references unknown knowledge base ids."""


def _known_ids(kb: KnowledgeBase) -> set[str]:
    return {p.id for p in kb.products} | {f.id for f in kb.faq}


def _read_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise EvalDataError(f"{path.name}: expected a JSON object")
    return data


def _unique_ids(items: list[dict[str, Any]], source: str) -> None:
    ids = [item.get("id") for item in items]
    if any(not isinstance(i, str) or not i for i in ids) or len(ids) != len(set(ids)):
        raise EvalDataError(f"{source}: every case needs a unique non-empty id")


# ---------- Retrieval ----------


@dataclass(frozen=True)
class RetrievalCase:
    id: str
    query: str
    expected_first: str
    must_include: tuple[str, ...] = ()
    context: str = ""


@dataclass(frozen=True)
class RetrievalResult:
    case: RetrievalCase
    returned: list[str]
    first: str | None
    hit: bool
    recall: float

    @property
    def passed(self) -> bool:
        return self.hit and self.recall == 1.0


@dataclass(frozen=True)
class RetrievalReport:
    results: list[RetrievalResult]
    hit_at_1: float
    recall: float
    min_hit_at_1: float
    min_recall: float

    @property
    def passed(self) -> bool:
        return self.hit_at_1 >= self.min_hit_at_1 and self.recall >= self.min_recall


def load_retrieval_suite(kb: KnowledgeBase, path: Path = RETRIEVAL_SUITE) -> tuple[list[RetrievalCase], dict[str, float]]:
    """Read cases and thresholds; every referenced id must exist in the knowledge base."""
    data = _read_json(path)
    raw_cases = data.get("cases")
    thresholds = data.get("thresholds")
    if not isinstance(raw_cases, list) or not raw_cases or not isinstance(thresholds, dict):
        raise EvalDataError(f"{path.name}: needs non-empty 'cases' and 'thresholds'")
    _unique_ids(raw_cases, path.name)
    known = _known_ids(kb)
    cases = []
    for item in raw_cases:
        case = RetrievalCase(
            id=item["id"],
            query=item["query"],
            expected_first=item["expected_first"],
            must_include=tuple(item.get("must_include", [])),
            context=item.get("context", ""),
        )
        unknown = ({case.expected_first} | set(case.must_include)) - known
        if unknown:
            raise EvalDataError(f"{path.name}: {case.id} references unknown ids {sorted(unknown)}")
        cases.append(case)
    limits = {key: float(thresholds[key]) for key in ("min_hit_at_1", "min_recall")}
    return cases, limits


def run_retrieval(
    cases: list[RetrievalCase], thresholds: dict[str, float], kb: KnowledgeBase, top_k: int
) -> RetrievalReport:
    """Run the real index: hit@1 — expected item first; recall — required items returned."""
    index = KnowledgeIndex(kb)
    results = []
    for case in cases:
        hits = index.search(case.query, case.context, top_k=top_k)
        returned = [h.id for h in hits]
        matches = [h.id for h in hits if h.reason == "match"]
        first = matches[0] if matches else None
        required = set(case.must_include) | {case.expected_first}
        recall = len(required & set(returned)) / len(required)
        results.append(RetrievalResult(case, returned, first, first == case.expected_first, recall))
    count = len(results)
    return RetrievalReport(
        results=results,
        hit_at_1=sum(r.hit for r in results) / count,
        recall=sum(r.recall for r in results) / count,
        min_hit_at_1=thresholds["min_hit_at_1"],
        min_recall=thresholds["min_recall"],
    )


# ---------- Dialogues ----------

_EXPECT_KEYS = {
    "upsell_applicable",
    "needs_clarification",
    "injection_suspected",
    "allowed_upsell",
    "forbidden_upsell",
    "reply_contains_any",
    "reply_not_contains",
    "max_unverified_amounts",
    "allow_removed_leaks",
}


@dataclass(frozen=True)
class Expectation:
    upsell_applicable: bool | None = None
    needs_clarification: bool | None = None
    injection_suspected: bool | None = None
    allowed_upsell: tuple[str, ...] = ()
    forbidden_upsell: tuple[str, ...] = ()
    reply_contains_any: tuple[str, ...] = ()
    reply_not_contains: tuple[str, ...] = ()
    max_unverified_amounts: int = 0
    allow_removed_leaks: bool = False


@dataclass(frozen=True)
class DialogueCase:
    id: str
    title: str
    message: str
    history_text: str = ""
    client_name: str | None = None
    expect: Expectation = field(default_factory=Expectation)


@dataclass
class DialogueResult:
    case_id: str
    title: str
    failures: list[str]
    customer_reply: str | None = None
    upsell_applicable: bool | None = None
    upsell_product_id: str | None = None
    needs_clarification: bool | None = None
    warnings: list[str] = field(default_factory=list)
    latency_ms: int | None = None

    @property
    def passed(self) -> bool:
        return not self.failures


def load_dialogue_suite(kb: KnowledgeBase, path: Path = DIALOGUE_SUITE) -> list[DialogueCase]:
    """Read scenarios; unknown expectation keys and product ids are rejected."""
    data = _read_json(path)
    raw_cases = data.get("cases")
    if not isinstance(raw_cases, list) or not raw_cases:
        raise EvalDataError(f"{path.name}: needs non-empty 'cases'")
    _unique_ids(raw_cases, path.name)
    product_ids = {p.id for p in kb.products}
    cases = []
    for item in raw_cases:
        raw_expect = item.get("expect", {})
        unknown_keys = set(raw_expect) - _EXPECT_KEYS
        if unknown_keys:
            raise EvalDataError(f"{path.name}: {item['id']} has unknown expect keys {sorted(unknown_keys)}")
        # JSON lists become tuples: Expectation is frozen and hashable.
        values: dict[str, Any] = {
            key: tuple(value) if isinstance(value, list) else value for key, value in raw_expect.items()
        }
        expect = Expectation(**values)
        unknown_ids = (set(expect.allowed_upsell) | set(expect.forbidden_upsell)) - product_ids
        if unknown_ids:
            raise EvalDataError(f"{path.name}: {item['id']} references unknown products {sorted(unknown_ids)}")
        cases.append(
            DialogueCase(
                id=item["id"],
                title=item["title"],
                message=item["message"],
                history_text=item.get("history_text", ""),
                client_name=item.get("client_name"),
                expect=expect,
            )
        )
    return cases


def check_dialogue(case: DialogueCase, response: SuggestResponse) -> list[str]:
    """Deterministic checks of one structured answer; returns failure descriptions."""
    expect = case.expect
    s = response.suggestion
    reply = s.customer_reply.lower()
    failures = []
    if expect.upsell_applicable is not None and s.upsell_applicable != expect.upsell_applicable:
        failures.append(f"upsell_applicable={s.upsell_applicable}, ожидалось {expect.upsell_applicable}")
    if expect.needs_clarification is not None and s.needs_clarification != expect.needs_clarification:
        failures.append(f"needs_clarification={s.needs_clarification}, ожидалось {expect.needs_clarification}")
    if expect.injection_suspected is not None and response.meta.injection_suspected != expect.injection_suspected:
        failures.append(f"injection_suspected={response.meta.injection_suspected}, ожидалось {expect.injection_suspected}")
    if s.upsell_applicable and expect.allowed_upsell and s.upsell_product_id not in expect.allowed_upsell:
        failures.append(f"допродажа {s.upsell_product_id} не из списка {list(expect.allowed_upsell)}")
    if s.upsell_product_id in expect.forbidden_upsell:
        failures.append(f"допродажа {s.upsell_product_id} запрещена в этом сценарии")
    if expect.reply_contains_any and not any(term.lower() in reply for term in expect.reply_contains_any):
        failures.append(f"в ответе нет ни одного из {list(expect.reply_contains_any)}")
    for term in expect.reply_not_contains:
        if term.lower() in reply:
            failures.append(f"в ответе есть «{term}»")
    unverified = sum(UNVERIFIED_MARK in w for w in response.meta.warnings)
    if unverified > expect.max_unverified_amounts:
        failures.append(f"непроверенных сумм: {unverified}")
    if not expect.allow_removed_leaks and any(LEAK_MARK in w for w in response.meta.warnings):
        failures.append("сервер вырезал внутренний фрагмент из ответа клиенту")
    return failures


async def run_dialogues(cases: list[DialogueCase], assistant: SalesAssistant) -> list[DialogueResult]:
    """Run scenarios one by one; a service error is recorded as a failed case."""
    results = []
    for case in cases:
        context = DialogContext(
            message=case.message,
            history=parse_history_text(case.history_text) if case.history_text else [],
            client_name=case.client_name,
            source="eval",
        )
        try:
            response = await assistant.suggest(context)
        except AppError as error:
            results.append(DialogueResult(case.id, case.title, [f"ошибка сервиса: {error.code}"]))
            continue
        s = response.suggestion
        results.append(
            DialogueResult(
                case_id=case.id,
                title=case.title,
                failures=check_dialogue(case, response),
                customer_reply=s.customer_reply,
                upsell_applicable=s.upsell_applicable,
                upsell_product_id=s.upsell_product_id,
                needs_clarification=s.needs_clarification,
                warnings=response.meta.warnings,
                latency_ms=response.meta.latency_ms,
            )
        )
    return results
