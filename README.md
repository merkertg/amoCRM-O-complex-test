# AI Sales Assistant for amoCRM

A Python MVP of an AI assistant for sales managers who chat with customers in amoCRM. The manager pastes or opens a conversation, and the service returns **two independent blocks**: a polite, ready-to-review **reply to the customer** built only from facts in a small company knowledge base, and an internal **upsell hint for the manager**: whether an upsell is appropriate right now, which product or service to offer (only from the knowledge base), why, and a sample phrase. The assistant never sends anything to the customer: the manager reviews, edits and sends the reply. The demo company КлиматДом (air conditioners, installation, service) and all its data are fictional.

**All six stages of the specification are implemented.** A FastAPI service with a REST API and Swagger docs, a JSON knowledge base that reloads on edit, keyword retrieval with light Russian stemming, an OpenAI-compatible LLM client on HTTPX with retries, a strict structured JSON answer validated by Pydantic with one repair attempt, and server-side guards. The guards keep upsells inside the knowledge base, strip internal hints from the customer reply, flag amounts that are not in the facts, detect prompt injection and mask phone numbers, e-mails and card numbers before the LLM. The manager UI is plain HTML/CSS/JS. The amoCRM integration has three parts: a widget for the lead card, which calls the backend with an amoCRM one-time JWT; a webhook receiver for chat messages; and a REST API v4 client for lead and contact data. 95 pytest tests run without network or keys. A Docker image runs as a non-root user.

**Start with the [quickstart](docs/instructions/quickstart.md)** or the detailed Russian walkthroughs for [stages 01–06](docs/STAGE_01.md). Illustrated PDF guides: [Russian](docs/guide/amocrm-sales-assistant-guide.pdf) and [English](docs/guide/amocrm-sales-assistant-guide-en.pdf); [rebuild and verification](docs/guide/README.md). After starting the server, open the manager UI at <http://127.0.0.1:8000> or the API documentation at <http://127.0.0.1:8000/docs>.

## Roadmap

| Stage | Work | Status |
| --- | --- | --- |
| 01 | Minimal architecture, project structure, settings, error model | Implemented |
| 02 | Knowledge base (JSON, validation, hot reload) and retrieval | Implemented: 10 products/services, 7 FAQ entries, keyword search with stemming and related items |
| 03 | LLM client, prompt, two-block structured answer, guards | Implemented; tested with a fake LLM and a stub OpenAI-compatible server, a live LLM requires a key |
| 04 | FastAPI REST API and the manager UI | Implemented: `/api/v1/suggest`, `/health`, `/api/v1/knowledge-base`, Swagger, responsive UI |
| 05 | Tests and Docker | Implemented: 95 tests, Dockerfile, Compose, container smoke check |
| 06 | amoCRM integration | Implemented: lead-card widget with one-time JWT, chat webhooks, REST API v4 client; checked on a widget mock, a real amoCRM account is not verified |
| + | CI, linters, Redis cache for multiple replicas | Not started |

## Documentation

Instructions ([docs/instructions/](docs/instructions/)):

- [Quickstart](docs/instructions/quickstart.md): requirements, Docker or local run, LLM providers, settings
- [Using the assistant](docs/instructions/usage.md): manager UI, REST API, response fields, warnings, error codes
- [Knowledge base](docs/instructions/knowledge-base.md): file format, editing without restart, how retrieval uses it
- [amoCRM integration](docs/instructions/amocrm.md): private integration, widget upload, webhooks, server settings
- [Testing and verification](docs/instructions/testing.md): pytest, manual checks with a stub LLM, Docker smoke check
- [Project structure](docs/instructions/project-structure.md)

Stage learning guides in Russian:

- [Stage 01: architecture and project structure](docs/STAGE_01.md)
- [Stage 02: knowledge base and retrieval](docs/STAGE_02.md)
- [Stage 03: LLM and two answer blocks](docs/STAGE_03.md)
- [Stage 04: FastAPI and manager UI](docs/STAGE_04.md)
- [Stage 05: tests and Docker](docs/STAGE_05.md)
- [Stage 06: amoCRM integration](docs/STAGE_06.md)
- [Russian PDF guide](docs/guide/amocrm-sales-assistant-guide.pdf), [English PDF guide](docs/guide/amocrm-sales-assistant-guide-en.pdf) and [rebuild instructions](docs/guide/README.md)
- [Project verification](docs/VERIFICATION.md)

Design and history:

- [Solution approach](docs/APPROACH.md)
- [Architecture decisions](docs/adr/)
- [Development log](docs/DEVELOPMENT_LOG.md)

## Quick start

```bash
cp .env.example .env    # set LLM_API_KEY (and LLM_BASE_URL / LLM_MODEL if not OpenAI)
docker compose up --build
```

Open <http://127.0.0.1:8000>, paste a customer message and press «Сгенерировать рекомендации». Local run without Docker, Ollama and all settings: [Quickstart](docs/instructions/quickstart.md).
