# Access protection

[← README](../../README.md) · [All documentation](../../README.md#documentation)

The manager UI and `/api/v1/suggest` call a paid LLM. On a server reachable from the internet — and amoCRM needs one with HTTPS — protect them with a login and keep the generation rate limit on. The Russian walkthrough is in the [Stage 08](../STAGE_08.md) guide.

## What is protected and how

| Path | Protection |
| --- | --- |
| `/`, `/static/*`, `/api/v1/suggest`, `/api/v1/knowledge-base`, `/docs`, `/openapi.json` | HTTP Basic login when `UI_BASIC_AUTH_*` is set |
| `/api/v1/amocrm/suggest` | One-time widget JWT (`X-Auth-Token`); see [amoCRM integration](amocrm.md) |
| `/api/v1/amocrm/webhook` | `?secret=` from `AMOCRM_WEBHOOK_SECRET` |
| `/health` | Public: monitoring and the Docker health check |

Generation rate limit: `RATE_LIMIT_PER_MINUTE` requests per minute per client IP on `/api/v1/suggest` and per amoCRM user on `/api/v1/amocrm/suggest`.

## Enable the manager login

```dotenv
UI_BASIC_AUTH_USERNAME=manager
UI_BASIC_AUTH_PASSWORD=a-long-random-password
```

Set both or neither: one without the other stops the service at startup with `UI_BASIC_AUTH_USERNAME и UI_BASIC_AUTH_PASSWORD задаются вместе`. Restart the server.

The browser shows its own sign-in window on the first visit and then sends the credentials with every request to the same address, so the UI needs no changes. Scripts pass them explicitly:

```bash
curl -u manager:a-long-random-password http://127.0.0.1:8000/api/v1/suggest \
  -H 'Content-Type: application/json' -d '{"message": "Сколько стоит монтаж?"}'
```

Without the login, protected paths answer:

```text
HTTP/1.1 401 Unauthorized
www-authenticate: Basic realm="AI Sales Assistant", charset="UTF-8"
{"error":{"code":"unauthorized","message":"Введите логин и пароль менеджера."}}
```

HTTP Basic sends the password with every request, encoded but not encrypted — use it only over HTTPS. Credentials are compared in constant time; neither they nor the `Authorization` header are logged. Without `UI_BASIC_AUTH_*` the service logs a warning at startup.

## Rate limit

```dotenv
RATE_LIMIT_PER_MINUTE=30
```

`0` disables the limit. Over the limit the API answers `429` with `Retry-After` in seconds, and the UI shows «Слишком много запросов. Подождите немного и попробуйте снова.»:

```text
HTTP/1.1 429 Too Many Requests
retry-after: 59
{"error":{"code":"rate_limited","message":"Слишком много запросов. Подождите немного и попробуйте снова."}}
```

The window slides: a request is counted for 60 seconds. Counters live in process memory (like the amoCRM message cache) and reset on restart.

Behind a reverse proxy every request may come from the proxy address and share one counter. Uvicorn trusts `X-Forwarded-For` only from addresses listed in the `FORWARDED_ALLOW_IPS` environment variable (default `127.0.0.1,::1`); set it to your proxy address so the limit applies per real client.

## Check

```bash
curl -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1:8000/
curl -s -o /dev/null -w "%{http_code}\n" -u manager:a-long-random-password http://127.0.0.1:8000/
curl -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1:8000/health
```

Expected: `401`, `200`, `200`. Automated checks: `tests/test_access.py`.
