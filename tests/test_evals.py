"""Наборы оценок и их проверки (LLM подменена FakeLLM)."""

import json

import pytest

from app.knowledge.repository import KnowledgeBaseRepository
from app.llm.client import LLMTimeoutError
from app.schemas import Suggestion, SuggestionMeta, SuggestResponse
from evals.runner import (
    DialogueCase,
    EvalDataError,
    Expectation,
    check_dialogue,
    load_dialogue_suite,
    load_retrieval_suite,
    run_dialogues,
    run_retrieval,
)
from scripts.run_evals import main
from tests.conftest import KB_PATH, FakeLLM, llm_reply, make_settings, run
from tests.test_assistant import make_assistant


@pytest.fixture
def kb():
    return KnowledgeBaseRepository(KB_PATH).get()


def response(warnings=None, injection=False, **suggestion) -> SuggestResponse:
    return SuggestResponse(
        suggestion=Suggestion.model_validate(llm_reply(**suggestion)),
        meta=SuggestionMeta(
            request_id="x", model="fake", latency_ms=1, warnings=warnings or [], injection_suspected=injection
        ),
    )


# ---------- Поиск ----------


def test_retrieval_suite_meets_thresholds(kb):
    cases, thresholds = load_retrieval_suite(kb)
    report = run_retrieval(cases, thresholds, kb, make_settings().kb_top_k)
    failed = [r.case.id for r in report.results if not r.passed]
    assert report.passed, f"не прошли: {failed}"
    assert len(cases) >= 20


def test_retrieval_suite_rejects_unknown_ids(kb, tmp_path):
    path = tmp_path / "retrieval.json"
    path.write_text(
        json.dumps({"thresholds": {"min_hit_at_1": 1, "min_recall": 1},
                    "cases": [{"id": "a", "query": "монтаж", "expected_first": "no-such-item"}]}),
        encoding="utf-8",
    )
    with pytest.raises(EvalDataError, match="unknown ids"):
        load_retrieval_suite(kb, path)


def test_retrieval_report_fails_below_threshold(kb, tmp_path):
    path = tmp_path / "retrieval.json"
    path.write_text(
        json.dumps({"thresholds": {"min_hit_at_1": 1, "min_recall": 1},
                    "cases": [{"id": "wrong", "query": "Сколько стоит монтаж?", "expected_first": "wifi-module"}]}),
        encoding="utf-8",
    )
    cases, thresholds = load_retrieval_suite(kb, path)
    report = run_retrieval(cases, thresholds, kb, 5)
    assert not report.passed and report.hit_at_1 == 0
    assert report.results[0].first == "install-standard"


def test_cli_retrieval_passes(capsys):
    assert main(["retrieval"]) == 0
    assert "Результат: PASS" in capsys.readouterr().out


# ---------- Диалоги ----------


def test_dialogue_suite_is_valid(kb):
    cases = load_dialogue_suite(kb)
    assert len(cases) >= 10
    titles = " ".join(c.title for c in cases)
    assert "неуместна" in titles and "уточняющий" in titles  # сценарии ТЗ на месте


def test_dialogue_suite_rejects_unknown_expect_key(kb, tmp_path):
    path = tmp_path / "dialogues.json"
    path.write_text(
        json.dumps({"cases": [{"id": "a", "title": "t", "message": "m", "expect": {"upsell": True}}]}),
        encoding="utf-8",
    )
    with pytest.raises(EvalDataError, match="unknown expect keys"):
        load_dialogue_suite(kb, path)


def test_check_dialogue_passes_matching_answer():
    case = DialogueCase(
        "c", "t", "m",
        expect=Expectation(upsell_applicable=False, reply_contains_any=("42 900",), reply_not_contains=("скидк",)),
    )
    assert check_dialogue(case, response()) == []


def test_check_dialogue_reports_every_mismatch():
    case = DialogueCase(
        "c", "t", "m",
        expect=Expectation(
            upsell_applicable=False,
            injection_suspected=True,
            forbidden_upsell=("wifi-module",),
            reply_contains_any=("рассрочк",),
            reply_not_contains=("бриз",),
        ),
    )
    answer = response(
        warnings=["Сумма «500 ₽» в ответе клиенту не найдена в базе знаний — проверьте.",
                  "Из ответа клиенту удалён внутренний фрагмент — проверьте текст перед отправкой."],
        upsell_applicable=True,
        upsell_product_id="wifi-module",
        upsell_recommendation="Wi-Fi модуль",
        suggested_sales_phrase="Добавьте модуль",
    )
    failures = check_dialogue(case, answer)
    assert len(failures) == 7
    assert any("непроверенных сумм: 1" in f for f in failures)
    assert any("вырезал внутренний фрагмент" in f for f in failures)


def test_run_dialogues_records_answers_and_service_errors():
    cases = [
        DialogueCase("ok", "ответ есть", "Сколько стоит Бриз 09?", expect=Expectation(reply_contains_any=("42 900",))),
        DialogueCase("timeout", "модель молчит", "Сколько стоит монтаж?"),
    ]
    llm = FakeLLM(llm_reply(), LLMTimeoutError())
    results = run(run_dialogues(cases, make_assistant(llm)))
    assert [r.passed for r in results] == [True, False]
    assert results[0].customer_reply and results[0].latency_ms is not None
    assert results[1].failures == ["ошибка сервиса: llm_timeout"]


def test_cli_dialogues_requires_a_model(monkeypatch, tmp_path, capsys):
    monkeypatch.chdir(tmp_path)  # без .env
    for name in ("LLM_API_KEY", "LLM_BASE_URL"):
        monkeypatch.delenv(name, raising=False)
    assert main(["dialogues"]) == 2
    assert "LLM_API_KEY" in capsys.readouterr().out
