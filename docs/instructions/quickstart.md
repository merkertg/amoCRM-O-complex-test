# Quickstart

[← README](../../README.md) · [All documentation](../../README.md#documentation)

Configure an LLM provider, start the service with Docker or locally, open the manager UI and check that it works. Detailed walkthroughs in Russian are in the [Stage 01](../STAGE_01.md) and [Stage 04](../STAGE_04.md) guides.

For a guided demonstration without a live LLM key, follow the Russian
[demo walkthrough](../DEMO.md). For the automated checks and manual Docker
workflow, see the Russian [CI/CD guide](../CI_CD.md).

## Requirements

- An API key of any OpenAI-compatible Chat Completions API (OpenAI, OpenRouter, DeepSeek and others), or a local [Ollama](https://ollama.com) without a key.
- Docker with the `docker compose` command (Docker Desktop on macOS) — for the container run.
- Python 3.12 or newer — for the local run. On macOS the system `python3` is 3.9; install 3.12 with `uv python install 3.12` or Homebrew.
- Git, to clone the repository.

Run all commands from the project root, the directory containing `requirements.txt`.

## Supported platforms

| | macOS (Apple Silicon) | Linux |
| --- | --- | --- |
| Python on the host | 3.12 in `.venv` | same |
| Container | Docker Desktop | Docker Engine or Desktop |
| Verified by | Local run: pytest, Uvicorn, curl, browser, Docker build and container start | Not verified (the image is `python:3.12-slim`) |

Windows is not checked.

## Configure the LLM

```bash
cp .env.example .env
```

Open `.env` and set at least `LLM_API_KEY`. Examples:

| Provider | `LLM_BASE_URL` | `LLM_MODEL` | `LLM_API_KEY` |
| --- | --- | --- | --- |
| OpenAI | `https://api.openai.com/v1` | `gpt-4.1-mini` | your key |
| OpenRouter | `https://openrouter.ai/api/v1` | a model id from OpenRouter | your key |
| Ollama on the host | `http://localhost:11434/v1` | `qwen2.5:7b` | empty |
| Ollama from Docker | `http://host.docker.internal:11434/v1` | `qwen2.5:7b` | empty |

For models that reject `temperature`, set `LLM_TEMPERATURE=none`. If the provider does not support `response_format`, set `LLM_JSON_MODE=false`. `.env` is ignored by Git.

## Option 1. Docker

```bash
docker compose up --build
```

Expected output ends with:

```text
assistant-1  | INFO:     Uvicorn running on http://0.0.0.0:8000 (Press CTRL+C to quit)
```

`./data` is mounted read-only into the container, so edits of the knowledge base are picked up without a rebuild. Stop with `Ctrl+C` or `docker compose down`.

## Option 2. Local run

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
uvicorn app.main:app --reload
```

Expected output:

```text
INFO:     Uvicorn running on http://127.0.0.1:8000 (Press CTRL+C to quit)
INFO:     Application startup complete.
```

`--reload` restarts the server when a `.py` file changes. If port 8000 is busy, use `--port 8001`.

## Check that it works

```bash
curl http://127.0.0.1:8000/health
```

```json
{"status":"ok","llm":{"model":"gpt-4.1-mini","api_key_set":true},"knowledge_base":{"path":"knowledge_base.json","products":10,"faq":7,"loaded_at":"..."},"amocrm_enabled":false}
```

`status` is `degraded` if the knowledge base file was edited into an invalid state; the service keeps the last valid version, and the error is shown in `knowledge_base.last_error`.

Open the manager UI at <http://127.0.0.1:8000>, press the «Покупка кондиционера» example and «Сгенерировать рекомендации». Interactive API documentation: <http://127.0.0.1:8000/docs>.

## Settings

Settings are read from environment variables, then from `.env`, then from defaults in `app/config.py`. An empty variable means the default. Settings are read at startup, so restart the server after changing `.env`.

| Variable | Default | Purpose |
| --- | --- | --- |
| `LLM_BASE_URL` | `https://api.openai.com/v1` | Base URL of an OpenAI-compatible API |
| `LLM_API_KEY` | not set | Bearer key; not needed for Ollama |
| `LLM_MODEL` | `gpt-4.1-mini` | Model name |
| `LLM_TEMPERATURE` | `0.2` | `none` — do not send the parameter |
| `LLM_MAX_TOKENS` | not set | Sent as `max_tokens` only if set |
| `LLM_JSON_MODE` | `true` | Send `response_format: {"type": "json_object"}` |
| `LLM_TIMEOUT_SECONDS` | `30` | Timeout of one LLM request |
| `LLM_MAX_RETRIES` | `2` | Retries on timeout, network error, 429 and 5xx |
| `KNOWLEDGE_BASE_PATH` | `data/knowledge_base.json` | Knowledge base file |
| `KB_TOP_K` | `5` | Matched knowledge base items passed to the LLM (plus up to 3 related) |
| `MAX_MESSAGE_CHARS`, `MAX_HISTORY_CHARS`, `MAX_HISTORY_MESSAGES` | `4000`, `12000`, `30` | Input limits; the latest history is kept |
| `REDACT_PII_FOR_LLM` | `true` | Mask phones, e-mails and card numbers before the LLM |
| `LOG_LEVEL` | `INFO` | Log level |
| `CORS_ALLOW_ORIGINS` | empty | Comma-separated origins, e.g. `https://example.amocrm.ru` |
| `UI_BASIC_AUTH_USERNAME`, `UI_BASIC_AUTH_PASSWORD` | not set | Manager login for the UI, `/api/v1/suggest` and `/docs`; set both on any non-local server — see [Access protection](access.md) |
| `RATE_LIMIT_PER_MINUTE` | `30` | Generations per minute per client IP or amoCRM user; `0` — no limit |
| `AMOCRM_*` | disabled | See [amoCRM integration](amocrm.md) |
