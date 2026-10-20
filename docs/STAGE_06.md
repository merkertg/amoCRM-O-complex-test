# Этап 06. Интеграция с amoCRM: подробное руководство

Этот документ объясняет, что позволяет официальный API amoCRM и почему
интеграция построена именно так. Дальше разобраны вебхуки сообщений и кэш,
проверка одноразового токена виджета, сборка контекста по сделке и
устройство самого виджета. В конце — как всё настроить и где ограничения.
Команды выполняются из папки `amoCRM` с активированным `.venv`.

Короткая английская инструкция по настройке — [amoCRM integration](instructions/amocrm.md).
Решение кратко — [ADR 0004](adr/0004-amocrm-widget-and-webhooks.md).

Быстрые переходы: [возможности API](#3-что-даёт-официальный-api) ·
[схема](#4-схема-интеграции) · [вебхуки](#5-вебхуки-и-кэш-сообщений) ·
[токен виджета](#6-одноразовый-токен-виджета) · [адаптер](#7-адаптер-контекст-по-сделке) ·
[REST API v4](#8-клиент-rest-api-v4) · [виджет](#9-виджет) ·
[настройка](#10-настройка-по-шагам) · [ограничения](#12-ограничения) ·
[типичные ошибки](#14-типичные-ошибки) · [проверь себя](#15-проверь-себя).

## 1. Что получилось на этом этапе

| Что | Где | Зачем |
| --- | --- | --- |
| Эндпоинты amoCRM | `app/api/amocrm.py` | `POST /api/v1/amocrm/suggest` (виджет), `POST /api/v1/amocrm/webhook` |
| Разбор вебхуков | `app/integrations/amocrm/webhooks.py` | `message[add][0][text]` → `StoredMessage` |
| Кэш сообщений | `app/integrations/amocrm/message_store.py` | Последние сообщения по сделке и контакту, TTL, дедупликация |
| Проверка токена | `app/integrations/amocrm/auth.py` | Подпись HS256, срок, ID интеграции, аккаунт |
| Клиент REST API v4 | `app/integrations/amocrm/client.py` | Сделка с контактами, имя контакта |
| Адаптер | `app/integrations/amocrm/adapter.py` | `DialogContext` по ID сделки |
| Виджет | `amocrm_widget/` | Панель в карточке сделки с обоими блоками |
| Сборка архива | `scripts/build_widget.py` | `dist/widget.zip` для загрузки в amoCRM |
| 16 тестов | `tests/test_amocrm.py` | Вебхуки, токены, контекст, сбои API |

## 2. Карта файлов

```text
app/api/amocrm.py                      # widget_suggest(), webhook()
app/integrations/amocrm/
├── webhooks.py                        # parse_nested_form(), extract_chat_messages()
├── message_store.py                   # StoredMessage, MessageStore
├── auth.py                            # verify_widget_token(), WidgetUser
├── client.py                          # AmoCRMClient: get_lead(), get_contact()
└── adapter.py                         # AmoCRMAdapter.build_context(), AmoContextInfo
amocrm_widget/
├── manifest.json                      # описание виджета, области, настройки
├── script.js                          # логика виджета (AMD-модуль)
├── style.css                          # стили панели
├── i18n/ru.json, i18n/en.json         # тексты для amoCRM
└── images/                            # логотипы обязательных размеров
scripts/build_widget.py                # проверка и упаковка в dist/widget.zip
```

## 3. Что даёт официальный API

ТЗ требует изучить официальную документацию и не придумывать методы.
Итог исследования (ссылки — в конце документа):

| Механизм | Что даёт | Подходит ли |
| --- | --- | --- |
| **REST API v4** (`/api/v4/...`), OAuth 2.0 или долгосрочный токен | Сделки, контакты, компании, примечания | ✅ данные сделки и имя клиента |
| **Вебхуки** `message[add]` и `outgoing_message[add]` | Входящее сообщение клиента и исходящее менеджера **с текстом**, контакт, сделка | ✅ единственный документированный способ получить тексты чатов любых каналов |
| **API бесед** `/api/v4/talks` | Метаданные беседы: `talk_id`, `chat_id`, `contact_id`, `entity_id`, статус | ⚠️ текстов нет |
| **API событий** `/api/v4/events`, типы `incoming_chat_message`, `outgoing_chat_message` | Факт сообщения; в `value_after` только `message.id` | ⚠️ текстов нет |
| **API чатов** (`amojo`, `/v2/origin/custom/{scope_id}/chats/{id}/history`) | История сообщений | ❌ только для **собственного** канала интеграции: регистрация канала, подпись HMAC-SHA1 |
| **Примечания** `/api/v4/leads/{id}/notes` | Внутренние заметки сделки | можно сохранять подсказки — не реализовано |
| **Web SDK — виджеты** | JS в интерфейсе amoCRM: области `lcard`, `ccard`, `card_sdk`, `everywhere` и др.; `this.$authorizedAjax()` с одноразовым JWT | ✅ показ обоих блоков внутри amoCRM |

**Главный вывод.** Документированного способа «прочитать переписку чата по
ID сделки» через REST API нет. Поэтому:

- история собирается из **вебхуков** с момента их подключения;
- вызов делает менеджер из **виджета** в карточке сделки;
- если вебхуков нет, менеджер вставляет текст в поле виджета вручную.

Ещё одно ограничение: среди областей виджета нет окна чата, и нет
документированного способа вставить текст в поле ввода сообщения. Менеджер
копирует ответ кнопкой — это совпадает с требованием «отправляет только
менеджер».

## 4. Схема интеграции

```text
Клиент ──сообщение──► amoCRM ──вебхук message[add] (текст, сделка, контакт)──► /api/v1/amocrm/webhook
                                                                                │ сохранить в кэш
                                                                                ▼ (без LLM, < 2 с)
Менеджер в карточке сделки                                                 MessageStore
   │ «Сгенерировать рекомендации»                                               ▲
   ▼                                                                            │
Виджет ──$authorizedAjax + X-Auth-Token (JWT)──► /api/v1/amocrm/suggest ──► AmoCRMAdapter
                                                   │ проверка JWT                │ GET /api/v4/leads/{id}?with=contacts
                                                   │                             │ GET /api/v4/contacts/{id}
                                                   ▼                             ▼
                                             SalesAssistant (этап 03) ◄── DialogContext
                                                   │
Виджет ◄──── ответ клиенту + подсказка менеджеру ◄─┘
   │ «Копировать ответ»
   ▼
Менеджер вставляет ответ в чат amoCRM и отправляет сам
```

## 5. Вебхуки и кэш сообщений

### Формат

amoCRM отправляет вебхуки как `application/x-www-form-urlencoded` с
вложенными ключами. Входящее сообщение:

```text
message[add][0][id]=m1
message[add][0][text]=Здравствуйте! Подбираю кондиционер в спальню
message[add][0][created_at]=1792496200
message[add][0][element_type]=2
message[add][0][element_id]=4242
message[add][0][contact_id]=77
message[add][0][talk_id]=…
message[add][0][chat_id]=…
```

Исходящее — то же под ключом `outgoing_message`. По документации
`element_id` / `element_type` — сущность CRM, к которой привязан чат.
Сделку обозначает код `2` (или `lead`).

### Разбор: webhooks.py

`parse_nested_form()` превращает плоские ключи во вложенный словарь:

```text
[("message[add][0][text]", "Привет"), ("account[id]", "1")]
→ {"message": {"add": {"0": {"text": "Привет"}}}, "account": {"id": "1"}}
```

`extract_chat_messages()` проходит по `message` (роль «клиент») и
`outgoing_message` (роль «менеджер»), достаёт `id`, текст, время, сделку и
контакт. Сообщение только с вложением сохраняется как «[вложение]», без
`id` или текста — пропускается.

Почему не `request.form()` FastAPI: для разбора форм Starlette требует
отдельную библиотеку `python-multipart`. Тело вебхука — простой
urlencoded-текст, его разбирает стандартный `urllib.parse.parse_qsl`.

### Кэш: message_store.py

| Свойство | Как сделано |
| --- | --- |
| Ключи | `lead:{id}` и `contact:{id}` — сообщение без сделки найдётся по контакту |
| Дубли | amoCRM повторяет вебхук при сбое; повтор с тем же `id` игнорируется |
| Размер | `deque(maxlen=…)`: не больше `AMOCRM_HISTORY_LIMIT + 10` сообщений на ключ и 5000 ключей |
| Срок жизни | `AMOCRM_MESSAGE_TTL_HOURS = 24`: старые сообщения отбрасываются при чтении |
| Потоки | `threading.Lock` |
| Хранение | В памяти процесса: после перезапуска пусто, нужен один процесс |

Персональные данные не копятся бесконечно: только последние сообщения и
только сутки.

### Эндпоинт: /api/v1/amocrm/webhook

```python
expected = request.app.state.settings.amocrm_webhook_secret
if expected is None or not hmac.compare_digest(secret.encode(), expected.get_secret_value().encode()):
    raise WebhookForbiddenError()
```

- Вебхуки amoCRM не подписаны, поэтому URL содержит секрет:
  `?secret=…`. Сравнение через `hmac.compare_digest` — за постоянное время,
  чтобы секрет нельзя было подобрать по времени ответа.
- LLM здесь не вызывается: amoCRM ждёт ответ не дольше **2 секунд**,
  повторяет доставку при ошибках, а после 100 ошибок за 2 часа отключает
  вебхук.

Фактические ответы:

```bash
curl -s -X POST "http://127.0.0.1:8000/api/v1/amocrm/webhook?secret=hook" \
  --data-urlencode "message[add][0][id]=m1" \
  --data-urlencode "message[add][0][text]=Здравствуйте! Подбираю кондиционер в спальню" \
  --data-urlencode "message[add][0][element_type]=2" \
  --data-urlencode "message[add][0][element_id]=4242"
```

```text
{"received":1,"stored":1}          # первое сообщение
{"received":1,"stored":0}          # повторная доставка того же id
HTTP/1.1 403 Forbidden             # неверный secret
{"error":{"code":"amocrm_webhook_forbidden","message":"Неверный секрет вебхука."}}
```

## 6. Одноразовый токен виджета

Виджет вызывает бэкенд из браузера менеджера. Как бэкенд узнает, что запрос
пришёл из amoCRM, а не от постороннего? В Web SDK есть метод
`this.$authorizedAjax()`: amoCRM добавляет к запросу заголовок
`X-Auth-Token` — **JWT**, подписанный секретным ключом интеграции
алгоритмом **HS256**. Ключ знают только amoCRM и владелец интеграции.

Поля токена по документации:

| Поле | Смысл |
| --- | --- |
| `iss` | Адрес аккаунта, например `https://example.amocrm.ru` |
| `aud` | Адрес из `redirect_uri` интеграции |
| `jti` | UUID токена |
| `iat`, `nbf`, `exp` | Выпущен, действует с, действует до (в примере документации — 30 минут) |
| `account_id`, `user_id` | Аккаунт и пользователь, от имени которого запрос |
| `client_uuid` | ID интеграции |
| `subdomain` | Поддомен аккаунта |

Проверка в `app/integrations/amocrm/auth.py`:

```python
payload = jwt.decode(
    token, secret, algorithms=["HS256"],
    options={"require": ["exp", "iat", "account_id", "user_id"], "verify_aud": False},
    leeway=leeway_seconds,
)
if client_id and payload.get("client_uuid") != client_id:
    raise WidgetAuthError()
if account_base_url and _host(str(payload.get("iss", ""))) != _host(account_base_url):
    raise WidgetAuthError()
```

1. Подпись проверяется секретом интеграции; `algorithms=["HS256"]` явно
   запрещает подмену алгоритма (атака `alg: none`).
2. `exp`/`nbf` — срок действия, `leeway=30` с — допуск на расхождение часов.
3. `client_uuid` должен совпасть с `AMOCRM_CLIENT_ID` — токен другой
   интеграции не подойдёт.
4. Хост `iss` должен совпасть с `AMOCRM_BASE_URL` — токен чужого аккаунта
   не подойдёт.

Тест `test_widget_rejects_invalid_tokens` проверяет шесть случаев:
`missing`, `not-jwt`, `expired`, `other-integration`, `other-account`,
`wrong-signature`. Фактический ответ без токена:

```text
HTTP/1.1 401 Unauthorized
{"error":{"code":"amocrm_widget_unauthorized","message":"Запрос не авторизован: откройте ассистента из интерфейса amoCRM."}}
```

## 7. Адаптер: контекст по сделке

`AmoCRMAdapter.build_context(lead_id, message, history_text)` в
`app/integrations/amocrm/adapter.py`:

1. **Данные CRM.** `GET /api/v4/leads/{id}?with=contacts` → список
   контактов сделки и основной (`is_main`). `GET /api/v4/contacts/{id}` →
   объект контакта целиком. Адаптер использует **только имя** (`first_name`
   или первое слово `name`). Телефоны, e-mail и остальные поля контакта
   не используются и в модель не уходят — это проверяет тест.
2. **Сделки нет** → 404 `amocrm_lead_not_found`.
3. **API недоступен** (сеть, 5xx, неверный токен) → работа продолжается
   только по переписке, менеджер видит «Не удалось загрузить данные сделки
   из amoCRM — подсказка построена только по переписке».
4. **История.** Сообщения из кэша по сделке; если их нет — по контактам
   сделки. Не больше `AMOCRM_HISTORY_LIMIT`.
5. **Текущее сообщение.**
   - Менеджер вставил текст в поле виджета → он и есть сообщение
     (`message_source: "manual"`). Если такой же текст — последнее
     сообщение в кэше, из истории он убирается, чтобы не дублироваться.
   - Поле пустое → берутся **последние подряд идущие сообщения клиента**
     (`message_source: "webhook"`). Клиенты часто пишут несколькими
     короткими сообщениями: «18 метров.» + «Сколько будет стоить с
     установкой?» — это одно обращение.
   - Сообщений клиента нет → 422 `amocrm_no_message`: «Вставьте текст
     сообщения клиента в поле ассистента».
   - Если после последнего сообщения клиента уже есть ответ менеджера,
     появляется предупреждение «На последнее сообщение клиента в чате уже
     есть ответ».

Фактический результат вызова виджета после трёх вебхуков (клиент →
менеджер → клиент):

```json
{
  "context": {
    "lead_id": 4242,
    "message_source": "webhook",
    "history_messages": 2,
    "crm_data_loaded": false
  },
  "upsell": "Wi-Fi модуль «Бриз Коннект»",
  "warnings": []
}
```

`crm_data_loaded: false` — в этом запуске не был задан токен REST API, и
адаптер работал только по кэшу; с токеном там `true`.

## 8. Клиент REST API v4

`AmoCRMClient` в `app/integrations/amocrm/client.py` — два документированных
метода, заголовок `Authorization: Bearer <token>`:

| Метод | Запрос |
| --- | --- |
| `get_lead(id)` | `GET /api/v4/leads/{id}?with=contacts` |
| `get_contact(id)` | `GET /api/v4/contacts/{id}` |

| Ответ amoCRM | Что делает клиент |
| --- | --- |
| 200 | Возвращает JSON |
| 204, 404 | `None` — «не найдено» |
| 401, 403 | `AmoCRMAuthError`: «amoCRM отклонил токен доступа» |
| Другие ошибки, сеть, не JSON | `AmoCRMError` |

Токен — долгосрочный токен приватной интеграции (от 1 дня до 5 лет, без
`refresh_token`) или access token OAuth 2.0.

## 9. Виджет

### manifest.json

```json
{
  "widget": {"name": "widget.name", "version": "1.0.0", "interface_version": 2,
             "locale": ["ru", "en"], "installation": true, ...},
  "locations": ["lcard-1", "settings"],
  "settings": {"backend_url": {"name": "settings.backend_url", "type": "text", "required": true}}
}
```

- `lcard-1` — карточка сделки, `-1` — блок в правой панели.
- `settings` — страница установки, где администратор вводит адрес сервера.
- Тексты (`widget.name` и др.) — ключи из `i18n/ru.json` и `i18n/en.json`.

### script.js

AMD-модуль, который загружает amoCRM. Обязательные колбэки `render`,
`init`, `bind_actions` возвращают `true`:

| Колбэк | Что делает |
| --- | --- |
| `render` | В области `lcard` рисует панель через `self.render_template()` |
| `init` | Подключает `style.css` из папки виджета (`self.params.path`) |
| `bind_actions` | Вешает обработчики кнопок с пространством имён `.aiSalesAssistant` |
| `destroy` | Снимает обработчики при уходе из карточки |

Что происходит по нажатию кнопки:

1. ID сделки — `APP.data.current_card.id`. Вне карточки `current_card`
   равно `false`, у несохранённой сделки ID равен `0` — виджет просит
   сначала сохранить сделку.
2. Адрес сервера — из настроек виджета (`self.get_settings().backend_url`).
3. `self.$authorizedAjax({url: …/api/v1/amocrm/suggest, method: "POST", …})` —
   amoCRM добавит `X-Auth-Token`.
4. Ответ выводится только через `.text()` и `.val()` — без вставки HTML.
5. «Копировать ответ» и «Копировать фразу» — в буфер обмена. Отправить
   что-либо в чат виджет не может: такого кода в нём нет.

### Сборка архива

```bash
python scripts/build_widget.py
```

```text
Готово: dist/widget.zip (версия 1.0.0)
```

Скрипт проверяет, что на месте `manifest.json`, `script.js`, `style.css`,
все логотипы и файлы локализации для каждого языка из `manifest.json`, что
JSON валиден. Файлы кладутся в корень архива, имя — `widget.zip`, как
требует документация.

## 10. Настройка по шагам

Подробно — в [amoCRM integration](instructions/amocrm.md). Кратко:

1. Развернуть бэкенд по **HTTPS** (для теста — туннель cloudflared/ngrok).
2. В amoCRM: **амоМаркет** → **Создать интеграцию**. На вкладке **Ключи**
   взять ID интеграции, секретный ключ и сгенерировать долгосрочный токен.
3. `python scripts/build_widget.py` → загрузить `dist/widget.zip` в
   интеграцию (**режим редактирования**), установить виджет, указать адрес
   сервера.
4. **амоМаркет** → **WEB HOOKS**: адрес
   `https://…/api/v1/amocrm/webhook?secret=…`, события сообщений в чатах.
5. В `.env`: `AMOCRM_ENABLED=true`, адрес аккаунта, токен, ID и секрет
   интеграции, секрет вебхука, `CORS_ALLOW_ORIGINS=https://<поддомен>.amocrm.ru`.

## 11. Как это проверено

На настоящем аккаунте amoCRM интеграция **не проверялась**. Проверено:

- 16 тестов: разбор вебхуков, дубли, 6 видов плохих токенов, контекст из
  вебхуков, приоритет ручного ввода, недоступный API, несуществующая сделка;
- страница-имитация карточки сделки: настоящий `script.js`, заглушки
  `APP.data.current_card`, `render_template` и `$authorizedAjax`, который
  добавляет подписанный JWT. Страница работала с адреса
  `http://127.0.0.1:9200`, бэкенд — с `:8010`, то есть запрос был
  кросс-доменным и прошёл CORS. Виджет показал оба блока, ошибок в консоли
  браузера не было;
- в логе сервера нет текстов сообщений и секрета вебхука.

## 12. Ограничения

1. **Нет области внутри окна чата** и документированного способа вставить
   текст в поле ввода — ответ копируется вручную.
2. **История только из вебхуков**, начиная с момента подписки. Старые
   сообщения можно вставить в поле виджета.
3. **Кэш в памяти**: один процесс, очищается при перезапуске. Для
   нескольких реплик — Redis с тем же интерфейсом (`add`, `for_lead`,
   `for_contact`).
4. **Вебхуки не подписаны** — защита секретом в URL и HTTPS.
5. **Названия событий в интерфейсе** вебхуков могут отличаться от
   документации или быть недоступны на тарифе.
6. **Вложения** не анализируются.
7. **Kommo** (международная версия) — тот же API на домене `kommo.com`.

## 13. Развитие

- Кнопка «Сохранить подсказку в примечание» — `POST /api/v4/leads/{id}/notes`
  с `note_type: "common"` (примечания внутренние).
- Вкладка в карточке через `card_sdk` вместо блока в правой панели.
- Собственный канал через API чатов — для полной истории.
- Redis для кэша.

## 14. Типичные ошибки

| Симптом | Причина | Что сделать |
| --- | --- | --- |
| «Сервер ассистента недоступен: проверьте адрес…» | Неверный `backend_url`, HTTP вместо HTTPS или CORS | Проверить адрес в настройках виджета и `CORS_ALLOW_ORIGINS` |
| 401 `amocrm_widget_unauthorized` | Неверный `AMOCRM_CLIENT_SECRET`/`AMOCRM_CLIENT_ID` или `AMOCRM_BASE_URL` другого аккаунта | Сверить значения с вкладкой «Ключи» |
| 503 `amocrm_disabled` | `AMOCRM_ENABLED=false` | Включить и перезапустить |
| 422 `amocrm_no_message` | Вебхуки не настроены или сообщения старше TTL | Вставить текст в поле виджета; подключить вебхуки |
| 403 на вебхук | `secret` в URL не совпадает с `AMOCRM_WEBHOOK_SECRET` | Исправить URL вебхука |
| «Сначала сохраните сделку» | Новая карточка, ID ещё `0` | Сохранить сделку |
| Предупреждение «Не удалось загрузить данные сделки» | Нет или просрочен `AMOCRM_ACCESS_TOKEN` | Сгенерировать новый долгосрочный токен |
| amoCRM не принимает архив | Ошибка в `manifest.json` или структуре | Собирать только `scripts/build_widget.py`, читать текст ошибки amoCRM |

## 15. Проверь себя

### Вопросы

1. Почему историю переписки нельзя просто запросить через REST API?
   *Ответ:* API бесед и событий не отдают текстов, API чатов работает
   только для собственного канала; тексты есть только в вебхуках.
2. Почему вебхук не вызывает LLM сразу?
   *Ответ:* amoCRM ждёт ответ до 2 секунд и отключает вебхук после
   множества ошибок; генерация длится дольше и нужна только по запросу
   менеджера.
3. Что защищает `algorithms=["HS256"]` в `jwt.decode`?
   *Ответ:* от подмены алгоритма в заголовке токена, например `none`.
4. Почему из контакта берётся только имя?
   *Ответ:* минимизация персональных данных: для ответа нужно только
   обращение по имени.
5. Как виджет понимает, в какой он сделке?
   *Ответ:* `APP.data.current_card.id`; вне карточки `current_card` —
   `false`, у новой сделки ID `0`.
6. Почему два сообщения клиента подряд объединяются?
   *Ответ:* клиенты часто разбивают один вопрос на несколько сообщений.

### Самостоятельное задание

Реализуй метод `AmoCRMClient.add_note(lead_id, text)` —
`POST /api/v4/leads/{lead_id}/notes` с телом
`[{"note_type": "common", "params": {"text": text}}]` — и эндпоинт
`POST /api/v1/amocrm/note`, который сохраняет подсказку менеджеру в
примечание сделки (с той же проверкой JWT). Напиши тест на
`MockTransport`, проверяющий URL и тело запроса.

## 16. Источники

- [Формат вебхуков](https://www.amocrm.ru/developers/content/crm_platform/webhooks-format) — `message`, `outgoing_message`, тайм-аут 2 с, повторы, отключение.
- [API бесед](https://www.amocrm.ru/developers/content/crm_platform/talks-api) — только метаданные беседы.
- [События и примечания](https://www.amocrm.ru/developers/content/crm_platform/events-and-notes) — `incoming_chat_message`, `outgoing_chat_message`, примечания.
- [API чатов](https://www.amocrm.ru/developers/content/chats/chat-api-reference) — история для собственного канала, подпись запросов.
- [Механика виджетов](https://www.amocrm.ru/developers/content/web_sdk/mechanics) — колбэки, `render_template`, `crm_post`, `$authorizedAjax`.
- [Структура виджета](https://www.amocrm.ru/developers/content/integrations/structure) — `manifest.json`, `i18n`, логотипы.
- [Загрузка виджета](https://www.amocrm.ru/developers/content/integrations/upload) — `widget.zip`, режим редактирования.
- [Переменные окружения Web SDK](https://www.amocrm.ru/developers/content/web_sdk/env_variables) — `APP.data.current_card`, `APP.getBaseEntity()`.
- [Одноразовые токены](https://www.amocrm.ru/developers/content/oauth/disposable-tokens) — JWT HS256, поля.
- [Пошаговая авторизация](https://www.amocrm.ru/developers/content/oauth/step-by-step) — создание интеграции, ключи, долгосрочные токены.
- [Области подключения виджетов](https://developers.kommo.com/docs/widget-locations) — `lcard`, `card_sdk`, `everywhere` (документация Kommo, общая платформа).
