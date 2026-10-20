# Этап 04. FastAPI и интерфейс менеджера: подробное руководство

Этот документ объясняет HTTP-слой и веб-интерфейс:
- какие есть эндпоинты и как проверяются запросы;
- как ошибки превращаются в понятные ответы;
- что пишется в логи и чего там быть не должно;
- как устроена страница, с которой работает менеджер.

Команды выполняются из папки `amoCRM` с активированным `.venv`.

Короткие английские инструкции — [Quickstart](instructions/quickstart.md)
и [Using the assistant](instructions/usage.md).

Быстрые переходы: [запуск](#3-запуск-и-проверка) · [эндпоинты](#4-эндпоинты) ·
[проверка запроса](#5-проверка-запроса) · [ошибки](#6-обработчики-ошибок) ·
[документация API](#7-документация-api-docs) · [логи](#8-логи-без-персональных-данных) ·
[CORS](#9-cors) · [интерфейс](#10-интерфейс-менеджера) ·
[типичные ошибки](#11-типичные-ошибки) · [проверь себя](#12-проверь-себя).

## 1. Что получилось на этом этапе

| Что | Где | Зачем |
| --- | --- | --- |
| REST API | `app/api/routes.py` | `POST /api/v1/suggest`, `GET /health`, `GET /api/v1/knowledge-base` |
| Сборка и ошибки | `app/main.py` | Обработчики `AppError`, ошибок валидации и непредвиденных исключений |
| Логирование | `app/logging_setup.py` | Маскирование секретов и ПДн, access-лог без IP и query string |
| Интерфейс | `app/static/index.html`, `styles.css`, `app.js` | Страница менеджера без сборки и внешних библиотек |
| Документация API | `/docs`, `/openapi.json` | Генерируется FastAPI из моделей Pydantic |
| 10 тестов | `tests/test_api.py` | Ответы, коды ошибок, отсутствие ПДн в логах, раздача UI |

## 2. Карта файлов

```text
app/
├── main.py              # create_app(): CORS, обработчики, роутеры, /static, /
├── logging_setup.py     # setup_logging(), RedactingFilter, AccessLogFilter
├── api/
│   ├── routes.py        # suggest(), health(), knowledge_base(), ERROR_RESPONSES
│   └── amocrm.py        # эндпоинты amoCRM (этап 06)
└── static/
    ├── index.html       # разметка: форма слева, результат справа
    ├── styles.css       # цвета-токены, светлая и тёмная тема, адаптивная сетка
    └── app.js           # отправка формы, вывод результата, копирование, примеры
```

## 3. Запуск и проверка

```bash
uvicorn app.main:app --reload
```

Во второй вкладке:

```bash
curl -s http://127.0.0.1:8000/api/v1/suggest \
  -H 'Content-Type: application/json' \
  -d '{"message": "Хочу кондиционер в спальню 18 м². Сколько с установкой?", "client_name": "Анна"}'
```

Ответ содержит `suggestion` (два блока) и `meta`. Полный фактический пример —
в [руководстве этапа 03](STAGE_03.md#11-три-сценария-из-тз).

Без ключа LLM можно проверить всё, кроме качества ответа, заглушкой
OpenAI-совместимого API — см. [Testing](instructions/testing.md#manual-check-without-an-llm-key).

## 4. Эндпоинты

| Метод | Путь | Назначение |
| --- | --- | --- |
| `POST` | `/api/v1/suggest` | Ответ клиенту и подсказка по допродаже |
| `GET` | `/health` | Состояние: база знаний, настройки LLM, флаг amoCRM |
| `GET` | `/api/v1/knowledge-base` | Краткий список позиций и тем FAQ |
| `POST` | `/api/v1/amocrm/suggest` | Вызов из виджета amoCRM (этап 06) |
| `POST` | `/api/v1/amocrm/webhook` | Вебхуки amoCRM (этап 06) |
| `GET` | `/` | Интерфейс менеджера |
| `GET` | `/docs`, `/openapi.json` | Swagger UI и схема OpenAPI |

Префикс `/api/v1` оставляет место для будущей несовместимой версии API
(`/api/v2`) без поломки виджета, который уже установлен у клиентов.

### Разбор POST /api/v1/suggest

```python
@router.post("/api/v1/suggest", response_model=SuggestResponse, responses=ERROR_RESPONSES, ...)
async def suggest(body: SuggestRequest, request: Request) -> SuggestResponse:
    assistant: SalesAssistant = request.app.state.assistant
    history = body.history or (parse_history_text(body.history_text) if body.history_text else [])
    context = DialogContext(
        message=body.message,
        history=history,
        client_name=body.client_name,
        source="manual",
    )
    return await assistant.suggest(context)
```

Обработчик тонкий: он только переводит HTTP-запрос в `DialogContext` и
вызывает бизнес-логику. История принимается в двух видах: списком
`history` (для программ) или текстом `history_text` (для интерфейса,
куда менеджер вставляет переписку). Если пришли оба — используется список.

`async def` нужен потому, что внутри идёт сетевой запрос к LLM: пока
модель думает, сервер обслуживает другие запросы.

### /health

```bash
curl -s http://127.0.0.1:8000/health
```

```json
{"status":"ok","llm":{"model":"stub-model","api_key_set":true},
 "knowledge_base":{"path":"knowledge_base.json","products":10,"faq":7,"loaded_at":"2026-10-20T11:41:34.856924+00:00"},
 "amocrm_enabled":true}
```

Ключ не показывается — только факт, что он задан. Путь — только имя файла.
`status` становится `degraded`, если последняя правка базы знаний невалидна.

## 5. Проверка запроса

Модель `SuggestRequest` в `app/schemas.py` задаёт ограничения:

| Поле | Ограничение |
| --- | --- |
| `message` | обязательно, 1–4000 символов, не только пробелы |
| `history` | до 50 реплик, роль `client` / `manager` / `unknown`, текст до 4000 |
| `history_text` | до 12000 символов |
| `client_name` | до 100 символов |

FastAPI проверяет тело запроса до вызова обработчика. Фактический ответ на
сообщение из одних пробелов:

```text
HTTP/1.1 422 Unprocessable Entity
{"error":{"code":"validation_error","message":"Проверьте поля запроса: message"}}
```

Стандартный ответ FastAPI на ошибку валидации содержит поле `input` —
присланное значение. Мы заменили обработчик: в ответе **только имена полей**,
без значений, потому что там могут быть персональные данные. Тест
`test_validation_error_does_not_echo_input` проверяет, что имя клиента
из запроса не возвращается.

## 6. Обработчики ошибок

В `create_app()` три обработчика:

```python
@app.exception_handler(AppError)
async def app_error_handler(_: Request, exc: AppError) -> JSONResponse:
    return _error(exc.status_code, exc.code, exc.user_message)

@app.exception_handler(RequestValidationError)
async def validation_error_handler(_: Request, exc: RequestValidationError) -> JSONResponse:
    fields = sorted({".".join(str(p) for p in e["loc"] if p != "body") for e in exc.errors()})
    return _error(422, "validation_error", "Проверьте поля запроса: " + ", ".join(fields))

@app.exception_handler(Exception)
async def unhandled_error_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.error("unhandled %s on %s\n%s", type(exc).__name__, request.url.path,
                 "".join(traceback.format_tb(exc.__traceback__)))
    return _error(500, "internal_error", AppError.user_message)
```

Третий обработчик пишет в лог **тип** исключения и **стек вызовов**, но не
`str(exc)`: текст исключения может содержать данные клиента (например,
ошибка Pydantic включает исходное значение поля).

Все ошибки имеют одну форму `{"error": {"code", "message"}}`. Полная
таблица кодов — в [Using the assistant](instructions/usage.md#status-codes-you-may-see).

## 7. Документация API: /docs

FastAPI строит OpenAPI-схему из моделей и аннотаций. Чтобы `/docs` был
полезен без чтения кода:

- у моделей есть описания полей (`Field(description=...)`) и пример
  запроса (`json_schema_extra`);
- в `responses=ERROR_RESPONSES` перечислены коды 422, 502, 503, 504 с
  моделью `ErrorResponse`;
- эндпоинты сгруппированы тегами `assistant`, `service`, `knowledge base`, `amoCRM`.

Открой <http://127.0.0.1:8000/docs>, раскрой `POST /api/v1/suggest`, нажми
**Try it out** → **Execute** — запрос уйдёт с примером из схемы.

## 8. Логи без персональных данных

Требование ТЗ — «не логировать персональные данные и токены». Решение
в три слоя.

**1. Код не пишет данные.** Сообщения логов содержат только
идентификаторы, счётчики, длительности и коды. Фактическая строка после
генерации:

```text
INFO app.core.assistant: suggestion ready id=b1fe357926d0 source=manual latency_ms=636
  sources=breeze-09,breeze-12,dismantling,breeze-18,install-standard,wifi-module,service-plan,extended-warranty
  upsell=True clarification=False injection=- warnings=0
```

По `id` можно найти запрос в ответе API (`meta.request_id`), но текста
сообщения, имени и телефона здесь нет.

**2. RedactingFilter — страховка.** Если в будущем кто-то случайно напишет
в лог лишнее, фильтр на обработчике логов замаскирует `Bearer …`,
`token=…`, `api_key=…`, ключи `sk-…`, JWT (`eyJ…`), e-mail и телефоны.

**3. Access-лог uvicorn.** Стандартная строка содержит IP клиента и полный
путь с query string, а в URL вебхука amoCRM есть секрет
`?secret=…`. `AccessLogFilter` заменяет IP на `-` и отрезает query:

```text
INFO:     - - "POST /api/v1/amocrm/webhook HTTP/1.1" 200 OK
```

Логгеры `httpx` и `httpcore` подняты до `WARNING`: на `INFO` они пишут
полные URL каждого запроса.

Тесты `test_personal_data_is_not_logged` и
`test_secrets_and_prompt_are_not_logged` проверяют, что телефон, имя,
текст сообщения и ключ не появляются в логах.

## 9. CORS

Браузер не позволит странице `https://example.amocrm.ru` обратиться к
`https://assistant.example.com`, если сервер явно не разрешит. CORS
включается только при заданном `CORS_ALLOW_ORIGINS`:

```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type", "X-Auth-Token"],
)
```

Фактический ответ на предварительный запрос браузера (preflight) с
разрешённого origin:

```text
HTTP/1.1 200 OK
access-control-allow-methods: GET, POST, OPTIONS
access-control-allow-headers: Accept, Accept-Language, Content-Language, Content-Type, X-Auth-Token
access-control-allow-origin: http://127.0.0.1:9200
```

Собственному интерфейсу CORS не нужен: страница и API на одном адресе.

## 10. Интерфейс менеджера

Требование ТЗ: «простой и удобный для менеджера без технических знаний».
Поэтому страница — чистые HTML, CSS и JavaScript, без фреймворков и сборки.
Файлы раздаются самим FastAPI (`/static`), страница — по адресу `/`.

```text
┌──────────── Переписка ────────────┐ ┌──────────── Результат ───────────────────┐
│ Сообщение клиента *               │ │ ⚠ Проверьте перед отправкой (если есть)  │
│ История переписки (необязательно) │ │ ┃ Ответ клиенту          [Уточняющий вопрос]│
│ Имя клиента (необязательно)       │ │ ┃ <редактируемый текст>        [Копировать] │
│ [Сгенерировать рекомендации]      │ │ ┃ Подсказка менеджеру [Только для вас — …]  │
│ Примеры: покупка · мало информации│ │ ┃ Допродажа уместна / неуместна            │
│          жалоба · prompt injection│ │ ┃ Предложить · Почему · Пример фразы [Копир.]│
└───────────────────────────────────┘ │ ▸ Источники и технические детали          │
                                      └──────────────────────────────────────────┘
```

Как работает `app.js`:

1. **Отправка.** `fetch("/api/v1/suggest", {method: "POST", ...})` с телом
   `{message, history_text, client_name}`. Кнопка блокируется и меняет
   текст на «Генерирую…», показывается индикатор. `Ctrl+Enter` (или
   `Cmd+Enter`) — то же, что кнопка.
2. **Таймаут.** `AbortController` прерывает запрос через 90 секунд, менеджер
   видит понятное сообщение, а не вечную загрузку.
3. **Ошибки.** Если сервер вернул `{"error": {"message": ...}}`, этот текст
   показывается в красной плашке.
4. **Вывод.** Текст модели вставляется **только** через `textContent` и
   `value`, никогда через `innerHTML`. Даже если модель вернёт
   `<script>…</script>`, он отобразится как текст, а не выполнится.
5. **Ответ клиенту** — в редактируемом поле: менеджер может поправить
   текст перед копированием. Кнопка «Копировать» копирует текущее
   содержимое поля.
6. **Подсказка менеджеру** — оранжевый блок с пометкой «Только для вас —
   не отправлять клиенту». При неуместной допродаже показывается только
   причина.
7. **Предупреждения** из `meta.warnings` — жёлтая плашка над ответом.
8. **Копирование** — `navigator.clipboard`, а на `http://` (где он
   недоступен) — запасной вариант через временное поле.
9. **Примеры** — четыре кнопки заполняют форму сценариями из ТЗ.

Вёрстка: цвета заданы переменными (`--primary`, `--manager` и др.) и
переопределены в `@media (prefers-color-scheme: dark)` — тёмная тема
включается автоматически. На ширине меньше 900 px колонки встают друг под
друга; проверено на ширине телефона 375 px без горизонтальной прокрутки.

## 11. Типичные ошибки

| Симптом | Причина | Что сделать |
| --- | --- | --- |
| Страница открывается, кнопка ничего не делает | Пустое сообщение | Появится «Вставьте сообщение клиента» — заполнить поле |
| «Сервер не ответил за 90 секунд» | Медленная модель | Увеличить `LLM_TIMEOUT_SECONDS` или выбрать быструю модель |
| 422 «Проверьте поля запроса: message» | Пустое или слишком длинное сообщение | Сократить до 4000 символов |
| «Копировать» не копирует | Браузер запретил доступ к буферу | Выделить текст и `Cmd+C`; на `https://` или `localhost` работает |
| Виджет amoCRM получает ошибку CORS | Origin аккаунта не в `CORS_ALLOW_ORIGINS` | Добавить `https://<поддомен>.amocrm.ru`, перезапустить |
| В логе нет текстов запросов, сложно отлаживать | Так задумано | Искать по `request_id` из ответа API |

## 12. Проверь себя

### Вопросы

1. Почему обработчик ошибки валидации не возвращает присланные значения?
   *Ответ:* в них могут быть персональные данные клиента; достаточно имён полей.
2. Что увидит менеджер, если модель вернёт текст с HTML-тегами?
   *Ответ:* теги как обычный текст: вывод идёт через `textContent`/`value`.
3. Зачем убирать query string из access-лога?
   *Ответ:* в URL вебхука amoCRM передаётся секрет.
4. Почему CORS выключен по умолчанию?
   *Ответ:* собственный интерфейс работает с того же адреса; разрешать
   чужие origin нужно только для виджета amoCRM.
5. Чем `history` отличается от `history_text`?
   *Ответ:* первое — структурированный список для программ, второе — текст
   с префиксами для ручной вставки; список имеет приоритет.

### Самостоятельное задание

Добавь в интерфейс счётчик символов под полем «Сообщение клиента»
(«123 / 4000») и подсвети его красным при превышении. Проверь, что при
4001 символе сервер всё равно отвечает 422, — проверка на сервере остаётся
главной.

## 13. Что дальше

[Этап 05](STAGE_05.md): как устроены тесты, почему им не нужны сеть и
ключи, и как собрать и проверить Docker-образ.
