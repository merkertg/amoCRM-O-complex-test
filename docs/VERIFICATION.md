# Проверка проекта

Дата последней проверки: **20 октября 2026 года**, этапы 01–06,
код — коммит `df465b3`.
Здесь записаны только фактически выполненные проверки. Проверенное локально
и не проверенное (настоящая LLM, настоящий аккаунт amoCRM, CI) разделено.
Машиночитаемая сводка для PDF — [verification.json](guide/verification.json).

Окружение: macOS (Apple Silicon), Python 3.12.15, Docker 29.8.2.

## 1. Что проверяется

| Область | Как проверяем | Где смотреть |
| --- | --- | --- |
| Бизнес-логика | pytest с `FakeLLM`: оба блока, нехватка фактов, допродажа, починка JSON | `tests/test_assistant.py` |
| Защита | pytest: injection и ложные срабатывания, очистка, ПДн, утечки, суммы, правила допродажи | `tests/test_guards.py` |
| База знаний и поиск | pytest: схема, перезагрузка, сломанный файл, ранжирование | `tests/test_knowledge_base.py` |
| LLM-клиент | pytest с `httpx.MockTransport`: повторы, таймауты, 401/400, битые ответы, секреты в логах | `tests/test_llm_client.py` |
| REST API | pytest с `TestClient`: коды ошибок, нет эха ввода, нет ПДн в логах, UI и `/docs` | `tests/test_api.py` |
| amoCRM | pytest: вебхуки, дубли, 6 видов плохих JWT, контекст, сбои API | `tests/test_amocrm.py` |
| Настоящий сервер | Uvicorn + заглушка OpenAI-совместимого API + curl | раздел 3 |
| Интерфейс | Браузер: 4 сценария, ширина 375 px, отсутствие горизонтальной прокрутки | раздел 3 |
| Виджет | Страница-имитация карточки сделки с настоящим `script.js` и подписанным JWT, другой origin | раздел 3 |
| Логи | Чтение лога сервера после всех запросов | раздел 3 |
| Docker | `docker build`, запуск, `/health`, `id`, запрос к LLM из контейнера | раздел 3 |
| Архив виджета | `scripts/build_widget.py`, `unzip -l`, синтаксис `script.js` в Node | раздел 3 |
| PDF | Сборка на русском и английском, рендер всех страниц, визуальная проверка | [руководство и его исходник](guide/README.md) |

## 2. Исправления, найденные при проверке

- **Кавычки в названии позиции.** `find_product_by_name()` обрезал только
  крайние кавычки, и «Wi-Fi модуль «Бриз Коннект»» не находился. Теперь
  кавычки удаляются целиком при сравнении (тест
  `test_upsell_product_resolved_by_name`).
- **«18 м²» находило «Бриз 18».** Сквозная проверка показала, что в
  вопросе о спальне на 18 м² первой шла модель на 50 м². Число после слова
  теперь склеивается с ним (`бриз#18`), голые номера убраны из `keywords`.
- **Ложное предупреждение о сумме «итого».** Сумма двух известных цен
  (42 900 + 9 900 = 52 800) помечалась как непроверенная. Теперь такие
  суммы принимаются; проценты — нет.
- **Жалоба не находила раздел о ремонте.** «течь», «капает» не совпадали с
  «течет» после стемминга — добавлены ключевые слова.
- **Маскирование e-mail съедало точку.** «anna@mail.ru.» → «[email]» без
  точки в конце предложения. Регулярное выражение домена исправлено в
  `guards.py` и `logging_setup.py`.
- **Разбор формы вебхука.** `request.form()` в Starlette требует пакет
  `python-multipart`. Тело вебхука разбирается стандартным
  `urllib.parse.parse_qsl` — без лишней зависимости.
- **Python 3.9.** На системном Python `pip install` падает с
  `No matching distribution found for fastapi==0.151.0` — в документации
  указано создавать `.venv` на 3.12.
- **Идентификаторы тестов.** Параметры теста токенов показывались как
  длинные JWT-строки; заданы понятные имена (`expired`, `wrong-signature`…).

## 3. Результаты

### Автотесты

```text
$ pytest
95 passed in 0.3s
```

| Файл | Тестов |
| --- | --- |
| `tests/test_knowledge_base.py` | 19 |
| `tests/test_guards.py` | 24 |
| `tests/test_assistant.py` | 13 |
| `tests/test_llm_client.py` | 13 |
| `tests/test_api.py` | 10 |
| `tests/test_amocrm.py` | 16 |

