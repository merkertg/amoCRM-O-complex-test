# Этап 05. Тесты и Docker: подробное руководство

Этот документ объясняет, как устроены автоматические тесты, почему им не
нужны ни сеть, ни ключи, какой тест отвечает за какое требование ТЗ, как
собирается Docker-образ и как проверить контейнер. Команды выполняются из
папки `amoCRM` с активированным `.venv`.

Короткая английская инструкция — [Testing and verification](instructions/testing.md).

> Цифры ниже — состояние на конец этапа 05 (95 тестов в шести файлах). На
> [этапе 08](STAGE_08.md) добавлены `tests/test_access.py` и
> `tests/test_evals.py`: сейчас тестов 124. Актуальная таблица — в
> [Testing and verification](instructions/testing.md).

Быстрые переходы: [запуск](#3-запуск-тестов) · [FakeLLM](#4-fakellm-модель-без-модели) ·
[MockTransport](#5-mocktransport-http-без-сети) · [фикстуры](#6-фикстуры-и-фабрика-приложения) ·
[требования → тесты](#7-какой-тест-отвечает-за-какое-требование) ·
[логи в тестах](#8-как-проверить-что-в-логах-нет-данных) · [Dockerfile](#9-dockerfile) ·
[Compose](#10-docker-compose) · [проверка контейнера](#11-проверка-контейнера) ·
[типичные ошибки](#12-типичные-ошибки) · [проверь себя](#13-проверь-себя).

## 1. Что получилось на этом этапе

| Файл | Тестов | Что проверяет |
| --- | --- | --- |
| `tests/test_knowledge_base.py` | 19 | Схема базы, перезагрузка, сломанный файл, стемминг, ранжирование |
| `tests/test_guards.py` | 24 | Injection и ложные срабатывания, очистка, ПДн, утечки, суммы, правила допродажи, разбор истории |
| `tests/test_assistant.py` | 13 | Весь pipeline: оба блока, нехватка фактов, неуместная допродажа, починка JSON, изоляция injection |
| `tests/test_llm_client.py` | 13 | Тело запроса, повторы, таймауты, 401/400 без повторов, битые ответы провайдера, секреты в логах |
| `tests/test_api.py` | 10 | REST API, коды ошибок, нет эха ввода, нет ПДн в логах, раздача UI и `/docs` |
| `tests/test_amocrm.py` | 16 | Вебхуки, дубли, токен виджета (6 видов плохих токенов), контекст, сбои API amoCRM |
| **Всего** | **95** | Время выполнения — около 0,3 с |

Плюс `Dockerfile`, `docker-compose.yml` и `.dockerignore`.

## 2. Карта файлов

```text
tests/
├── conftest.py              # FakeLLM, llm_reply(), make_settings(), make_client, run()
├── test_knowledge_base.py
├── test_guards.py
├── test_assistant.py
├── test_llm_client.py
├── test_api.py
└── test_amocrm.py
pyproject.toml               # [tool.pytest.ini_options]
Dockerfile                   # образ python:3.12-slim, пользователь appuser
docker-compose.yml           # сервис assistant, .env, ./data только для чтения
.dockerignore                # что не попадает в образ
```

## 3. Запуск тестов

```bash
pytest
```

```text
95 passed in 0.3s
```

Полезные варианты:

```bash
pytest tests/test_assistant.py -v     # один файл, имя каждого теста
pytest -k injection -v                # тесты, в имени которых есть «injection»
pytest -x                             # остановиться на первой ошибке
```

Настройки pytest — в `pyproject.toml`:

```toml
[tool.pytest.ini_options]
testpaths = ["tests"]
pythonpath = ["."]
addopts = "-q"
filterwarnings = [
    "error::DeprecationWarning:app.*",
    "ignore:Using `httpx` with `starlette.testclient`",
]
```

- `pythonpath = ["."]` — корень проекта в пути импорта, иначе тесты не
  найдут пакет `app`.
- Предупреждение об устаревании **в нашем коде** превращается в ошибку —
  так оно не останется незамеченным.
- Starlette 1.x предупреждает, что её `TestClient` лучше работает с
  `httpx2`. Приложение использует `httpx`, как требует ТЗ, поэтому
  предупреждение скрыто только для тестов.

## 4. FakeLLM: модель без модели

Настоящая модель медленная, платная и каждый раз отвечает по-разному.
Для тестов логики нужно обратное: мгновенно, бесплатно, предсказуемо.
`FakeLLM` в `tests/conftest.py` подходит под протокол `LLMClient`:

```python
class FakeLLM:
    model = "fake-model"

    def __init__(self, *responses):
        self.responses = list(responses)
        self.calls: list[list[dict[str, str]]] = []

    async def complete(self, messages):
        self.calls.append(messages)
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        if isinstance(response, dict):
            return json.dumps(response, ensure_ascii=False)
        return response
```

Что он умеет:

- отдавать заранее заданные ответы по очереди — словарь превращается в
  JSON, строка отдаётся как есть (можно проверить «модель ответила не JSON»);
- бросать исключение (`FakeLLM(LLMTimeoutError())`) — проверка обработки
  ошибок;
- запоминать **промпты** в `calls`. Это главное: тест проверяет не только
  результат, но и то, *что* ушло в модель — например, что телефона там нет.

`llm_reply(**overrides)` — готовый корректный ответ модели, в котором
тест меняет только нужные поля.

### Пример: телефон не уходит в модель

```python
def test_personal_data_is_masked_before_llm():
    llm = FakeLLM(llm_reply())
    message = "Перезвоните мне: +7 916 123-45-67, почта ivan.petrov@example.com"
    run(make_assistant(llm).suggest(ctx(message, client_name="Иван")))
    prompt = llm.last_user_prompt
    assert "123-45-67" not in prompt and "ivan.petrov@example.com" not in prompt
    assert "[телефон]" in prompt and "[email]" in prompt
```

### Почему run(), а не pytest-asyncio

`suggest()` асинхронный. Вместо отдельного плагина используется
`run = asyncio.run` — на одну зависимость меньше, а каждый тест получает
свой цикл событий.

## 5. MockTransport: HTTP без сети

LLM-клиент и клиент amoCRM работают через `httpx.AsyncClient`. HTTPX
позволяет подменить транспорт — слой, который реально отправляет байты в
сеть — функцией, которая сама формирует ответ:

```python
def make_client(handler, **kwargs):
    requests = []

    def wrapped(request):
        requests.append(request)
        return handler(request, len(requests))

    return OpenAICompatibleClient(transport=httpx.MockTransport(wrapped), ...), requests
```

Так проверяется весь путь запроса: URL, заголовки, тело, разбор ответа,
повторы. Например, «первый раз 502, второй раз успех»:

```python
client, requests = make_client(lambda req, n: httpx.Response(502) if n == 1 else ok_response())
assert run(client.complete(MESSAGES))
assert len(requests) == 2
```

Таймаут имитируется исключением: `raise httpx.ReadTimeout("timeout", request=req)`.
В тестах задержка между повторами `backoff_seconds=0`, поэтому они быстрые.

Тот же приём — для amoCRM: `amocrm_api()` в `tests/test_amocrm.py` отвечает
на `GET /api/v4/leads/1001` и `GET /api/v4/contacts/501` так, как это
описано в документации amoCRM, и проверяет заголовок `Authorization`.

## 6. Фикстуры и фабрика приложения

```python
def make_settings(**overrides) -> Settings:
    values = {"knowledge_base_path": KB_PATH, "llm_api_key": None,
              "amocrm_enabled": False, "cors_allow_origins": ""}
    values.update(overrides)
    return Settings(_env_file=None, **values)
```

`_env_file=None` — тесты **не читают** локальный `.env`: результат не
зависит от того, что настроено на компьютере разработчика.

Фикстура `make_client` создаёт `TestClient` для нового приложения:

```python
def factory(llm, amocrm_client=None, **overrides) -> TestClient:
    app = create_app(make_settings(**overrides), llm_client=llm, amocrm_client=amocrm_client)
    return TestClient(app)
```

`TestClient` вызывает приложение напрямую, без Uvicorn и сетевого порта,
но со всеми middleware, обработчиками ошибок и валидацией.

## 7. Какой тест отвечает за какое требование

| Требование ТЗ | Тесты |
| --- | --- |
| Ответ на основе базы знаний | `test_returns_both_blocks_with_valid_upsell` (факты в промпте), `test_search_finds_relevant_item` |
| Не выдумывать цены | `test_invented_price_is_flagged_for_manager`, `test_unverified_amounts`, `test_total_of_two_known_prices_is_accepted` |
| Недостаточно информации → уточняющий вопрос | `test_insufficient_information_leads_to_clarifying_question` |
| Допродажа только из базы | `test_upsell_of_unknown_product_is_blocked`, `test_upsell_outside_knowledge_base_is_disabled`, `test_upsell_product_resolved_by_name` |
| Допродажа неуместна — прямо указать | `test_upsell_not_applicable_for_complaint`, `test_not_applicable_upsell_clears_fields` |
| Внутреннее не попадает в ответ клиенту | `test_internal_recommendation_never_reaches_customer_reply`, `test_internal_leaks_are_removed_from_customer_reply`, `test_copied_upsell_reason_is_removed_from_customer_reply` |
| Ошибки API и таймауты | `test_timeout_is_retried_then_reported`, `test_server_error_is_retried`, `test_rate_limit_exhausts_retries`, `test_auth_error_is_not_retried`, `test_llm_timeout_maps_to_504` |
| Некорректные ответы модели | `test_invalid_json_is_repaired_with_second_call`, `test_missing_required_field_triggers_repair`, `test_invalid_json_twice_raises_error`, `test_malformed_provider_response` |
| Prompt injection | `test_prompt_injection_detected`, `test_regular_messages_are_not_flagged`, `test_prompt_injection_is_flagged_and_isolated`, `test_sanitize_neutralizes_prompt_tags_and_control_chars` |
| Не логировать ПДн и токены | `test_personal_data_is_not_logged`, `test_secrets_and_prompt_are_not_logged`, `test_validation_error_does_not_echo_input` |
| Учёт истории | `test_insufficient_information…` (история в промпте), `test_long_history_keeps_latest_messages`, `test_parse_history_text` |
| Интеграция с amoCRM | весь `tests/test_amocrm.py` |

## 8. Как проверить, что в логах нет данных

pytest умеет перехватывать логи фикстурой `caplog`:

```python
def test_personal_data_is_not_logged(make_client, caplog):
    caplog.set_level(logging.DEBUG)
    client = make_client(FakeLLM(llm_reply()))
    client.post("/api/v1/suggest",
                json={"message": "Мой номер +7 916 555-12-34, хочу Бриз 09", "client_name": "Евлампия"})
    assert "555-12-34" not in caplog.text
    assert "Евлампия" not in caplog.text
    assert "хочу Бриз 09" not in caplog.text
    assert "suggestion ready" in caplog.text
```

Последняя строка важна: она доказывает, что лог вообще пишется и тест
проверяет реальный вывод, а не пустоту.

## 9. Dockerfile

```dockerfile
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY app ./app
COPY data ./data

RUN useradd --create-home --uid 10001 appuser
USER appuser

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=3)"

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers"]
```

| Строка | Зачем |
| --- | --- |
| `python:3.12-slim` | Нужная версия Python, минимальный образ Debian |
| `PYTHONUNBUFFERED=1` | Логи сразу видны в `docker logs`, без буферизации |
| `PIP_NO_CACHE_DIR=1` | Кэш pip не раздувает образ |
| `COPY requirements.txt` **до** `COPY app` | Слой с зависимостями кэшируется: правка кода не переустанавливает библиотеки |
| `useradd` + `USER appuser` | Сервис работает не от root: при уязвимости у процесса меньше прав |
| `HEALTHCHECK` | Docker сам видит, жив ли сервис (`docker ps` → `healthy`); `curl` в slim-образе нет, поэтому проверка на Python |
| `--host 0.0.0.0` | Слушать все интерфейсы контейнера, иначе порт недоступен снаружи |
| Один процесс uvicorn | Кэш сообщений amoCRM живёт в памяти процесса |

`.dockerignore` не пускает в образ `.venv`, `.git`, `.env` (секреты!),
тесты, документацию и исходники виджета — они не нужны для работы.

## 10. docker-compose

```yaml
services:
  assistant:
    build: .
    image: amocrm-sales-assistant:latest
    env_file: .env
    ports:
      - "8000:8000"
    volumes:
      - ./data:/app/data:ro
    restart: unless-stopped
```

- `env_file: .env` — секреты передаются в контейнер при запуске и не
  попадают в образ.
- `./data:/app/data:ro` — база знаний с компьютера, только для чтения:
  правка файла видна сразу (этап 02), а контейнер не может её испортить.
- `restart: unless-stopped` — после сбоя или перезагрузки Docker сервис
  поднимется сам.

```bash
cp .env.example .env
docker compose up --build
```

## 11. Проверка контейнера

Фактическая проверка (20 октября 2026 года, Docker 29.8.2, macOS):

```bash
docker build -t amocrm-sales-assistant:test .
docker run -d --rm --name assistant-smoke -p 18000:8000 amocrm-sales-assistant:test
curl -s http://127.0.0.1:18000/health
```

```json
{"status":"ok","llm":{"model":"stub-model","api_key_set":true},"knowledge_base":{"path":"knowledge_base.json","products":10,"faq":7,...},"amocrm_enabled":false}
```

```bash
docker exec assistant-smoke id
```

```text
uid=10001(appuser) gid=10001(appuser) groups=10001(appuser)
```

Запрос `POST /api/v1/suggest` из контейнера к заглушке модели на
компьютере (`LLM_BASE_URL=http://host.docker.internal:9100/v1`) вернул
жалобу с `upsell_applicable: false` — сеть из контейнера к LLM работает.

```bash
docker stop assistant-smoke
```

## 12. Типичные ошибки

| Симптом | Причина | Что сделать |
| --- | --- | --- |
| `ModuleNotFoundError: No module named 'app'` в тестах | Запуск не из корня или без `pythonpath` | Запускать `pytest` из папки `amoCRM` |
| Тест зависит от моего `.env` | Создан `Settings()` без `_env_file=None` | Использовать `make_settings()` |
| `env file .env not found` в Compose | Нет `.env` | `cp .env.example .env` |
| Контейнер `unhealthy` | Сервис не стартовал: битая база знаний или ошибка настроек | `docker compose logs assistant` |
| Из контейнера не достучаться до Ollama | `localhost` внутри контейнера — сам контейнер | `LLM_BASE_URL=http://host.docker.internal:11434/v1` |
| Правка `.env` не применилась | Переменные читаются при старте контейнера | `docker compose up -d` пересоздаст контейнер |

## 13. Проверь себя

### Вопросы

1. Зачем `FakeLLM` запоминает промпты?
   *Ответ:* чтобы проверять, что именно ушло в модель: маскирование ПДн,
   изоляцию данных клиента, наличие фактов.
2. Почему тесты создают `Settings(_env_file=None)`?
   *Ответ:* чтобы результат не зависел от локального `.env`.
3. Чем `MockTransport` лучше подмены метода `post()`?
   *Ответ:* проверяется весь путь HTTPX — URL, заголовки, тело, разбор
   ответа, повторы; подменяется только сеть.
4. Почему `COPY requirements.txt` стоит раньше `COPY app`?
   *Ответ:* слой с зависимостями кэшируется и не пересобирается при
   каждой правке кода.
5. Почему `.env` в `.dockerignore`?
   *Ответ:* секреты не должны попасть в образ, который можно передать
   другим; они передаются при запуске через `env_file`.

### Самостоятельное задание

Напиши тест, который проверяет, что при `REDACT_PII_FOR_LLM=false` телефон
**доходит** до модели, а при `true` — нет. Используй `make_assistant(llm,
redact_pii_for_llm=False)` и `llm.last_user_prompt`.

## 14. Что дальше

[Этап 06](STAGE_06.md): что позволяет официальный API amoCRM и как
ассистент встроен в карточку сделки.
