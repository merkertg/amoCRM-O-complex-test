"""Append the bilingual command, troubleshooting and verification reference."""

from html import escape

from reportlab.platypus import KeepTogether, Spacer

from guide.i18n import loc, tr
from guide.layout import (
    AMBER,
    AMBER_L,
    BODY_S,
    CELL,
    CELL_B,
    CELL_M,
    GREEN,
    H2,
    QUESTION,
    SMALL,
    TEAL,
    W,
    callout,
    code_block,
    p,
    simple_table,
)
from guide.toc import section


def _command(story: list, title: str, command: str) -> None:
    """Keep a command label attached to its readable code block."""
    story.append(KeepTogether([p(title, H2), code_block(command), Spacer(1, 5)]))


def _localized(value: str | dict[str, str]) -> str:
    """Escape a localized verification value for ReportLab paragraph markup."""
    return escape(loc(value))


def add_reference(story: list, verification: dict) -> None:
    """Add sections 24–27 without treating historical checks as a new run."""
    section(
        story,
        24,
        tr(
            "Команды выполняются из корня проекта. Долгоживущие процессы — в отдельных терминалах.",
            "Run commands from the project root. Use separate terminals for long-running processes.",
        ),
        TEAL,
    )
    _command(
        story,
        tr("Первый запуск: Python 3.12 и локальное окружение", "First run: Python 3.12 and a local environment"),
        "python3.12 -m venv .venv\n"
        ".venv/bin/python -m pip install -r requirements-dev.txt\n"
        "cp .env.example .env",
    )
    story.append(
        p(
            tr(
                "Копируйте .env только при первой настройке; заполните параметры модели в редакторе. "
                "После изменения настроек перезапустите сервер.",
                "Copy .env only during initial setup; edit the model settings in an editor. "
                "Restart the server after changing settings.",
            ),
            SMALL,
        )
    )
    _command(
        story,
        tr("Терминал A: сервер; остановка — Ctrl+C", "Terminal A: server; stop with Ctrl+C"),
        ".venv/bin/python -m uvicorn app.main:app --reload",
    )
    _command(
        story,
        tr("Терминал B: здоровье и автономные тесты", "Terminal B: health and offline tests"),
        "curl -s http://127.0.0.1:8000/health\n"
        ".venv/bin/python -m pytest\n"
        ".venv/bin/python -m pytest -k injection -v",
    )
    _command(
        story,
        tr("Архив виджета и обе версии PDF", "Widget archive and both PDF editions"),
        ".venv/bin/python scripts/build_widget.py\n"
        "unzip -l dist/widget.zip\n"
        ".venv/bin/python -m pip install -r requirements-guide.txt\n"
        ".venv/bin/python scripts/build_guide.py",
    )
    _command(
        story,
        tr("Альтернатива локальному серверу: Docker", "Docker alternative to the local server"),
        "docker compose up --build\n"
        "docker compose down",
    )
    story.append(
        callout(
            tr(
                "<b>Без ключа модели.</b> Код заглушки и точная последовательность — "
                "docs/instructions/testing.md. Заглушка на :9100 и приложение на :8000 "
                "работают в двух терминалах; проверки curl выполняйте в третьем. Запускайте "
                "Uvicorn через .venv/bin/python -m uvicorn. Ответ заглушки проверяет связь "
                "компонентов, но не качество настоящей LLM.",
                "<b>Without a model key.</b> The stub source and exact sequence are in "
                "docs/instructions/testing.md. Run the stub on :9100 and the app on :8000 "
                "in two terminals; use a third for curl checks. Start Uvicorn with "
                ".venv/bin/python -m uvicorn. Stub responses check component wiring, "
                "but do not establish real LLM quality.",
            ),
            AMBER,
            AMBER_L,
        )
    )

    section(
        story,
        25,
        tr(
            "Сначала прочитайте error.code. Секреты и тексты клиента не прикладывайте к журналу ошибки.",
            "Read error.code first. Keep secrets and customer texts out of error reports.",
        ),
        AMBER,
    )
    error_rows = [
        (
            "422 · validation_error / empty_message",
            ("Проверьте обязательные поля и длину; вставьте непустое сообщение.", "Check required fields and lengths; provide a non-empty message."),
        ),
        (
            "503 · knowledge_base_unavailable",
            ("Проверьте путь и JSON базы знаний. При сломанном обновлении /health может быть degraded: используется последняя корректная версия.", "Check the knowledge base path and JSON. A broken update may make /health degraded while the last valid version is retained."),
        ),
        (
            "503 · llm_auth",
            ("Провайдер ответил 401/403: проверьте LLM_API_KEY; перезапустите сервис после правки .env.", "The provider returned 401/403: check LLM_API_KEY; restart after editing .env."),
        ),
        (
            "502 · llm_bad_request",
            ("Проверьте модель и параметры; если провайдер их не поддерживает — LLM_TEMPERATURE=none или LLM_JSON_MODE=false.", "Check the model and parameters; if unsupported, use LLM_TEMPERATURE=none or LLM_JSON_MODE=false."),
        ),
        (
            "503 · llm_unavailable / 504 · llm_timeout",
            ("Проверьте доступность LLM_BASE_URL и лимиты провайдера. Сервис уже повторил запрос согласно LLM_MAX_RETRIES.", "Check LLM_BASE_URL availability and provider limits. The service already retried according to LLM_MAX_RETRIES."),
        ),
        (
            "502 · llm_bad_response / llm_invalid_output",
            ("Первый код — неверная оболочка ответа API; второй — JSON подсказки не прошёл проверку даже после одной попытки исправления.", "The first means a malformed provider response; the second means the suggestion JSON failed validation even after one repair attempt."),
        ),
        (
            "503 · amocrm_disabled",
            ("Проверьте AMOCRM_ENABLED и AMOCRM_CLIENT_SECRET; настройки читаются при запуске.", "Check AMOCRM_ENABLED and AMOCRM_CLIENT_SECRET; settings are read at startup."),
        ),
        (
            "401 · amocrm_widget_unauthorized",
            ("Откройте виджет из карточки сделки. Проверьте секрет, ID интеграции и адрес аккаунта; не сохраняйте JWT в отчётах.", "Open the widget from a lead card. Check the secret, integration ID and account address; do not save JWTs in reports."),
        ),
        (
            "403 · amocrm_webhook_forbidden / 400 · amocrm_webhook_invalid",
            ("Сверьте секрет вебхука либо исправьте формат JSON/UTF-8. Не публикуйте URL с секретом.", "Check the webhook secret or fix the JSON/UTF-8 body. Do not publish URLs containing a secret."),
        ),
        (
            "404 · amocrm_lead_not_found / 422 · amocrm_no_message",
            ("Проверьте ID сделки. Если кэш пуст после перезапуска или вебхуки ещё не пришли, вставьте сообщение вручную.", "Check the lead ID. If the cache is empty after restart or before webhooks arrive, paste the message manually."),
        ),
        (
            "502 · amocrm_error",
            ("Проверьте доступ REST API и серверный токен. Адаптер перехватывает этот сбой и продолжает по переписке с предупреждением.", "Check REST API availability and the server token. The adapter catches this failure and continues from the conversation with a warning."),
        ),
        (
            "500 · internal_error",
            ("Повторите запрос. Для разбора используйте код ошибки и технические идентификаторы, без переписки и персональных данных.", "Retry the request. Investigate using the error code and technical IDs, without conversation content or personal data."),
        ),
    ]
    story.append(
        simple_table(
            [tr("HTTP и код", "HTTP and code"), tr("Что проверить", "What to check")],
            [[code, tr(*guidance)] for code, guidance in error_rows],
            [177, W - 177],
            [CELL_M, CELL],
        )
    )

    section(
        story,
        26,
        tr(
            "Ответьте своими словами, затем сравните с ответами в нижней части страницы.",
            "Answer in your own words, then compare with the answers below.",
        ),
        TEAL,
    )
    questions = [
        ("Почему модель не получает всю базу знаний?", "Why does the model not receive the entire knowledge base?"),
        ("Чем отличается customer_reply от upsell_recommendation? Кто отправляет ответ?", "How does customer_reply differ from upsell_recommendation? Who sends the reply?"),
        ("Что произойдёт с выдуманным upsell_product_id и подозрительной суммой?", "What happens to an invented upsell_product_id and a suspicious amount?"),
        ("Почему успешный тест с FakeLLM не доказывает качество настоящей модели?", "Why does a passing FakeLLM test not establish real model quality?"),
        ("Откуда берётся история amoCRM и что изменится после перезапуска сервера?", "Where does amoCRM history come from, and what changes after a server restart?"),
        ("Чем отличаются секрет вебхука, JWT виджета и токен REST API?", "How do the webhook secret, widget JWT and REST API token differ?"),
    ]
    for number, pair in enumerate(questions, 1):
        story += [p(f"{number}. {tr(*pair)}", QUESTION), Spacer(1, 6)]
    story += [Spacer(1, 10), p(tr("Ответы для самопроверки", "Self-check answers"), H2)]
    answers = [
        (
            "Поиск выбирает релевантные позиции и связанные товары. Меньше лишнего текста, а факты остаются в data/knowledge_base.json.",
            "Retrieval selects relevant entries and related items. This reduces irrelevant text while facts remain in data/knowledge_base.json.",
        ),
        (
            "Первое поле — черновик клиенту, второе — внутренняя подсказка менеджеру. Менеджер проверяет, редактирует, копирует и отправляет сам.",
            "The first is a customer-facing draft; the second is an internal manager hint. The manager reviews, edits, copies and sends it.",
        ),
        (
            "Guards проверяют товар по базе; неизвестная допродажа не допускается. Непроверенная сумма вызывает предупреждение: текст всё равно проверяет менеджер.",
            "Guards check the product against the KB and reject an unknown upsell. An unverified amount triggers a warning; the manager still reviews the text.",
        ),
        (
            "FakeLLM возвращает заданный тестом текст. Тест проверяет обработку ответа, а реальная LLM требует отдельных сценариев и оценки качества.",
            "FakeLLM returns text supplied by the test. The test checks answer handling; a real LLM needs separate scenarios and quality assessment.",
        ),
        (
            "Тексты приходят из вебхуков и хранятся в памяти одного процесса. После перезапуска кэш пуст; менеджер может вставить сообщение вручную.",
            "Texts arrive through webhooks and are kept in one process's memory. Restart clears the cache; the manager can paste a message manually.",
        ),
        (
            "Секрет защищает приём вебхука; одноразовый JWT подтверждает вызов виджета; REST-токен даёт серверу доступ к данным сделки и контакта.",
            "The secret protects webhook intake; the one-time JWT authenticates a widget call; the REST token gives the server access to lead and contact data.",
        ),
    ]
    for number, pair in enumerate(answers, 1):
        story += [p(f"<b>{number}.</b> {tr(*pair)}", BODY_S), Spacer(1, 5)]

    section(
        story,
        27,
        tr(
            "Источник чисел — docs/guide/verification.json; результаты имеют явно указанную область проверки.",
            "Numbers come from docs/guide/verification.json; each result has an explicit verification scope.",
        ),
        GREEN,
    )
    checked_at = escape(str(verification.get("checked_at", "—")))
    base_commit = escape(str(verification.get("base_commit", "—")))
    current_base = escape(str(verification.get("current_base_commit", base_commit)))
    tests = verification.get("tests", {})
    story += [
        p(
            tr(
                f"<b>Дата сводки:</b> {checked_at}. <b>Исходный прогон сервиса:</b> {base_commit}. "
                f"<b>Тесты:</b> {tests.get('passed', '—')} passed, {tests.get('failed', '—')} failed, "
                f"{tests.get('skipped', '—')} skipped; {tests.get('seconds', '—')} с.",
                f"<b>Summary date:</b> {checked_at}. <b>Original service run:</b> {base_commit}. "
                f"<b>Tests:</b> {tests.get('passed', '—')} passed, {tests.get('failed', '—')} failed, "
                f"{tests.get('skipped', '—')} skipped; {tests.get('seconds', '—')} s.",
            ),
            BODY_S,
        ),
        Spacer(1, 6),
        callout(
            tr(
                "<b>Граница доказательств.</b> Проверки сервера, UI, виджета и Docker ниже — "
                "зафиксированный локальный прогон с заглушкой LLM. Пересборка PDF сама по себе "
                "не повторяет этот прогон. Текущий прогон указан отдельно только в объёме "
                "действительно выполненных команд; настоящая LLM и настоящий аккаунт amoCRM "
                "требуют самостоятельной проверки.",
                "<b>Evidence boundary.</b> The server, UI, widget and Docker checks below record "
                "a local run with a stub LLM. Rebuilding the PDF does not repeat that run. "
                "The current run is listed separately only for commands actually executed; "
                "a real LLM and a real amoCRM account require separate verification.",
            ),
            AMBER,
            AMBER_L,
        ),
    ]

    # Current-run entries are optional so an older summary cannot imply a new run.
    current_run = verification.get("current_run", [])
    if isinstance(current_run, dict):
        current_run = current_run.get("checks", [])
    if current_run:
        story += [
            p(tr(f"Текущий прогон · {current_base} + рабочие изменения", f"Current run · {current_base} + working changes"), H2),
            simple_table(
                [tr("Проверка", "Check"), tr("Результат", "Result")],
                [[_localized(item["name"]), _localized(item["result"])] for item in current_run],
                [165, W - 165],
                [CELL_B, CELL],
            ),
        ]

    historical_date = escape(str(verification.get("historical_checked_at", checked_at)))
    story += [
        p(tr(f"Зафиксированные локальные проверки · {historical_date}", f"Recorded local checks · {historical_date}"), H2),
        simple_table(
            [tr("Проверка", "Check"), tr("Результат сводки", "Recorded result")],
            [[_localized(item["name"]), _localized(item["result"])] for item in verification.get("checks", [])],
            [165, W - 165],
            [CELL_B, CELL],
        ),
    ]
    if verification.get("http"):
        story += [
            Spacer(1, 5),
            p(
                tr(
                    "Полный перечень HTTP-сценариев с заглушкой хранится в verification.json и docs/VERIFICATION.md.",
                    "The full list of HTTP scenarios with the stub is in verification.json and docs/VERIFICATION.md.",
                ),
                SMALL,
            ),
        ]
    story.append(p(tr("Не проверено", "Not verified"), H2))
    for item in verification.get("not_verified", []):
        story += [p("• " + _localized(item), BODY_S), Spacer(1, 3)]
    story.append(
        p(
            tr(
                "Подробные свидетельства, ограничения и способ повторения — docs/VERIFICATION.md "
                "и docs/instructions/testing.md. Снимки ответов в других разделах руководства "
                "относятся к описанному локальному прогону с заглушкой.",
                "Detailed evidence, limitations and reproduction steps are in docs/VERIFICATION.md "
                "and docs/instructions/testing.md. Response snapshots elsewhere in the guide "
                "belong to the documented local run with a stub.",
            ),
            SMALL,
        )
    )
