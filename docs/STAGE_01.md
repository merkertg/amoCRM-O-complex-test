# Этап 01. Архитектура и структура проекта: подробное руководство

Этот документ объясняет, как устроен каркас сервиса: на какие модули он
разбит и почему, как модули связаны между собой, откуда берутся настройки,
как устроены ошибки и как всё это запустить. Команды выполняются в Terminal
из папки `amoCRM`, если не сказано иное.

Наглядная версия со схемами — в [PDF-руководстве](guide/amocrm-sales-assistant-guide.pdf).
Короткие английские инструкции без объяснений — в [docs/instructions/](instructions/):
[быстрый запуск](instructions/quickstart.md), [использование](instructions/usage.md),
[база знаний](instructions/knowledge-base.md), [amoCRM](instructions/amocrm.md),
[проверки](instructions/testing.md), [структура проекта](instructions/project-structure.md).

Быстрые переходы: [запуск](#3-как-запустить-на-mac) ·
[модули и зависимости](#4-модули-и-направление-зависимостей) ·
[DialogContext](#5-dialogcontext--единый-вход-бизнес-логики) ·
[настройки](#6-настройки-appconfigpy) ·
[ошибки](#7-ошибки-apperror) ·
[сборка приложения](#8-сборка-приложения-create_app) ·
[типичные ошибки](#9-типичные-ошибки) ·
[проверь себя](#10-проверь-себя).

## 1. Что получилось на этом этапе

Задача этапа по ТЗ — спроектировать минимальную архитектуру и структуру
проекта. Итог — один сервис FastAPI, в котором каждая часть отвечает за своё:

| Что | Где | Зачем |
| --- | --- | --- |
| HTTP-слой | `app/api/` | Принимает запросы, проверяет поля, отдаёт JSON и коды ошибок |
| Бизнес-логика | `app/core/` | Pipeline: контекст → поиск → промпт → LLM → проверки |
| База знаний | `app/knowledge/` | Загрузка JSON, валидация, поиск релевантных фактов |
| LLM-клиент | `app/llm/` | Запрос к любому OpenAI-совместимому API, повторы, ошибки |
| amoCRM | `app/integrations/amocrm/` | Вебхуки, кэш сообщений, REST API v4, проверка токена виджета |
| Модели данных | `app/schemas.py` | Запрос, ответ, `DialogContext`, структурированный ответ модели |
| Настройки | `app/config.py` | Все параметры — из переменных окружения и `.env` |
| Ошибки | `app/errors.py` | Единый формат ошибок с понятным менеджеру текстом |
| Сборка | `app/main.py` | `create_app()` соединяет части, подключает обработчики и UI |

Главная цепочка, которую нужно понять на этом этапе:

```text
Менеджер (UI или виджет amoCRM) → FastAPI (app/api) → DialogContext
   → SalesAssistant (app/core) → база знаний (app/knowledge) + LLM (app/llm)
   → SuggestResponse: ответ клиенту + подсказка менеджеру
```

Сознательно **нет**: агентов, очередей, микросервисов, векторной БД и
базы данных для переписки. ТЗ прямо просит не усложнять: база знаний
маленькая, запрос обрабатывается за секунды, менеджер ждёт ответ сразу.

## 2. Карта файлов

```text
amoCRM/
├── app/
│   ├── main.py                    # create_app(): сборка, обработчики ошибок, CORS, UI
│   ├── config.py                  # Settings: настройки из окружения и .env
│   ├── schemas.py                 # DialogMessage, DialogContext, SuggestRequest, Suggestion…
│   ├── errors.py                  # AppError: статус, код, сообщение менеджеру
│   ├── logging_setup.py           # логи без персональных данных (этап 04)
│   ├── api/                       # HTTP (этапы 04 и 06)
│   ├── core/                      # бизнес-логика (этап 03)
│   ├── knowledge/                 # база знаний и поиск (этап 02)
│   ├── llm/                       # LLM-клиент (этап 03)
│   ├── integrations/amocrm/       # amoCRM (этап 06)
│   └── static/                    # интерфейс менеджера (этап 04)
├── data/knowledge_base.json       # база знаний
├── amocrm_widget/                 # исходники виджета amoCRM
├── tests/                         # pytest (этап 05)
├── scripts/                       # сборка виджета и PDF-руководства
├── docs/                          # руководства этапов, инструкции, ADR, журнал, отчёт
├── Dockerfile, docker-compose.yml # контейнер (этап 05)
├── requirements.txt               # зависимости приложения с точными версиями
├── requirements-dev.txt           # + pytest
├── pyproject.toml                 # метаданные и настройки pytest
├── .env.example                   # образец настроек с комментариями
└── AGENTS.md                      # правила дальнейшей работы
```

## 3. Как запустить на Mac

### Шаг 1. Python 3.12

Системный `python3` на macOS — версии 3.9, а проекту нужен 3.12+
(тип `StrEnum`, синтаксис `X | None` и др.). Проверь:

```bash
python3 --version
```

Если версия ниже 3.12, поставь новую через uv (`uv python install 3.12`)
или Homebrew (`brew install python@3.12`).

### Шаг 2. Окружение и зависимости

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
```

`.venv` — отдельная папка с Python и библиотеками только для этого проекта.
`source .venv/bin/activate` включает её в текущей вкладке Terminal: в начале
строки появится `(.venv)`. Версии всех библиотек закреплены в
`requirements.txt` знаком `==`, поэтому у всех одинаковое окружение.

### Шаг 3. Настройки

```bash
cp .env.example .env
```

Открой `.env` и впиши `LLM_API_KEY`. Остальное можно оставить как есть.
Файл `.env` перечислен в `.gitignore` и в Git не попадает.

### Шаг 4. Сервер

```bash
uvicorn app.main:app --reload
```

```text
INFO     app.knowledge.repository: knowledge base loaded: products=10 faq=7
INFO:     Uvicorn running on http://127.0.0.1:8000 (Press CTRL+C to quit)
INFO:     Application startup complete.
```

`app.main:app` означает «модуль `app/main.py`, объект `app`». `--reload`
перезапускает сервер при изменении `.py`-файлов.

### Шаг 5. Проверка

```bash
curl -i http://127.0.0.1:8000/health
```

Фактический ответ (проверка 20 октября 2026 года):

```text
HTTP/1.1 200 OK
{"status":"ok","llm":{"model":"stub-model","api_key_set":true},
 "knowledge_base":{"path":"knowledge_base.json","products":10,"faq":7,
 "loaded_at":"2026-10-20T11:41:34.856924+00:00"},"amocrm_enabled":true}
```

Интерфейс менеджера: <http://127.0.0.1:8000>, документация API:
<http://127.0.0.1:8000/docs>. Остановить сервер — `Ctrl+C`.

## 4. Модули и направление зависимостей

Главное правило архитектуры — **зависимости направлены внутрь**:

```text
app/api ─────────────► app/core ─────► app/knowledge
   │                      │
   │                      └──────────► app/llm (только протокол LLMClient)
   └──► app/integrations/amocrm ──► app/core/dialog.py, app/schemas.py
```

- `app/core` ничего не знает про FastAPI, HTTP-запросы и amoCRM. На вход
  он получает `DialogContext`, на выход отдаёт `SuggestResponse`.
- `app/api` знает про FastAPI и вызывает `core`.
- Адаптер amoCRM превращает данные amoCRM в тот же `DialogContext`.

Зачем так строго:

1. **Тестируемость.** Бизнес-логику можно проверить, не поднимая сервер
   и не ходя в сеть: в тестах вместо LLM подставляется `FakeLLM`.
2. **Замена частей.** Поменять провайдера LLM, добавить Telegram вместо
   amoCRM или заменить поиск — значит заменить один модуль, а не
   переписывать pipeline.
3. **Требование ТЗ.** «Раздели бизнес-логику, API, доступ к базе знаний,
   LLM-клиент и amoCRM-интеграцию на независимые модули».

### Протокол вместо класса

`core` зависит не от конкретного `OpenAICompatibleClient`, а от протокола
`LLMClient` из `app/llm/client.py`:

```python
class LLMClient(Protocol):
    model: str

    async def complete(self, messages: list[dict[str, str]]) -> str: ...
```

Подходит любой объект, у которого есть атрибут `model` и асинхронный метод
`complete()`. Наследоваться от `LLMClient` не нужно — это «утиная
типизация» с подсказкой для читателя и IDE. Так `FakeLLM` в тестах
подменяет настоящий клиент без единой строчки наследования.

## 5. DialogContext — единый вход бизнес-логики

Переписку могут прислать два разных источника:

- менеджер в веб-интерфейсе: сообщение, история текстом, имя;
- виджет amoCRM: только ID сделки, а сообщение и история берутся из
  вебхуков и REST API.

Чтобы бизнес-логика не разбиралась с источниками, оба приводятся к одной
модели в `app/schemas.py`:

```python
class DialogContext(BaseModel):
    """Нормализованный контекст диалога — единый вход для бизнес-логики."""

    message: str
    history: list[DialogMessage] = Field(default_factory=list)
    client_name: str | None = None
    source: str = "manual"
```

`DialogMessage` — одна реплика: роль (`client`, `manager` или `unknown`)
и текст. Поле `source` нужно только для логов (`manual`,
`amocrm:webhook`, `amocrm:manual`): по нему видно, откуда пришёл запрос,
без записи самого текста.

## 6. Настройки: app/config.py

Все параметры — ключ LLM, модель, таймауты, пути, токены amoCRM — читаются
из переменных окружения. В коде нет ни одного секрета.

```python
class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        env_ignore_empty=True,  # пустая переменная = значение по умолчанию
        env_parse_none_str="none",  # LLM_TEMPERATURE=none -> параметр не отправляется
    )

    llm_base_url: str = "https://api.openai.com/v1"
    llm_api_key: SecretStr | None = None
    llm_model: str = "gpt-4.1-mini"
    llm_temperature: float | None = 0.2
    ...
```

Как это работает:

- **Приоритет:** переменная окружения → строка в `.env` → значение по
  умолчанию в классе. Имя переменной — имя поля в верхнем регистре:
  `llm_model` ↔ `LLM_MODEL`.
- **Проверка типов:** `LLM_TIMEOUT_SECONDS=abc` не превратится молча в 0 —
  Pydantic остановит запуск с понятной ошибкой.
- **`env_ignore_empty=True`:** в `.env.example` много строк вида
  `LLM_API_KEY=`. Пустое значение означает «использовать умолчание», а не
  «пустая строка».
- **`env_parse_none_str="none"`:** некоторые модели не принимают
  `temperature`. `LLM_TEMPERATURE=none` превращается в `None`, и клиент
  вообще не отправляет этот параметр.
- **`SecretStr`:** ключи хранятся в обёртке. `print(settings)` покажет
  `llm_api_key=SecretStr('**********')`; настоящее значение достаётся
  только явным `.get_secret_value()` в момент создания клиента.
- **`get_settings()` с `@lru_cache`:** настройки читаются один раз при
  запуске. После правки `.env` сервер нужно перезапустить.

Свойство `cors_origins` превращает строку `"https://a.amocrm.ru, https://b.amocrm.ru"`
в список — так удобнее задавать в `.env`, чем JSON-массивом.

### Эксперимент: temperature=none

```bash
LLM_TEMPERATURE=none python -c "from app.config import Settings; print(Settings().llm_temperature)"
```

```text
None
```

## 7. Ошибки: AppError

В сервисе много мест, где что-то может пойти не так: LLM не ответила,
база знаний сломана, токен виджета просрочен. Менеджеру нужен понятный
текст, программе — стабильный код, HTTP — правильный статус. Всё это
хранит базовый класс в `app/errors.py`:

```python
class AppError(Exception):
    status_code: int = 500
    code: str = "internal_error"
    user_message: str = "Внутренняя ошибка сервиса. Попробуйте ещё раз."
```

Каждая конкретная ошибка — подкласс с другими значениями:

| Класс | Модуль | Статус | Код |
| --- | --- | --- | --- |
| `LLMTimeoutError` | `app/llm/client.py` | 504 | `llm_timeout` |
| `LLMUnavailableError` | `app/llm/client.py` | 503 | `llm_unavailable` |
| `LLMAuthError` | `app/llm/client.py` | 503 | `llm_auth` |
| `LLMOutputError` | `app/core/assistant.py` | 502 | `llm_invalid_output` |
| `KnowledgeBaseError` | `app/knowledge/repository.py` | 503 | `knowledge_base_unavailable` |
| `WidgetAuthError` | `app/integrations/amocrm/auth.py` | 401 | `amocrm_widget_unauthorized` |
| `LeadNotFoundError` | `app/integrations/amocrm/adapter.py` | 404 | `amocrm_lead_not_found` |

Модули не знают про FastAPI — они просто бросают исключение. Один
обработчик в `create_app()` превращает любое `AppError` в ответ:

```json
{"error": {"code": "llm_unavailable", "message": "Сервис модели временно недоступен. Попробуйте ещё раз позже."}}
```

Интерфейс показывает `message`, а программа может ветвиться по `code`.

## 8. Сборка приложения: create_app()

`app/main.py` содержит фабрику, которая собирает все части:

```python
def create_app(
    settings: Settings | None = None,
    llm_client: LLMClient | None = None,
    amocrm_client: AmoCRMClient | None = None,
) -> FastAPI:
```

По шагам:

1. Настраивает логирование без персональных данных.
2. Создаёт `KnowledgeBaseRepository` и **сразу** загружает базу знаний.
   Если файл невалиден, запуск останавливается с понятной ошибкой
   (принцип fail fast: лучше не стартовать, чем отвечать клиентам без фактов).
3. Создаёт LLM-клиент из настроек — или берёт переданный (так тесты
   подставляют `FakeLLM`).
4. Создаёт кэш сообщений и, если `AMOCRM_ENABLED=true`, адаптер amoCRM.
5. Создаёт `FastAPI` с `lifespan`: при остановке сервера закрываются
   HTTP-соединения LLM и amoCRM.
6. Кладёт зависимости в `app.state` — обработчики берут их оттуда.
7. Подключает CORS (только если задан `CORS_ALLOW_ORIGINS`), обработчики
   ошибок, роутеры и статический интерфейс.

В конце модуля:

```python
app = create_app()
```

Этот объект запускает Uvicorn. Тесты вызывают `create_app(...)` сами
с тестовыми настройками и фейками — без подмены глобальных переменных
(monkeypatch).

## 9. Типичные ошибки

| Симптом | Причина | Что сделать |
| --- | --- | --- |
| `ERROR: No matching distribution found for fastapi==0.151.0` при `pip install` | `.venv` создан системным Python 3.9 | Удалить `.venv` и создать заново на 3.12: `python3.12 -m venv .venv` |
| `ModuleNotFoundError: No module named 'fastapi'` | Не активировано окружение | `source .venv/bin/activate` |
| `RuntimeError: База знаний не загружена: JSONDecodeError…` | Сломан `data/knowledge_base.json` при запуске | Исправить JSON; текст ошибки показывает строку и столбец |
| `[Errno 48] Address already in use` | Порт 8000 занят | `uvicorn app.main:app --port 8001` или `lsof -i :8000` |
| Изменения в `.env` не применяются | Настройки читаются один раз при старте | Перезапустить сервер |
| `/health` показывает `api_key_set: false` | В `.env` пустой `LLM_API_KEY` | Вписать ключ или настроить Ollama |

## 10. Проверь себя

### Вопросы

1. Почему `app/core` не импортирует FastAPI?
   *Ответ:* чтобы бизнес-логику можно было вызвать и протестировать без
   HTTP, а API и amoCRM были лишь «входами» в неё.
2. Зачем нужен `DialogContext`, если есть `SuggestRequest`?
   *Ответ:* `SuggestRequest` — формат HTTP-запроса из интерфейса. Виджет
   amoCRM присылает совсем другое (ID сделки). `DialogContext` — общий
   формат после нормализации для обоих источников.
3. Что произойдёт, если в `.env` написать `LLM_TIMEOUT_SECONDS=быстро`?
   *Ответ:* сервер не запустится: pydantic-settings не сможет превратить
   строку в число и покажет имя поля.
4. Почему в логах не появится ключ, даже если напечатать настройки?
   *Ответ:* поле имеет тип `SecretStr`, его `repr` — звёздочки.
5. Чем `create_app()` удобнее глобального объекта для тестов?
   *Ответ:* в фабрику можно передать свои настройки и фейковые клиенты,
   каждый тест получает свежее приложение.

### Самостоятельное задание

Добавь настройку `APP_TITLE` (по умолчанию «AI-ассистент менеджера amoCRM»)
и используй её как `title` в `FastAPI(...)`. Проверь, что заголовок на
`/docs` меняется после перезапуска с новой переменной окружения.

## 11. Что дальше

[Этап 02](STAGE_02.md): база знаний — формат JSON, проверка, перезагрузка
без перезапуска и поиск релевантных фактов.
