# amoCRM integration

[← README](../../README.md) · [All documentation](../../README.md#documentation)

Connect the assistant to an amoCRM account: a private integration, the widget in the lead card, chat message webhooks and server settings. What the official API allows, why the integration is built this way and its limits are explained in Russian in the [Stage 06](../STAGE_06.md) guide.

## How it works

1. A customer writes to a chat connected to amoCRM. amoCRM sends a `message[add]` webhook with the text; the manager's reply comes as `outgoing_message[add]`. The server caches both by lead and contact, without calling the LLM: amoCRM waits at most 2 seconds.
2. The manager opens the lead card. The widget in the right panel (`lcard-1`) has an optional text field and the «Сгенерировать рекомендации» button.
3. The widget calls `POST /api/v1/amocrm/suggest` through `this.$authorizedAjax()`. amoCRM adds `X-Auth-Token`, a one-time JWT signed with the integration secret key (HS256).
4. The server verifies the token, loads the lead and the first name of its main contact through REST API v4, takes the latest customer messages from the cache (or the text from the field), and runs the same pipeline as `/api/v1/suggest`.
5. The widget shows the reply with «Копировать ответ» and the manager hint marked «не отправлять клиенту». The manager pastes the reply into the chat and sends it.

## Requirements

- An amoCRM account where you are an administrator.
- The backend reachable over **HTTPS** from the internet: amoCRM pages are HTTPS, so the browser blocks HTTP calls, and webhooks need a public address. For a test, a tunnel to `localhost:8000` (cloudflared, ngrok) is enough.

## 1. Create a private integration

1. In amoCRM open **амоМаркет** → **Создать интеграцию**.
2. Fill in the name, description, access rights and Redirect URI, for example your backend URL.
3. On the **Ключи** tab copy:
   - **ID интеграции** → `AMOCRM_CLIENT_ID`;
   - **Секретный ключ** → `AMOCRM_CLIENT_SECRET`;
   - press **Сгенерировать токен** for a long-lived token (from 1 day to 5 years, shown once) → `AMOCRM_ACCESS_TOKEN`. An OAuth 2.0 access token works the same way.

## 2. Upload the widget

```bash
python scripts/build_widget.py
```

```text
Готово: dist/widget.zip (версия 1.0.0)
```

The archive has `manifest.json`, `script.js`, `style.css`, `i18n/` and `images/` at its root. In **амоМаркет** open the integration, switch to **режим редактирования** and upload `dist/widget.zip`. amoCRM reports manifest errors on upload. Install the widget and set **«Адрес сервера ассистента»** to your backend URL, for example `https://assistant.example.com`.

Bump `widget.version` in `amocrm_widget/manifest.json` before uploading a new archive.

## 3. Subscribe to chat webhooks

In **амоМаркет** → **WEB HOOKS** add:

```text
https://assistant.example.com/api/v1/amocrm/webhook?secret=<AMOCRM_WEBHOOK_SECRET>
```

Select the incoming and outgoing chat message events. The webhook format (`message`, `outgoing_message`) is documented, but the event names in the UI may differ or be unavailable on your plan. Without webhooks everything still works: the manager pastes the customer message into the widget field.

## 4. Configure the server

```dotenv
AMOCRM_ENABLED=true
AMOCRM_BASE_URL=https://yoursubdomain.amocrm.ru
AMOCRM_ACCESS_TOKEN=...
AMOCRM_CLIENT_ID=...
AMOCRM_CLIENT_SECRET=...
AMOCRM_WEBHOOK_SECRET=a-long-random-string
CORS_ALLOW_ORIGINS=https://yoursubdomain.amocrm.ru
```

| Variable | Purpose |
| --- | --- |
| `AMOCRM_ENABLED` | Turns on `/api/v1/amocrm/*`; otherwise they answer `503 amocrm_disabled` |
| `AMOCRM_BASE_URL` | Account address; also checked against the token `iss` |
| `AMOCRM_ACCESS_TOKEN` | REST API v4 token; without it lead and contact data are skipped with a warning |
| `AMOCRM_CLIENT_ID` | Must equal the token `client_uuid` |
| `AMOCRM_CLIENT_SECRET` | Verifies the token signature |
| `AMOCRM_WEBHOOK_SECRET` | Expected `secret` query parameter of webhooks |
| `AMOCRM_HISTORY_LIMIT` | Messages per lead given to the model, default 20 |
| `AMOCRM_MESSAGE_TTL_HOURS` | How long cached messages live, default 24 |
| `CORS_ALLOW_ORIGINS` | Must contain the account origin: the widget calls the backend from the browser |

Restart the server. Run one Uvicorn process: the message cache lives in memory.

## Check

```bash
curl -s -X POST "https://assistant.example.com/api/v1/amocrm/webhook?secret=<secret>" \
  --data-urlencode 'message[add][0][id]=test-1' \
  --data-urlencode 'message[add][0][text]=Сколько стоит монтаж?' \
  --data-urlencode 'message[add][0][element_type]=2' \
  --data-urlencode 'message[add][0][element_id]=<lead id>' \
  --data-urlencode "message[add][0][created_at]=$(date +%s)"
```

```json
{"received":1,"stored":1}
```

Open that lead in amoCRM, leave the widget field empty and press «Сгенерировать рекомендации».

## Limits

- Generations from the widget are limited per amoCRM user (`RATE_LIMIT_PER_MINUTE`); over the limit the widget shows «Слишком много запросов…». The manager login (`UI_BASIC_AUTH_*`) does not apply to `/api/v1/amocrm/*`, which has its own JWT and webhook-secret checks — see [Access protection](access.md).
- No widget location inside the chat window and no documented way to insert text into the chat input: the widget lives in the lead card and the manager copies the reply.
- Chat history comes only from webhooks received after you subscribed; older messages can be pasted into the widget field.
- The cache is in process memory: one process, lost on restart. Replace `MessageStore` with Redis for several replicas.
- amoCRM webhooks are not signed: protect them with the secret and HTTPS. The secret is removed from access logs.
- Attachments are stored as «[вложение]» and not analysed.