### Настоящий сервер с заглушкой модели

Uvicorn с `AMOCRM_ENABLED=true` и заглушкой OpenAI-совместимого API на
порту 9100.

| Запрос | Статус | Результат |
| --- | --- | --- |
| `GET /health` | 200 | `status: ok`, 10 позиций, 7 FAQ |
| `POST /api/v1/suggest` — покупка, «18 м²» | 200 | Первый источник `breeze-09`, допродажа `wifi-module`, предупреждений нет |
| `POST /api/v1/suggest` — жалоба | 200 | Первый источник `faq-repair`, `upsell_applicable: false` |
| `POST /api/v1/suggest` — injection | 200 | `injection_suspected: true`, предупреждение менеджеру |
| `POST /api/v1/suggest` — сообщение из пробелов | 422 | `validation_error`, имя клиента не возвращается |
| `POST /api/v1/amocrm/webhook` | 200 | `stored: 1`; повтор того же `id` — `stored: 0` |
| `POST /api/v1/amocrm/webhook?secret=wrong` | 403 | `amocrm_webhook_forbidden` |
| `POST /api/v1/amocrm/suggest` с JWT | 200 | `message_source: webhook`, `history_messages: 2` |
| `POST /api/v1/amocrm/suggest` без токена | 401 | `amocrm_widget_unauthorized` |
| `POST /api/v1/amocrm/suggest`, сделка без сообщений | 422 | `amocrm_no_message` |
| `OPTIONS /api/v1/amocrm/suggest` с разрешённого origin | 200 | `access-control-allow-headers` содержит `X-Auth-Token` |
| `POST /api/v1/suggest`, модель остановлена | 503 | `llm_unavailable` после 3 попыток (0,5 с и 1 с между ними) |

### Интерфейс и виджет

- Интерфейс: сценарии «покупка» и «prompt injection» отрисованы, блок
  подсказки помечен «Только для вас — не отправлять клиенту»; на ширине
  375 px `scrollWidth = clientWidth = 375`.
- Виджет: страница на `http://127.0.0.1:9200` загрузила настоящий
  `amocrm_widget/script.js`, по кнопке вызвала бэкенд на `:8010` через
  `$authorizedAjax` с подписанным JWT; оба блока показаны, ошибок в консоли
  нет.
- `scripts/build_widget.py` собрал `dist/widget.zip` (10 файлов);
  `script.js` загружается в Node с заглушкой `define` и отдаёт колбэки
  `render, init, bind_actions, settings, onSave, destroy`.

### Логи

После всех запросов в логе сервера нет текстов сообщений, имён, телефонов,
IP-адресов и `secret=` из URL вебхука. Пример строки:

```text
INFO app.core.assistant: suggestion ready id=b1fe357926d0 source=manual latency_ms=636 sources=breeze-09,... upsell=True clarification=False injection=- warnings=0
INFO:     - - "POST /api/v1/amocrm/webhook HTTP/1.1" 200 OK
```

### Docker

| Команда | Результат |
| --- | --- |
| `docker build -t amocrm-sales-assistant:test .` | Успешно |
| `docker run … -p 18000:8000` + `curl /health` | `status: ok` |
| `docker exec … id` | `uid=10001(appuser)` |
| `POST /api/v1/suggest` из контейнера к заглушке на `host.docker.internal` | 200, жалоба → `upsell_applicable: false` |

## 4. Что не проверено

| Что | Почему | Как проверить |
| --- | --- | --- |
| Качество ответов настоящей LLM | Не было ключа API | Задать `LLM_API_KEY`, пройти 4 сценария в интерфейсе и сценарии из руководства этапа 03 |
| Настоящий аккаунт amoCRM | Нет доступа к аккаунту | Шаги из [amoCRM integration](instructions/amocrm.md) |
| Названия событий вебхуков в интерфейсе amoCRM | Документация описывает формат, но не названия в списке | При настройке вебхука |
| CI | Его нет | Добавить GitHub Actions с pytest |
| Linux и Windows на хосте | Проверялся только macOS | Образ Docker основан на Linux и собирается |

## 5. Как повторить

```bash
source .venv/bin/activate
pytest
```

Ручная проверка без ключа, Docker и архив виджета — в
[Testing and verification](instructions/testing.md).
