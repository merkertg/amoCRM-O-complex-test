"""Разделы 14–23: этапы 04–06 — API и интерфейс, тесты и Docker, интеграция с amoCRM."""

import json

from reportlab.platypus import KeepTogether, Spacer

from guide.diagrams import (
    adapter_flow,
    amocrm_sequence,
    jwt_checks,
    log_layers,
    ui_wireframe,
)
from guide.i18n import tr
from guide.layout import (
    AMBER,
    AMBER_L,
    BLUE,
    BLUE_L,
    CELL,
    CELL_B,
    CELL_M,
    GREEN,
    GREEN_L,
    H2,
    ORANGE,
    ORANGE_L,
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
from guide.sources import (
    DOCKER_OUTPUT,
    LOG_LINES,
    SUGGEST_RESPONSE,
    WEBHOOK_RESPONSES,
    WIDGET_CONTEXT,
    class_source,
    read_source,
    source_slice,
    widget_manifest,
    without_docstrings,
)
from guide.toc import section

TEST_PURPOSE = {
    "tests/test_knowledge_base.py": ("схема, перезагрузка, стемминг, ранжирование", "schema, reload, stemming, ranking"),
    "tests/test_guards.py": ("injection, очистка, ПДн, утечки, суммы, допродажа", "injection, sanitising, PII, leaks, amounts, upsell"),
    "tests/test_assistant.py": ("pipeline: оба блока, нехватка фактов, починка JSON", "pipeline: both blocks, missing facts, JSON repair"),
    "tests/test_llm_client.py": ("повторы, таймауты, 401/400, битые ответы, логи", "retries, timeouts, 401/400, broken answers, logs"),
    "tests/test_api.py": ("коды ошибок, нет эха ввода, нет ПДн в логах, UI", "error codes, no input echo, no PII in logs, UI"),
    "tests/test_amocrm.py": ("вебхуки, 6 видов плохих JWT, контекст, сбои API", "webhooks, 6 bad JWT kinds, context, API failures"),
    "tests/test_access.py": ("этап 08: вход менеджера, публичные пути, лимит и 429", "Stage 08: manager login, public paths, limit and 429"),
    "tests/test_evals.py": ("этап 08: наборы оценок, пороги поиска, проверки диалогов", "Stage 08: evaluation suites, retrieval thresholds, dialogue checks"),
}


def add_stages_delivery(story, facts, test_counts):
    """Добавить в story разделы 14–23."""

    # 14. REST API
    section(
        story,
        14,
        tr(
            "Этап 04: пять эндпоинтов, документация /docs и единый формат ошибок.",
            "Stage 04: five endpoints, /docs and one error format.",
        ),
        AMBER,
    )
    story += [
        simple_table(
            [tr("Метод", "Method"), tr("Путь", "Path"), tr("Назначение (из OpenAPI)", "Purpose (from OpenAPI)")],
            [[method, path, summary] for method, path, summary in facts["paths"]],
            [50, 160, W - 210],
            [CELL_B, CELL_M, CELL],
        ),
        Spacer(1, 4),
        p(
            tr(
                "Плюс / — интерфейс менеджера, /docs и /openapi.json — документация. Описания "
                "эндпоинтов в схеме на русском: так их видит менеджер в /docs.",
                "Plus / — the manager UI, /docs and /openapi.json — documentation. Endpoint "
                "summaries in the schema are in Russian: that is what managers see in /docs.",
            ),
            SMALL,
        ),
        p(tr("Запрос", "Request"), H2),
        code_block(
            "curl -s http://127.0.0.1:8000/api/v1/suggest \\\n"
            "  -H 'Content-Type: application/json' \\\n"
            "  -d '{\"message\": \"Хочу кондиционер в спальню 18 м². Сколько с установкой?\",\n"
            "       \"client_name\": \"Анна\"}'"
        ),
        p(tr("Фактический ответ (заглушка модели)", "Actual response (stub model)"), H2),
        code_block(SUGGEST_RESPONSE),
        Spacer(1, 6),
        callout(
            tr(
                "Ошибка валидации возвращает только имена полей: "
                "{\"error\": {\"code\": \"validation_error\", \"message\": \"Проверьте поля запроса: message\"}}. "
                "Стандартный ответ FastAPI содержит присланные значения — а там могут быть "
                "персональные данные.",
                "A validation error returns field names only: "
                "{\"error\": {\"code\": \"validation_error\", \"message\": \"Проверьте поля запроса: message\"}}. "
                "FastAPI's default response echoes the submitted values — which may contain "
                "personal data.",
            ),
            AMBER,
            AMBER_L,
        ),
    ]

    # 15. Интерфейс менеджера
    section(
        story,
        15,
        tr(
            "HTML, CSS и JavaScript без сборки: слева переписка, справа два блока.",
            "HTML, CSS and JavaScript without a build: conversation on the left, two blocks on the right.",
        ),
        AMBER,
    )
    story += [
        Diagram(300, ui_wireframe),
        Spacer(1, 10),
        simple_table(
            [tr("Что", "What"), tr("Как сделано", "How")],
            [
                [tr("Отправка", "Submit"), tr("fetch POST /api/v1/suggest; Ctrl+Enter; кнопка блокируется на время запроса", "fetch POST /api/v1/suggest; Ctrl+Enter; the button is disabled while waiting")],
                [tr("Таймаут", "Timeout"), tr("AbortController через 90 с — понятное сообщение вместо вечной загрузки", "AbortController after 90 s — a clear message instead of endless loading")],
                [tr("Безопасный вывод", "Safe output"), tr("только textContent и value, никогда innerHTML", "only textContent and value, never innerHTML")],
                [tr("Ответ клиенту", "Customer reply"), tr("редактируемое поле и «Копировать»", "editable field and «Copy»")],
                [tr("Подсказка", "Hint"), tr("оранжевый блок «Только для вас — не отправлять клиенту»", "orange block «For you only — do not send»")],
                [tr("Предупреждения", "Warnings"), tr("жёлтая плашка из meta.warnings", "yellow box from meta.warnings")],
                [tr("Вёрстка", "Layout"), tr("тёмная тема по prefers-color-scheme; колонки друг под другом уже 900 px", "dark theme via prefers-color-scheme; columns stack below 900 px")],
            ],
            [110, W - 110],
        ),
    ]

    # 16. Логи без ПДн
    section(
        story,
        16,
        tr(
            "Требование ТЗ — не логировать персональные данные и токены. Решение в три слоя.",
            "The specification forbids logging personal data and tokens. Three layers.",
        ),
        AMBER,
    )
    story += [
        Diagram(66, log_layers),
        p(tr("Фактические строки лога", "Actual log lines"), H2),
        code_block(LOG_LINES),
        Spacer(1, 8),
        cards(
            [
                ("request_id", tr("связывает строку лога с ответом API (meta.request_id) без текста запроса", "links a log line to the API response (meta.request_id) without the request text"), BLUE, BLUE_L),
                (tr("Ошибки", "Errors"), tr("непредвиденное исключение — тип и стек, без str(exc): там могут быть данные", "unexpected exception — type and stack, no str(exc): it may hold data"), ORANGE, ORANGE_L),
                ("httpx", tr("логгеры httpx и httpcore подняты до WARNING: на INFO они пишут полные URL", "httpx and httpcore loggers are at WARNING: at INFO they print full URLs"), TEAL, TEAL_L),
            ]
        ),
        callout(
            tr(
                "Тесты test_personal_data_is_not_logged и test_secrets_and_prompt_are_not_logged "
                "перехватывают логи (caplog) и проверяют, что телефона, имени, текста сообщения и "
                "ключа там нет, — а строка suggestion ready есть.",
                "Tests test_personal_data_is_not_logged and test_secrets_and_prompt_are_not_logged "
                "capture logs (caplog) and check that the phone, name, message text and key are "
                "absent — while the suggestion ready line is present.",
            ),
            GREEN,
            GREEN_L,
        ),
    ]

    # 17. Тесты
    total = sum(test_counts.values())
    section(
        story,
        17,
        tr(
            f"Этап 05: {total} тестов без сети и ключей — модель и HTTP подменяются.",
            f"Stage 05: {total} tests without network or keys — the model and HTTP are replaced.",
        ),
        GREEN,
    )
    story += [
        simple_table(
            [tr("Файл", "File"), tr("Тестов", "Tests"), tr("Что проверяет", "What it checks")],
            [
                [path, str(count), tr(*TEST_PURPOSE[path])]
                for path, count in sorted(test_counts.items(), key=lambda kv: -kv[1])
            ]
            + [[tr("Всего", "Total"), str(total), tr("собрано pytest при сборке PDF", "collected by pytest while building this PDF")]],
            [180, 50, W - 230],
            [CELL_M, CELL_B, CELL],
        ),
        p(tr("FakeLLM: модель без модели", "FakeLLM: a model without a model"), H2),
        code_block(without_docstrings(class_source("tests/conftest.py", "FakeLLM"))),
        Spacer(1, 6),
        cards(
            [
                ("FakeLLM", tr("ответы по очереди, исключения, запоминает промпты — тест видит, что ушло в модель", "queued answers, exceptions, remembers prompts — the test sees what went to the model"), VIOLET, VIOLET_L),
                ("MockTransport", tr("HTTPX без сети: URL, заголовки, тело, повторы — для LLM и amoCRM", "HTTPX without network: URL, headers, body, retries — for the LLM and amoCRM"), TEAL, TEAL_L),
                ("_env_file=None", tr("тесты не читают локальный .env — результат одинаков у всех", "tests ignore the local .env — same result for everyone"), BLUE, BLUE_L),
            ]
        ),
    ]

    # 18. Docker
    section(
        story,
        18,
        tr(
            "Образ python:3.12-slim, запуск не от root, проверка здоровья, база знаний снаружи.",
            "python:3.12-slim image, non-root user, health check, knowledge base mounted from the host.",
        ),
        GREEN,
    )
    dockerfile = "\n".join(line for line in read_source("Dockerfile").splitlines() if line and not line.startswith("#"))
    story += [
        code_block(dockerfile),
        Spacer(1, 8),
        simple_table(
            [tr("Решение", "Decision"), tr("Зачем", "Why")],
            [
                [tr("requirements.txt раньше кода", "requirements.txt before the code"), tr("слой зависимостей кэшируется: правка кода не переустанавливает библиотеки", "the dependency layer is cached: a code change does not reinstall libraries")],
                ["USER appuser (uid 10001)", tr("при уязвимости у процесса меньше прав", "a compromised process has fewer rights")],
                ["HEALTHCHECK", tr("Docker сам видит, жив ли сервис; curl в slim-образе нет — проверка на Python", "Docker sees whether the service is alive; slim has no curl — the check uses Python")],
                [tr("Один процесс uvicorn", "One uvicorn process"), tr("кэш сообщений amoCRM живёт в памяти процесса", "the amoCRM message cache lives in process memory")],
                ["./data:/app/data:ro", tr("база знаний правится без пересборки, контейнер её не испортит", "the KB is edited without a rebuild, the container cannot damage it")],
                [".dockerignore", tr(".env, .venv, тесты и документация не попадают в образ", ".env, .venv, tests and docs stay out of the image")],
            ],
            [160, W - 160],
        ),
        p(tr("Фактическая проверка контейнера", "Actual container check"), H2),
        code_block(DOCKER_OUTPUT),
    ]

    # 19. amoCRM: что даёт API
    section(
        story,
        19,
        tr(
            "Этап 06: ТЗ требует не придумывать методы — вот что есть в официальной документации.",
            "Stage 06: the specification forbids invented methods — here is what the official docs offer.",
        ),
        ORANGE,
    )
    story += [
        simple_table(
            [tr("Механизм", "Mechanism"), tr("Что даёт", "What it gives"), tr("Для нас", "For us")],
            [
                [tr("REST API v4", "REST API v4"), tr("сделки, контакты, примечания; OAuth 2.0 или долгосрочный токен", "leads, contacts, notes; OAuth 2.0 or a long-lived token"), tr("да: сделка и имя клиента", "yes: lead and customer name")],
                [tr("Вебхуки message / outgoing_message", "Webhooks message / outgoing_message"), tr("входящие и исходящие сообщения чатов <b>с текстом</b>", "incoming and outgoing chat messages <b>with text</b>"), tr("да: единственный источник текстов", "yes: the only source of texts")],
                [tr("API бесед /api/v4/talks", "Talks API /api/v4/talks"), tr("метаданные беседы: talk_id, chat_id, статус", "talk metadata: talk_id, chat_id, status"), tr("нет текстов", "no texts")],
                [tr("API событий /api/v4/events", "Events API /api/v4/events"), tr("incoming_chat_message: только message.id", "incoming_chat_message: message.id only"), tr("нет текстов", "no texts")],
                [tr("API чатов (amojo)", "Chats API (amojo)"), tr("история сообщений", "message history"), tr("нет: только собственный канал, HMAC-SHA1", "no: own channel only, HMAC-SHA1")],
                [tr("Примечания", "Notes"), "POST /api/v4/leads/{id}/notes", tr("можно сохранять подсказки — развитие", "could store hints — next step")],
                [tr("Виджеты Web SDK", "Web SDK widgets"), tr("JS в карточке (lcard), $authorizedAjax с одноразовым JWT", "JS in the card (lcard), $authorizedAjax with a one-time JWT"), tr("да: оба блока в amoCRM", "yes: both blocks in amoCRM")],
            ],
            [140, 200, W - 340],
        ),
        Spacer(1, 10),
        callout(
            tr(
                "<b>Вывод.</b> Прочитать переписку чата по ID сделки через REST API нельзя. Поэтому "
                "история собирается из вебхуков, а вызов делает менеджер из виджета в карточке "
                "сделки. Области внутри окна чата и способа вставить текст в поле ввода нет — "
                "менеджер копирует ответ. Это совпадает с требованием «отправляет только менеджер».",
                "<b>Conclusion.</b> REST API cannot read a chat by lead id. So the history is built "
                "from webhooks, and the manager calls the assistant from a widget in the lead card. "
                "There is no location inside the chat window and no way to fill the chat input — the "
                "manager copies the reply, which matches «only the manager sends».",
            ),
            ORANGE,
            ORANGE_L,
        ),
    ]

    # 20. amoCRM: схема
    section(
        story,
        20,
        tr(
            "Вебхук наполняет кэш заранее; генерация — только по кнопке менеджера.",
            "The webhook fills the cache in advance; generation happens only on the manager's click.",
        ),
        ORANGE,
    )
    story += [
        Diagram(260, amocrm_sequence),
        Spacer(1, 10),
        simple_table(
            ["#", tr("Шаг", "Step")],
            [
                ["1–2", tr("Клиент пишет в чат; amoCRM шлёт вебхук message[add]. Сервер кладёт текст в кэш и отвечает сразу: amoCRM ждёт не дольше 2 секунд", "The customer writes; amoCRM sends message[add]. The server caches the text and answers at once: amoCRM waits at most 2 seconds")],
                ["3", tr("Менеджер нажимает кнопку в карточке сделки; amoCRM добавляет X-Auth-Token", "The manager clicks in the lead card; amoCRM adds X-Auth-Token")],
                ["4", tr("Бэкенд проверяет JWT, берёт сделку и имя основного контакта через REST API v4", "The backend checks the JWT, loads the lead and the main contact's name via REST API v4")],
                ["5–6", tr("Тот же pipeline, что у /api/v1/suggest; виджет показывает оба блока", "The same pipeline as /api/v1/suggest; the widget shows both blocks")],
                ["7", tr("Менеджер копирует ответ в чат и отправляет сам", "The manager copies the reply into the chat and sends it")],
            ],
            [40, W - 40],
        ),
    ]

    # 21. Вебхуки и кэш
    section(
        story,
        21,
        tr(
            "Формат form-urlencoded, дедупликация, лимиты и срок жизни — без вызова LLM.",
            "form-urlencoded format, deduplication, limits and TTL — without calling the LLM.",
        ),
        ORANGE,
    )
    story += [
        code_block(
            "message[add][0][id]=m1\n"
            "message[add][0][text]=Здравствуйте! Подбираю кондиционер в спальню\n"
            "message[add][0][created_at]=1792496200\n"
            "message[add][0][element_type]=2          # 2 — " + tr("сделка", "lead") + "\n"
            "message[add][0][element_id]=4242\n"
            "message[add][0][contact_id]=77\n\n"
            'parse_nested_form([("message[add][0][text]", "Привет"), ("account[id]", "1")])\n'
            '→ {"message": {"add": {"0": {"text": "Привет"}}}, "account": {"id": "1"}}'
        ),
        Spacer(1, 8),
        simple_table(
            [tr("Свойство кэша", "Cache property"), tr("Как сделано", "How")],
            [
                [tr("Ключи", "Keys"), tr("lead:{id} и contact:{id} — сообщение без сделки найдётся по контакту", "lead:{id} and contact:{id} — a message without a lead is found by contact")],
                [tr("Дубли", "Duplicates"), tr("amoCRM повторяет доставку при сбое; тот же id игнорируется", "amoCRM redelivers on failure; the same id is ignored")],
                [tr("Размер", "Size"), tr("AMOCRM_HISTORY_LIMIT + 10 сообщений на ключ, до 5000 ключей", "AMOCRM_HISTORY_LIMIT + 10 messages per key, up to 5000 keys")],
                [tr("Срок жизни", "TTL"), tr("24 часа (AMOCRM_MESSAGE_TTL_HOURS) — ПДн не копятся", "24 hours (AMOCRM_MESSAGE_TTL_HOURS) — PII does not pile up")],
                [tr("Секрет", "Secret"), tr("?secret=… сравнивается hmac.compare_digest; в лог не попадает", "?secret=… is compared with hmac.compare_digest; never logged")],
                [tr("Хранение", "Storage"), tr("память процесса: один воркер, пусто после перезапуска; для реплик — Redis", "process memory: one worker, empty after restart; Redis for replicas")],
            ],
            [110, W - 110],
        ),
        p(tr("Фактические ответы: первое сообщение, повтор, неверный секрет", "Actual responses: first message, redelivery, wrong secret"), H2),
        code_block(WEBHOOK_RESPONSES),
    ]

    # 22. Токен виджета
    section(
        story,
        22,
        tr(
            "$authorizedAjax добавляет JWT, подписанный секретным ключом интеграции (HS256).",
            "$authorizedAjax adds a JWT signed with the integration secret key (HS256).",
        ),
        ORANGE,
    )
    story += [
        simple_table(
            [tr("Поле JWT", "JWT claim"), tr("Смысл (по документации amoCRM)", "Meaning (amoCRM docs)")],
            [
                ["iss", tr("адрес аккаунта", "account address")],
                ["aud", tr("адрес из redirect_uri интеграции", "address from the integration redirect_uri")],
                ["jti", tr("UUID токена", "token UUID")],
                ["iat, nbf, exp", tr("выпущен, действует с, действует до", "issued, valid from, valid until")],
                ["account_id, user_id", tr("аккаунт и пользователь", "account and user")],
                ["client_uuid", tr("ID интеграции", "integration id")],
            ],
            [140, W - 140],
            [CELL_M, CELL],
        ),
        p(tr("Четыре проверки", "Four checks"), H2),
        Diagram(76, jwt_checks),
        Spacer(1, 8),
        code_block(
            source_slice("app/integrations/amocrm/auth.py", "payload = jwt.decode(", "        )")
            + "\n    …\n"
            + source_slice("app/integrations/amocrm/auth.py", "if client_id and", "raise WidgetAuthError()")
            + "\n"
            + source_slice("app/integrations/amocrm/auth.py", "if account_base_url and", "raise WidgetAuthError()")
        ),
        Spacer(1, 6),
        callout(
            tr(
                "algorithms=[\"HS256\"] запрещает подмену алгоритма в заголовке токена (атака "
                "alg: none). Тест проверяет шесть плохих токенов: missing, not-jwt, expired, "
                "other-integration, other-account, wrong-signature — все получают 401.",
                "algorithms=[\"HS256\"] forbids swapping the algorithm in the token header (the "
                "alg: none attack). A test checks six bad tokens: missing, not-jwt, expired, "
                "other-integration, other-account, wrong-signature — all get 401.",
            ),
            ORANGE,
            ORANGE_L,
        ),
    ]

    # 23. Виджет и адаптер
    manifest = widget_manifest()
    compact = {
        "widget": {k: manifest["widget"][k] for k in ("version", "interface_version", "locale", "installation")},
        "locations": manifest["locations"],
        "settings": manifest["settings"],
    }
    section(
        story,
        23,
        tr(
            "Панель в карточке сделки и выбор текущего сообщения: поле виджета или кэш вебхуков.",
            "A panel in the lead card and how the current message is chosen: widget field or webhook cache.",
        ),
        ORANGE,
    )
    story += [
        code_block(json.dumps(compact, ensure_ascii=False)),
        Spacer(1, 6),
        simple_table(
            [tr("Колбэк script.js", "script.js callback"), tr("Что делает", "What it does")],
            [
                ["render", tr("в области lcard рисует панель через render_template()", "draws the panel in lcard via render_template()")],
                ["init", tr("подключает style.css из папки виджета", "loads style.css from the widget folder")],
                ["bind_actions", tr("кнопка: APP.data.current_card.id → $authorizedAjax → вывод через .text()/.val()", "button: APP.data.current_card.id → $authorizedAjax → output via .text()/.val()")],
                ["destroy", tr("снимает обработчики при уходе из карточки", "removes handlers when leaving the card")],
            ],
            [110, W - 110],
            [CELL_M, CELL],
        ),
        p(tr("Как адаптер выбирает сообщение", "How the adapter picks the message"), H2),
        Diagram(164, adapter_flow),
        Spacer(1, 8),
        KeepTogether(
            [
                p(tr("Фактический контекст после трёх вебхуков", "Actual context after three webhooks"), H2),
                code_block(WIDGET_CONTEXT),
            ]
        ),
        Spacer(1, 4),
        p(
            tr(
                "REST API возвращает контакт целиком; адаптер использует только имя, остальные поля в LLM не передаются. Если REST API "
                "недоступен, подсказка строится по переписке с предупреждением менеджеру.",
                "REST API returns the full contact; the adapter uses only the first name and does not pass other fields to the LLM. If "
                "REST API is down, the hint is built from the conversation with a warning.",
            ),
            SMALL,
        ),
    ]
