# Project structure

[← README](../../README.md) · [All documentation](../../README.md#documentation)

```text
amoCRM/
├── .github/workflows/ci.yml        # Python 3.12 quality checks on push, PR and manual run
├── app/                           # Python package of the service
│   ├── main.py                    # create_app(): wiring, error handlers, CORS, static UI
│   ├── config.py                  # Settings from environment and .env (pydantic-settings)
│   ├── schemas.py                 # API models and the structured answer Suggestion
│   ├── errors.py                  # AppError: HTTP status, code, message for the manager
│   ├── logging_setup.py           # logging without personal data and secrets
│   ├── api/
│   │   ├── routes.py              # /api/v1/suggest, /health, /api/v1/knowledge-base
│   │   ├── amocrm.py              # /api/v1/amocrm/suggest, /api/v1/amocrm/webhook
│   │   └── access.py              # manager login (HTTP Basic) and generation rate limit
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
├── evals/                         # quality evaluations
│   ├── runner.py                  # retrieval metrics and dialogue checks
│   ├── retrieval.json             # 24 questions with expected items, CI thresholds
│   └── dialogues.json             # 12 scenarios for a live LLM
├── amocrm_widget/                 # widget sources: manifest, script, style, i18n, logos
├── scripts/
│   ├── build_widget.py            # dist/widget.zip for amoCRM
│   ├── build_guide.py             # PDF guide in Russian and English
│   ├── check_docs.py              # offline local Markdown links and anchors
│   ├── run_evals.py               # retrieval (CI) and dialogue (live LLM) evaluations
│   └── guide/                     # bilingual PDF guide modules
│       ├── sources.py             # project facts and source-code excerpts
│       ├── stages_core.py, stages_delivery.py # explanations for stages 01–06
│       ├── quality.py             # Stage 07: CI and local quality checks
│       ├── evaluation.py          # Stage 08: evaluations and access protection
│       ├── documentation.py       # documentation map and suggested reading paths
│       ├── reference.py           # commands, troubleshooting and verification
│       └── layout.py, diagrams.py, toc.py, i18n.py # shared layout and translations
├── tests/                         # pytest, FakeLLM and MockTransport
├── docs/
│   ├── instructions/              # these short instructions
│   ├── STAGE_01.md … STAGE_08.md  # detailed Russian guides per stage
│   ├── DEMO.md                    # guided manager demonstration with a local stub
│   ├── CI_CD.md                   # Russian CI walkthrough and manual Docker operation
│   ├── RELEASES.md                # versioning and manual image/widget release
│   ├── RECOVERY.md                # service, provider and knowledge-file recovery
│   ├── DEPENDENCY_UPDATES.md      # pinned direct dependencies and manual updates
│   ├── PROJECT_STATUS_2026-10-27.md # dated status and outstanding checks
│   ├── APPROACH.md, adr/          # approach and architecture decisions
│   ├── DEVELOPMENT_LOG.md         # development log
│   ├── VERIFICATION.md            # verification report
│   └── guide/                     # PDF guide, verification.json, rebuild instructions
├── reports/                       # evaluation reports (ignored by Git)
├── Dockerfile, docker-compose.yml # container image and local stack
├── requirements.txt               # runtime dependencies, pinned
├── requirements-dev.txt           # runtime dependencies + pytest, Ruff and mypy
├── requirements-guide.txt         # + ReportLab for PDF authoring
├── pyproject.toml                 # project metadata; pytest, Ruff and mypy settings
├── .env.example                   # all settings with comments
└── AGENTS.md                      # rules for further work
```

## Documentation organization

The same layers are used in AI Support Agent. Stage numbers follow this
project's roadmap; each guide describes the amoCRM assistant's own behavior.
Use the [root README](../../README.md#documentation) as the single entry point.

| Layer | Location | Purpose |
| --- | --- | --- |
| Project overview | [README.md](../../README.md) | Product, roadmap and complete documentation index |
| Short task instructions | [instructions/](.) | Task instructions for setup, Windows, usage, knowledge, amoCRM, testing, CI, evaluations, access, backup and privacy |
| Stage learning guides | [STAGE_01.md](../STAGE_01.md) through [STAGE_08.md](../STAGE_08.md) | Detailed Russian explanations and self-check questions |
| Practical walkthroughs | [DEMO.md](../DEMO.md), [CI_CD.md](../CI_CD.md), [RELEASES.md](../RELEASES.md), [RECOVERY.md](../RECOVERY.md), [DEPENDENCY_UPDATES.md](../DEPENDENCY_UPDATES.md) | Demonstration, checks, manual releases, recovery and dependency updates |
| Design | [APPROACH.md](../APPROACH.md), [adr/](../adr/) | English approach and architecture decisions |
| Evidence and history | [VERIFICATION.md](../VERIFICATION.md), [DEVELOPMENT_LOG.md](../DEVELOPMENT_LOG.md) | Russian factual results, limitations and completed steps |
| Illustrated guide | [guide/](../guide/) | Russian/English PDFs, shared verification data and rebuild instructions |

Suggested reading paths:

- First demonstration: [DEMO](../DEMO.md) → [Quickstart](quickstart.md) → [Usage](usage.md).
- Learning: [Stage 01](../STAGE_01.md) → subsequent stages → [Approach](../APPROACH.md).
- Development: [Testing](testing.md) → [CI instructions](ci-and-delivery.md) → [CI/CD walkthrough](../CI_CD.md).
- Evidence: [Verification report](../VERIFICATION.md) → [verification.json](../guide/verification.json).

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

[tool.ruff]
target-version = "py312"
src = [".", "scripts"]
extend-exclude = [".claude"]

[tool.ruff.lint]
select = ["E4", "E7", "E9", "F", "I"]

[tool.mypy]
python_version = "3.12"
files = ["app", "evals"]
check_untyped_defs = true
disallow_untyped_defs = true
warn_unused_ignores = true
warn_redundant_casts = true
strict_equality = true
enable_error_code = ["ignore-without-code"]
```

- `pythonpath = ["."]` lets tests import `app` without installing the project.
- Deprecation warnings raised by our own code fail the tests.
- Starlette 1.x warns that its TestClient prefers `httpx2`; the application itself uses `httpx` as the specification requires, so the warning is ignored in tests only.
- Ruff checks `app`, `tests`, `scripts` and `evals` for code errors and consistent imports; long prompts and teaching examples are not subject to a line-length rule.
- mypy checks the application and the evaluation runner (30 files), including function signatures and bodies, without blanket import or error exclusions. Tests and PDF authoring modules remain outside its scope.

## Quality workflow

[.github/workflows/ci.yml](../../.github/workflows/ci.yml) runs on pushes, pull requests and manual dispatch. It installs `requirements-dev.txt`, then runs Ruff, mypy, pytest, the offline retrieval evaluation, the documentation link checker and the widget builder. Dependency and action downloads require network access; tests use `FakeLLM` and `httpx.MockTransport` without contacting a provider or amoCRM.

Runtime dependencies stay in `requirements.txt`; pinned development tools are in `requirements-dev.txt`; PDF authoring dependencies stay in `requirements-guide.txt`. The workflow does not build or visually verify PDFs, build Docker images, or call a live LLM or amoCRM account. See [CI and quality checks](ci-and-delivery.md) for local commands and hosted-run verification.
