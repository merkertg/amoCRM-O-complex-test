# AI Sales Assistant for amoCRM

A Python MVP of an AI assistant for sales managers who chat with customers in amoCRM. The manager pastes or opens a conversation, and the service returns **two independent blocks**: a polite, ready-to-review **reply to the customer** built only from facts in a small company knowledge base, and an internal **upsell hint for the manager**: whether an upsell is appropriate right now, which product or service to offer (only from the knowledge base), why, and a sample phrase. The assistant never sends anything to the customer: the manager reviews, edits and sends the reply. The demo company КлиматДом (air conditioners, installation, service) and all its data are fictional.

**All six stages of the specification are implemented.** A FastAPI service with a REST API and Swagger docs, a JSON knowledge base that reloads on edit, keyword retrieval with light Russian stemming, an OpenAI-compatible LLM client on HTTPX with retries, a strict structured JSON answer validated by Pydantic with one repair attempt, and server-side guards. The guards keep upsells inside the knowledge base, strip internal hints from the customer reply, flag amounts that are not in the facts, detect prompt injection and mask phone numbers, e-mails and card numbers before the LLM. The manager UI is plain HTML/CSS/JS. The amoCRM integration has three parts: a widget for the lead card, which calls the backend with an amoCRM one-time JWT; a webhook receiver for chat messages; and a REST API v4 client for lead and contact data. 124 pytest tests run without network or keys. A Docker image runs as a non-root user.

**Stage 07 adds CI and local quality checks:** Ruff, mypy, pytest, documentation links and widget packaging. All commands pass locally; execution on GitHub Actions has not yet been verified.

**Stage 08 adds quality evaluations and access protection.** An offline retrieval evaluation (24 questions, hit@1 and recall gates) runs in CI. A dialogue evaluation (12 scenarios) measures a real LLM through the whole pipeline once a key is configured. Optional HTTP Basic login protects the manager UI, `/api/v1/suggest` and `/docs`, and a per-IP / per-amoCRM-user limit caps paid generations per minute.

**Start with the [demo walkthrough](docs/DEMO.md)** or the [quickstart](docs/instructions/quickstart.md). The documentation follows the same organization as AI Support Agent: short task instructions, detailed Russian stage guides, practical walkthroughs, design decisions and verification evidence. After starting the server, open the manager UI at <http://127.0.0.1:8000> or the API documentation at <http://127.0.0.1:8000/docs>.

## Roadmap

| Stage | Work | Status |
| --- | --- | --- |
| 01 | Minimal architecture, project structure, settings, error model | Implemented |
| 02 | Knowledge base (JSON, validation, hot reload) and retrieval | Implemented: 10 products/services, 7 FAQ entries, keyword search with stemming and related items |
| 03 | LLM client, prompt, two-block structured answer, guards | Implemented; tested with a fake LLM and a stub OpenAI-compatible server, a live LLM requires a key |
| 04 | FastAPI REST API and the manager UI | Implemented: `/api/v1/suggest`, `/health`, `/api/v1/knowledge-base`, Swagger, responsive UI |
| 05 | Tests and Docker | Implemented: test suite (currently 124 tests), Dockerfile, Compose, recorded container smoke check |
| 06 | amoCRM integration | Implemented: lead-card widget with one-time JWT, chat webhooks, REST API v4 client; checked on a widget mock, a real amoCRM account is not verified |
| 07 | CI and quality checks | Implemented: GitHub Actions workflow; Ruff, mypy, pytest, documentation links and widget packaging pass locally; remote CI not yet verified |
| 08 | Quality evaluations and access protection | Implemented: retrieval evaluation gated in CI, live-LLM dialogue evaluation, HTTP Basic login, generation rate limit; 124 tests, mypy over 30 files; a live-LLM evaluation run requires a key |
| + | Redis message cache for multiple replicas | Not started |

## Documentation

Instructions ([docs/instructions/](docs/instructions/)):

- [Quickstart](docs/instructions/quickstart.md): requirements, Docker or local run, LLM providers, settings
- [Using the assistant](docs/instructions/usage.md): manager UI, REST API, response fields, warnings, error codes
- [Knowledge base](docs/instructions/knowledge-base.md): file format, editing without restart, how retrieval uses it
- [amoCRM integration](docs/instructions/amocrm.md): private integration, widget upload, webhooks, server settings
- [Testing and verification](docs/instructions/testing.md): pytest, manual checks with a stub LLM, Docker smoke check
- [CI and quality checks](docs/instructions/ci.md): run the workflow commands locally, inspect GitHub Actions and understand the check scope
- [Quality evaluations](docs/instructions/evaluations.md): retrieval suite in CI, dialogue suite with a live LLM, reading the report
- [Access protection](docs/instructions/access.md): manager login, generation rate limit, what stays public
- [Project structure](docs/instructions/project-structure.md)

Detailed stage guides in Russian:

- [Stage 01: architecture and project structure](docs/STAGE_01.md)
- [Stage 02: knowledge base and retrieval](docs/STAGE_02.md)
- [Stage 03: LLM and two answer blocks](docs/STAGE_03.md)
- [Stage 04: FastAPI and manager UI](docs/STAGE_04.md)
- [Stage 05: tests and Docker](docs/STAGE_05.md)
- [Stage 06: amoCRM integration](docs/STAGE_06.md)
- [Stage 07: CI and quality checks](docs/STAGE_07.md)
- [Stage 08: evaluations and access protection](docs/STAGE_08.md)

Practical walkthroughs in Russian:

- [Demo walkthrough](docs/DEMO.md): a 5–7 minute manager demonstration with a local stub, grounded examples and explicit verification limits
- [CI/CD and Docker guide](docs/CI_CD.md): what the current workflow checks, local commands and manual container operation

Illustrated guides:

- [Russian PDF guide](docs/guide/amocrm-sales-assistant-guide.pdf)
- [English PDF guide](docs/guide/amocrm-sales-assistant-guide-en.pdf)
- [Rebuild and visual verification](docs/guide/README.md)

Design and history:

- [Solution approach](docs/APPROACH.md)
- [Architecture decisions](docs/adr/)
- [Verification report](docs/VERIFICATION.md): current local checks, recorded earlier runs and unverified integrations
- [Verification data](docs/guide/verification.json): evidence used by both PDF editions
- [Development log](docs/DEVELOPMENT_LOG.md)

## Quick start

```bash
cp .env.example .env    # set LLM_API_KEY (and LLM_BASE_URL / LLM_MODEL if not OpenAI)
docker compose up --build
```

Open <http://127.0.0.1:8000>, paste a customer message and press «Сгенерировать рекомендации». Local run without Docker, Ollama and all settings: [Quickstart](docs/instructions/quickstart.md).
