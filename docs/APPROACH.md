# AI Sales Assistant for amoCRM — Solution Approach

## Problem and product goal

Sales managers answer customers in amoCRM chats all day. They need a fast, correct reply and a reminder of what else may help the customer — without the risk that a model invents a price or sends something on its own. The assistant reads the customer message, the conversation and a small company knowledge base and returns two independent blocks:

1. **Customer reply** — polite, natural, grounded only in knowledge base facts, aware of the history; a clarifying question when facts are missing. Ready to send after the manager reviews it.
2. **Manager hint** — whether an upsell or cross-sell is appropriate now, which knowledge base item to offer, why, and a sample phrase; or an explicit «not appropriate» with the reason.

The second block is internal and is never sent automatically. Success criterion: a working MVP that helps a manager answer quickly and spot a relevant upsell.

## Current implementation: Stages 01–06

| Stage | Result |
| --- | --- |
| 01 Architecture | One FastAPI service; modules `api`, `core`, `knowledge`, `llm`, `integrations/amocrm`; `DialogContext` as the single input of the business logic; `AppError` with HTTP status, code and a manager-facing message |
| 02 Knowledge base | `data/knowledge_base.json` validated by Pydantic (unique ids, existing `related`), reloaded on file change, keeps the last valid version; weighted keyword retrieval with light Russian stemming and related items |
| 03 LLM | OpenAI-compatible Chat Completions over HTTPX with retries; system prompt with fact, safety and format rules; strict JSON validated by `Suggestion`; one repair attempt; server-side guards |
| 04 API and UI | `POST /api/v1/suggest`, `GET /health`, `GET /api/v1/knowledge-base`, Swagger; plain HTML/CSS/JS UI with two visually separated blocks |
| 05 Tests and Docker | 95 pytest tests without network; `python:3.12-slim` image running as a non-root user with a health check; Compose with a read-only knowledge base mount |
| 06 amoCRM | Lead-card widget (`lcard-1`) calling the backend with `$authorizedAjax` and a one-time JWT; webhook receiver for `message` / `outgoing_message`; REST API v4 client for the lead and the contact first name |

## Stack and responsibility

| Component | Responsibility |
| --- | --- |
| FastAPI, Uvicorn | HTTP, validation of requests, OpenAPI, static UI |
| Pydantic, pydantic-settings | Request and answer schemas, knowledge base schema, settings from the environment |
| HTTPX | LLM provider and amoCRM REST API calls; `MockTransport` in tests |
| PyJWT | HS256 verification of amoCRM one-time widget tokens |
| JSON file | Knowledge base editable without code changes |
| pytest | Unit and API tests with `FakeLLM` and mocked HTTP |
| Docker, Compose | Reproducible run |

No vector database, queues, agents or microservices: the knowledge base has tens of items and a request takes seconds.

## Pipeline

```text
DialogContext (manual UI/API or amoCRM adapter)
  → sanitise, trim, redact PII, detect injection
  → retrieve knowledge base items (+ related)
  → build prompt: system rules + <knowledge_base> <catalog> <client_info> <dialog_history> <customer_message>
  → LLM (retries) → parse JSON → validate Suggestion (one repair attempt)
  → enforce upsell rules → strip internal leaks → flag unverified amounts
  → SuggestResponse {suggestion, meta.warnings, meta.knowledge_sources}
```

## Key principles

- **Human in the loop.** The service only returns text. There is no code path that sends a message to a customer.
- **Facts only from the knowledge base.** The prompt forbids other facts; the server checks that the recommended item exists, takes its name from the file and flags amounts that are neither in the file nor in the conversation.
- **Separation of blocks.** Separate JSON fields, separate UI blocks with an «internal» badge, and server-side removal of internal wording from the customer reply.
- **Untrusted customer data.** Customer text is isolated in tagged blocks, prompt tags inside it are removed, injection markers produce a warning, and the model has no tools.
- **Warn, do not block.** Heuristic checks add warnings for the manager instead of failing the request; hard failures are reserved for invalid structure.
- **Privacy.** Logs contain ids, counters and error codes only; phones, e-mails and card numbers are masked before the LLM; only the contact first name is read from amoCRM; cached chat messages expire.

## Decisions

- [ADR 0001](adr/0001-application-layout-and-tooling.md): single FastAPI service, pip requirements, dependency direction.
- [ADR 0002](adr/0002-knowledge-base-and-keyword-retrieval.md): JSON knowledge base and keyword retrieval instead of a vector database.
- [ADR 0003](adr/0003-llm-client-structured-output-and-guards.md): OpenAI-compatible client on HTTPX, strict JSON with repair, server-side guards.
- [ADR 0004](adr/0004-amocrm-widget-and-webhooks.md): amoCRM widget with one-time JWT and webhook message cache.

## Architecture

```text
Manager UI ──POST /api/v1/suggest──────────────┐
amoCRM widget ──POST /api/v1/amocrm/suggest──► FastAPI (app/api)
amoCRM ──webhooks──► MessageStore               │
                         ▲                      ▼
            AmoCRMAdapter ──REST API v4──► amoCRM
                         │
                         ▼
                  SalesAssistant (app/core) ──► KnowledgeIndex (app/knowledge)
                         │
                         ▼
             OpenAICompatibleClient (app/llm) ──► LLM provider
```

## Verification

Local: 95 pytest tests; the UI and the widget clicked through in a browser against a stub OpenAI-compatible server; Docker image built and started; logs checked for personal data. Not verified: answer quality of a real LLM, a real amoCRM account, CI (there is no CI yet). Details: [VERIFICATION.md](VERIFICATION.md).

## Next steps

- Evaluate a real model on a fixed set of dialogues (grounding, clarification, upsell appropriateness).
- GitHub Actions with pytest, Ruff and mypy.
- Redis for the message cache to run several replicas.
- «Save hint as a note» via `POST /api/v4/leads/{id}/notes`.
- A `card_sdk` tab instead of the right-panel block.
