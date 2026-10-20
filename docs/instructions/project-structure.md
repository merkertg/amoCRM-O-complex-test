# Project structure

[← README](../../README.md) · [All documentation](../../README.md#documentation)

```text
amoCRM/
├── app/                           # Python package of the service
│   ├── main.py                    # create_app(): wiring, error handlers, CORS, static UI
│   ├── config.py                  # Settings from environment and .env (pydantic-settings)
│   ├── schemas.py                 # API models and the structured answer Suggestion
│   ├── errors.py                  # AppError: HTTP status, code, message for the manager
│   ├── logging_setup.py           # logging without personal data and secrets
│   ├── api/
│   │   ├── routes.py              # /api/v1/suggest, /health, /api/v1/knowledge-base
│   │   └── amocrm.py              # /api/v1/amocrm/suggest, /api/v1/amocrm/webhook
│   ├── core/                      # business logic, no HTTP or amoCRM inside
│   │   ├── assistant.py           # SalesAssistant: the pipeline
│   │   ├── prompts.py             # system prompt and user message blocks
│   │   ├── guards.py              # injection, sanitising, PII, leaks, amounts, upsell rules
│   │   └── dialog.py              # «Клиент: … / Менеджер: …» history parser
│   ├── knowledge/
│   │   ├── models.py              # knowledge base schema
│   │   ├── repository.py          # load and reload on file change
│   │   └── search.py              # tokenizer, stemmer, weighted keyword index
│   ├── llm/
│   │   └── client.py              # OpenAI-compatible client on HTTPX, error classes
│   ├── integrations/amocrm/
│   │   ├── client.py              # REST API v4: lead with contacts, contact
│   │   ├── auth.py                # one-time widget JWT verification
│   │   ├── webhooks.py            # message / outgoing_message webhook parsing
│   │   ├── message_store.py       # in-memory cache of chat messages with TTL
│   │   └── adapter.py             # DialogContext for a lead
│   └── static/                    # manager UI: index.html, styles.css, app.js
├── data/knowledge_base.json       # demo knowledge base
├── amocrm_widget/                 # widget sources: manifest, script, style, i18n, logos
├── scripts/
│   ├── build_widget.py            # dist/widget.zip for amoCRM
│   ├── build_guide.py             # PDF guide in Russian and English
│   └── guide/                     # PDF guide modules
├── tests/                         # pytest, FakeLLM and MockTransport
├── docs/
│   ├── instructions/              # these short instructions
│   ├── STAGE_01.md … STAGE_06.md  # detailed Russian guides per stage
│   ├── APPROACH.md, adr/          # approach and architecture decisions
│   ├── DEVELOPMENT_LOG.md         # development log
│   ├── VERIFICATION.md            # verification report
│   └── guide/                     # PDF guide, verification.json, rebuild instructions
├── Dockerfile, docker-compose.yml # container image and local stack
├── requirements.txt               # runtime dependencies, pinned
├── requirements-dev.txt           # + pytest
├── pyproject.toml                 # project metadata and pytest settings
├── .env.example                   # all settings with comments
└── AGENTS.md                      # rules for further work
```

## Dependency direction

```text
api ──► core ──► knowledge
 │        └────► llm (LLMClient protocol)
 └──► integrations/amocrm ──► core.dialog, schemas
```

`core` does not import FastAPI, HTTPX or amoCRM modules: it receives a `DialogContext`, a knowledge base repository and any object with `model` and `async complete(messages)`. Tests pass fakes through `create_app(settings, llm_client, amocrm_client)`.

## Configuration in pyproject.toml

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

- `pythonpath = ["."]` lets tests import `app` without installing the project.
- Deprecation warnings raised by our own code fail the tests.
- Starlette 1.x warns that its TestClient prefers `httpx2`; the application itself uses `httpx` as the specification requires, so the warning is ignored in tests only.
