"""Explain Stage 07 quality gates using the committed workflow source."""

import tomllib
from html import escape

from reportlab.platypus import Spacer

from guide.i18n import loc, tr
from guide.layout import (
    AMBER,
    AMBER_L,
    CELL,
    CELL_M,
    GREEN,
    H2,
    SMALL,
    W,
    callout,
    code_block,
    p,
    simple_table,
)
from guide.sources import PROJECT_ROOT, read_source, source_slice
from guide.toc import section


def mypy_file_count() -> int:
    """Python files in the directories that [tool.mypy] files lists."""
    files = tomllib.loads(read_source("pyproject.toml"))["tool"]["mypy"]["files"]
    return sum(len(list((PROJECT_ROOT / name).rglob("*.py"))) for name in files)


def add_quality(story: list, verification: dict) -> None:
    """Append the CI extension while distinguishing local and hosted evidence."""
    tests = verification["tests"]["total"]
    typed = mypy_file_count()
    section(story, 28, tr(
        "Этап 07: одни и те же проверки на компьютере разработчика и в GitHub Actions.",
        "Stage 07: the same checks on the developer's computer and in GitHub Actions.",
    ), GREEN)
    story += [
        p(tr(
            "Файл .github/workflows/ci.yml запускает проверки при push, pull request и вручную. "
            "Задание работает в Ubuntu с Python 3.12. После установки зависимостей выполняются шесть проверок.",
            ".github/workflows/ci.yml runs checks on push, pull requests and manual dispatch. "
            "The job uses Ubuntu and Python 3.12. Six checks run after dependencies are installed.",
        )),
        Spacer(1, 9),
        simple_table([tr("Команда (python …)", "Command (python …)"), tr("Что проверяет", "Scope")], [
            ["-m ruff check app tests scripts evals", tr("Ошибки E4/E7/E9/F и порядок импортов I; без обязательного переформатирования.", "E4/E7/E9/F code errors and I import ordering; no formatting gate.")],
            ["-m mypy app evals", tr(f"Все {typed} файлов app и evals: сигнатуры и тела функций; без общих исключений для импортов.", f"All {typed} app and evals files: function signatures and bodies; no blanket import exclusions.")],
            ["-m pytest", tr(f"{tests} тестов: FakeLLM вместо модели, MockTransport вместо HTTP.", f"{tests} tests: FakeLLM instead of a model, MockTransport instead of HTTP.")],
            ["scripts/run_evals.py retrieval", tr("Оценка поиска (этап 08): hit@1 и recall не ниже порогов из evals/retrieval.json.", "Retrieval evaluation (Stage 08): hit@1 and recall meet the thresholds in evals/retrieval.json.")],
            ["scripts/check_docs.py", tr("Локальные файлы и якоря Markdown; внешние URL не проверяются.", "Local Markdown files and anchors; external URLs are not checked.")],
            ["scripts/build_widget.py", tr("Архив widget.zip и обязательные файлы виджета.", "widget.zip archive and required widget files.")],
        ], [210, W - 210], [CELL_M, CELL]),
        p(tr("Установка и локальный запуск", "Install and run locally"), H2),
        code_block(
            ".venv/bin/python -m pip install -r requirements-dev.txt\n"
            ".venv/bin/python -m ruff check app tests scripts evals\n"
            ".venv/bin/python -m mypy app evals\n"
            ".venv/bin/python -m pytest\n"
            ".venv/bin/python scripts/run_evals.py retrieval\n"
            ".venv/bin/python scripts/check_docs.py\n"
            ".venv/bin/python scripts/build_widget.py"
        ),
        Spacer(1, 7),
        code_block(source_slice(".github/workflows/ci.yml", "permissions:", "  cancel-in-progress: true")),
        Spacer(1, 7),
        callout(tr(
            "<b>Границы CI.</b> Установка Python, actions и зависимостей требует сети; тесты "
            "работают с заглушками. Рабочие ключи LLM и amoCRM не нужны. Workflow не развёртывает "
            "приложение, не отправляет сообщения, не проверяет Docker и не заменяет визуальный просмотр PDF.",
            "<b>CI boundaries.</b> Installing Python, actions and dependencies needs network access; "
            "tests use fakes. No live LLM or amoCRM keys are needed. The workflow does not deploy "
            "the app, send messages, verify Docker or replace visual PDF review.",
        ), AMBER, AMBER_L),
        Spacer(1, 6),
        p(escape(loc(verification["ci"]["result"])), SMALL),
        p(tr(
            "При ошибке откройте упавший шаг в Actions и повторите его команду локально. "
            "Подробный разбор и ограничения: docs/STAGE_07.md и docs/instructions/ci-and-delivery.md.",
            "On failure, open the failed Actions step and repeat its command locally. "
            "Details and limitations: docs/STAGE_07.md and docs/instructions/ci-and-delivery.md.",
        ), SMALL),
    ]
