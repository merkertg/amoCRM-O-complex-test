"""Section 29: Stage 08 — quality evaluations and access protection.

Retrieval metrics come from a live run of the evaluation suite at build time;
the dialogue scenarios are read from evals/dialogues.json. No live LLM run is
claimed: the guide states that the dialogue suite still needs a configured model.
"""

from html import escape
from textwrap import dedent

from reportlab.platypus import KeepTogether, Spacer

from guide.diagrams import access_flow
from guide.i18n import loc, tr
from guide.layout import (
    AMBER,
    AMBER_L,
    BLUE,
    BLUE_L,
    CELL,
    CELL_M,
    GREEN,
    H2,
    SMALL,
    TEAL,
    TEAL_L,
    VIOLET,
    VIOLET_L,
    Diagram,
    W,
    callout,
    cards,
    code_block,
    p,
    simple_table,
)
from guide.sources import PROJECT_ROOT, _import_project, source_slice
from guide.toc import section


def evaluation_facts() -> dict:
    """Run the offline retrieval suite and read the dialogue suite from the repository."""
    _import_project()
    from app.knowledge.repository import KnowledgeBaseRepository
    from evals.runner import load_dialogue_suite, load_retrieval_suite, run_retrieval

    kb = KnowledgeBaseRepository(PROJECT_ROOT / "data" / "knowledge_base.json").get()
    cases, thresholds = load_retrieval_suite(kb)
    report = run_retrieval(cases, thresholds, kb, top_k=5)
    return {
        "retrieval_cases": len(cases),
        "hit_at_1": report.hit_at_1,
        "recall": report.recall,
        "thresholds": thresholds,
        "retrieval_passed": report.passed,
        "dialogues": [(case.id, case.title) for case in load_dialogue_suite(kb)],
    }


