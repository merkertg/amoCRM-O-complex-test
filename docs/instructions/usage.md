# Using the assistant

[← README](../../README.md) · [All documentation](../../README.md#documentation)

How a manager uses the web UI, how to call the REST API and how to read the answer. The Russian walkthrough is in the [Stage 03](../STAGE_03.md) and [Stage 04](../STAGE_04.md) guides.

## Manager UI

Open <http://127.0.0.1:8000>.

1. Paste the **customer message** into the left field (required, up to 4000 characters).
2. Optionally paste the **conversation history**: one line per message, starting with `Клиент:` or `Менеджер:`. Lines without a prefix continue the previous message. `Покупатель`, `Оператор`, `Client`, `Manager`, `К`, `М`, `Вы` are also recognised.
3. Optionally enter the **customer name**.
4. Press **«Сгенерировать рекомендации»** or `Ctrl+Enter`.

The right side shows:

| Block | Who it is for | What to do |
| --- | --- | --- |
| **Ответ клиенту** | The customer, after your review | Edit in place if needed, press «Копировать», paste into the chat and send yourself |
| **Подсказка менеджеру** | Only you — marked «не отправлять клиенту» | Decide whether to offer the item; copy the sample phrase if it fits |
| **Проверьте перед отправкой** | You | Warnings: unverified amounts, prompt injection, removed internal text, empty knowledge base match |
| **Источники и технические детали** | You | Knowledge base items given to the model, model name, latency, request id |

The four buttons under the form fill in test scenarios: purchase, too little information, complaint, prompt injection.

## REST API

### `POST /api/v1/suggest`

```bash
curl -s http://127.0.0.1:8000/api/v1/suggest \
  -H 'Content-Type: application/json' \
  -d '{"message": "Сколько стоит Бриз 09 с установкой?",
       "history_text": "Клиент: Ищу кондиционер в спальню\nМенеджер: Добрый день! Какая площадь?",
       "client_name": "Анна"}'
```

| Request field | Type | Required | Meaning |
| --- | --- | --- | --- |
| `message` | string, 1–4000 | yes | Current customer message; blank is rejected |
| `history` | list of `{"role": "client" \| "manager" \| "unknown", "text": "..."}` | no | Structured history; wins over `history_text` |
| `history_text` | string, up to 12000 | no | History as text with `Клиент:` / `Менеджер:` prefixes |
| `client_name` | string, up to 100 | no | Used for a personal greeting |

Response:

| Field | Meaning |
| --- | --- |
| `suggestion.customer_reply` | Draft reply to the customer |
| `suggestion.needs_clarification` | The reply asks a clarifying question because facts were missing |
| `suggestion.upsell_applicable` | Whether an upsell is appropriate now |
| `suggestion.upsell_product_id` | Knowledge base id, checked by the server |
| `suggestion.upsell_recommendation` | Item name, taken from the knowledge base |
| `suggestion.upsell_reason` | Why it fits, or why an upsell is inappropriate now |
| `suggestion.suggested_sales_phrase` | Sample phrase for the manager; `null` when not applicable |
| `meta.knowledge_sources` | Items passed to the model |
| `meta.injection_suspected` | Prompt injection markers found in customer data |
| `meta.warnings` | What to double-check before sending |
| `meta.request_id`, `meta.model`, `meta.latency_ms` | Technical details; `request_id` also appears in the log |

### Other endpoints

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/health` | Service state: knowledge base, LLM settings, amoCRM flag |
| `GET` | `/api/v1/knowledge-base` | Short list of items and FAQ topics |
| `POST` | `/api/v1/amocrm/suggest` | Called by the amoCRM widget, needs `X-Auth-Token` |
| `POST` | `/api/v1/amocrm/webhook?secret=...` | amoCRM chat message webhooks |
| `GET` | `/docs`, `/openapi.json` | Swagger UI and OpenAPI schema |

## Status codes you may see

Every error has the same body: `{"error": {"code": "...", "message": "..."}}`. The message is written for a manager.

| HTTP | `code` | When |
| --- | --- | --- |
| 422 | `validation_error` | Empty or too long field; the body lists field names, never values |
| 422 | `amocrm_no_message` | Widget call without text and no cached customer message |
| 400 | `amocrm_webhook_invalid` | Webhook body is not valid form data or JSON |
| 401 | `unauthorized` | Manager login is enabled and the request has no or wrong credentials — see [Access protection](access.md) |
| 401 | `amocrm_widget_unauthorized` | Missing, expired or foreign widget token |
| 403 | `amocrm_webhook_forbidden` | Wrong webhook secret |
| 404 | `amocrm_lead_not_found` | Lead does not exist in amoCRM |
| 429 | `rate_limited` | More than `RATE_LIMIT_PER_MINUTE` generations in a minute; wait for `Retry-After` seconds |
| 502 | `llm_invalid_output` | The model returned invalid JSON twice |
| 502 | `llm_bad_request`, `llm_bad_response` | The provider rejected the request or answered without content |
| 503 | `llm_unavailable` | Provider down, rate limited (429) or 5xx after retries |
| 503 | `llm_auth` | Wrong `LLM_API_KEY` (401/403) |
| 503 | `knowledge_base_unavailable`, `amocrm_disabled` | No valid knowledge base; amoCRM integration is off |
| 504 | `llm_timeout` | No answer within `LLM_TIMEOUT_SECONDS` after retries |
| 500 | `internal_error` | Unexpected error; the log has the type and stack, not the message text |