def add_evaluation(story: list, verification: dict) -> None:
    """Append section 29; numbers come from the live retrieval run and the suite files."""
    facts = evaluation_facts()
    section(story, 29, tr(
        "Этап 08: измерить качество поиска и ответов и закрыть платные запросы от посторонних.",
        "Stage 08: measure retrieval and answer quality, and keep strangers away from paid requests.",
    ), GREEN)
    story += [
        cards([
            (tr("Тест", "Test"), tr(
                "проверяет код: ответ модели задаёт FakeLLM. Зелёные тесты не говорят, хорошо ли отвечает настоящая модель.",
                "checks the code: FakeLLM supplies the model answer. Green tests say nothing about real model quality.",
            ), BLUE, BLUE_L),
            (tr("Оценка поиска", "Retrieval evaluation"), tr(
                f"{facts['retrieval_cases']} вопросов, офлайн, в CI: нужная позиция первая (hit@1) и обязательные — в промпте (recall).",
                f"{facts['retrieval_cases']} questions, offline, in CI: the right item first (hit@1), required items in the prompt (recall).",
            ), TEAL, TEAL_L),
            (tr("Оценка диалогов", "Dialogue evaluation"), tr(
                f"{len(facts['dialogues'])} сценариев через весь pipeline с моделью из .env; правила + отчёт с ответами.",
                f"{len(facts['dialogues'])} scenarios through the whole pipeline with the model from .env; rules + a report with replies.",
            ), VIOLET, VIOLET_L),
        ]),
        p(tr("Оценка поиска — результат этой сборки", "Retrieval evaluation — result of this build"), H2),
        code_block(
            ".venv/bin/python scripts/run_evals.py retrieval\n"
            f"hit@1 {facts['hit_at_1']:.3f} ({tr('порог', 'threshold')} {facts['thresholds']['min_hit_at_1']}) · "
            f"recall {facts['recall']:.3f} ({tr('порог', 'threshold')} {facts['thresholds']['min_recall']}) · "
            f"{tr('вопросов', 'questions')} {facts['retrieval_cases']}\n"
            + tr("Результат: ", "Result: ") + ("PASS" if facts["retrieval_passed"] else "FAIL")
        ),
        Spacer(1, 6),
        callout(tr(
            "<b>Первый прогон нашёл дефект.</b> «Какой гарантийный срок?» находил график работы: слово "
            "«гарантия» есть почти везде и весит мало, а редкое «срок» перевешивало. Исправлено в базе "
            "знаний — ключевыми словами «гарантийный срок», «срок гарантии» — без правки кода.",
            "<b>The first run found a defect.</b> «What is the warranty period?» matched the schedule: "
            "«warranty» appears almost everywhere and weighs little, while the rare word «period» won. "
            "Fixed in the knowledge base with extra keywords, without code changes.",
        ), TEAL, TEAL_L),
        p(tr("Сценарии диалогов", "Dialogue scenarios"), H2),
        simple_table(
            ["id", tr("Что проверяет", "What it checks")],
            [[case_id, escape(title)] for case_id, title in facts["dialogues"]],
            [150, W - 150],
            [CELL_M, CELL],
        ),
        Spacer(1, 4),
        p(tr(
            "Названия сценариев — из evals/dialogues.json (на русском). Правила детерминированные: решение о "
            "допродаже, уточняющий вопрос, запрещённые фразы, непроверенные суммы. На настоящей модели набор "
            "ещё не запускался: нужен ключ API.",
            "Scenario titles come from evals/dialogues.json (in Russian). Rules are deterministic: upsell "
            "decision, clarification, forbidden phrases, unverified amounts. The suite has not yet run on a "
            "real model: it needs an API key.",
        ), SMALL),
        KeepTogether([p(tr("Защита доступа", "Access protection"), H2), Diagram(112, access_flow)]),
        Spacer(1, 8),
        simple_table([tr("Настройка", "Setting"), tr("Что делает", "What it does")], [
            ["UI_BASIC_AUTH_USERNAME<br/>UI_BASIC_AUTH_PASSWORD", tr(
                "Вход менеджера для /, /static, /api/v1/suggest, /docs. Задаются парой, иначе сервер не стартует. Только с HTTPS: Basic не шифрует пароль.",
                "Manager login for /, /static, /api/v1/suggest, /docs. Set both or the server refuses to start. HTTPS only: Basic does not encrypt the password.",
            )],
            ["RATE_LIMIT_PER_MINUTE", tr(
                "Генераций в минуту на IP или пользователя amoCRM (по умолчанию 30, 0 — выключено). Сверх лимита — 429 и Retry-After.",
                "Generations per minute per IP or amoCRM user (default 30, 0 disables). Over the limit — 429 with Retry-After.",
            )],
            ["FORWARDED_ALLOW_IPS", tr(
                "Переменная Uvicorn: за прокси укажите его адрес, чтобы лимит считался по настоящему клиенту.",
                "A Uvicorn variable: behind a proxy set its address so the limit counts the real client.",
            )],
        ], [160, W - 160], [CELL_M, CELL]),
        p(tr("Скользящее окно лимита", "Sliding rate-limit window"), H2),
        code_block(dedent(source_slice("app/api/access.py", "while calls and now - calls[0]", "calls.append(now)"))),
        Spacer(1, 6),
        callout(tr(
            "<b>Проверено:</b> тесты доступа и оценок; живой Uvicorn с curl — 401 без логина, 200 с логином, "
            "/health открыт, 429 с Retry-After; в браузере — плашка о лимите. <b>Не проверено:</b> интерфейс за "
            "паролем в браузере и оценка диалогов на настоящей модели.",
            "<b>Verified:</b> access and evaluation tests; a live Uvicorn with curl — 401 without login, 200 "
            "with it, /health public, 429 with Retry-After; the limit message in the browser. <b>Not verified:</b> "
            "the UI behind a password in a browser and the dialogue suite on a real model.",
        ), AMBER, AMBER_L),
        p(escape(loc(verification["stage_08"]["summary"])), SMALL),
    ]
