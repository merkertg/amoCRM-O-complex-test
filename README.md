# AI Sales Assistant for amoCRM

A Python MVP of an AI assistant for sales managers who chat with customers in amoCRM. The manager pastes or opens a conversation, and the service returns **two independent blocks**: a polite, ready-to-review **reply to the customer** built only from facts in a small company knowledge base, and an internal **upsell hint for the manager**: whether an upsell is appropriate right now, which product or service to offer (only from the knowledge base), why, and a sample phrase. The assistant never sends anything to the customer: the manager reviews, edits and sends the reply. The demo company КлиматДом (air conditioners, installation, service) and all its data are fictional.

The project implements **all eight stages**: the six stages of the specification plus CI and quality evaluations with access protection. A FastAPI service with a REST API and Swagger docs, a JSON knowledge base that reloads on edit, keyword retrieval with light Russian stemming, an OpenAI-compatible LLM client on HTTPX with retries, a strict structured JSON answer validated by Pydantic with one repair attempt, and server-side guards: upsells stay inside the knowledge base, internal hints are stripped from the customer reply, amounts that are not in the facts are flagged, prompt injection is detected, and phone numbers, e-mails and card numbers are masked before the LLM. The manager UI is plain HTML/CSS/JS. The amoCRM integration has three parts: a lead-card widget that calls the backend with an amoCRM one-time JWT, a webhook receiver for chat messages, and a REST API v4 client for lead and contact data. Optional HTTP Basic login protects the manager UI, `/api/v1/suggest` and `/docs`; a per-IP / per-amoCRM-user limit caps paid generations per minute. GitHub Actions runs Ruff, mypy, 124 offline pytest tests, an offline retrieval evaluation with hit@1/recall thresholds, a documentation link check and the widget build; a 12-scenario dialogue evaluation measures a real LLM once a key is configured. The Docker image runs as a non-root user.

macOS (Apple Silicon) is verified locally: tests, a live Uvicorn with a stub model, the browser UI and a widget mock, and an earlier Docker build. The image is Linux-based; CI runs on Ubuntu, but its remote result is not yet confirmed. Windows is not checked; see [Windows and PowerShell](docs/instructions/windows.md). A real LLM and a real amoCRM account are not yet verified.

**Начни с [демонстрации](docs/DEMO.md)** или с [быстрого запуска](docs/instructions/quickstart.md). Интерфейс менеджера после запуска: <http://127.0.0.1:8000>, документация API: <http://127.0.0.1:8000/docs>. Текущее состояние и приоритеты — в [сводке от 27 октября 2026 года](docs/PROJECT_STATUS_2026-10-27.md).

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
- [Windows and PowerShell](docs/instructions/windows.md): Git Bash, WSL or PowerShell; equivalents of the Bash commands used in the guides
- [Using the assistant](docs/instructions/usage.md): manager UI, REST API, response fields, warnings, error codes
- [Knowledge base](docs/instructions/knowledge-base.md): file format, editing without restart, how retrieval uses it
- [amoCRM integration](docs/instructions/amocrm.md): private integration, widget upload, webhooks, server settings
- [Access protection](docs/instructions/access.md): manager login, generation rate limit, what stays public
- [Testing and verification](docs/instructions/testing.md): pytest, manual checks with a stub LLM, Docker smoke check
- [Quality evaluations](docs/instructions/evaluations.md): retrieval suite in CI, dialogue suite with a live LLM, reading the report
- [Резервное копирование и восстановление](docs/instructions/backup.md): что копировать, проверка копии, восстановление базы знаний и настроек
- [Персональные данные](docs/instructions/privacy.md): где проходят данные клиента, что маскируется, сколько хранится и как удалить
- [CI and delivery](docs/instructions/ci-and-delivery.md)
- [Project structure](docs/instructions/project-structure.md)

Stage learning guides in Russian:

- [Stage 01: architecture and project structure](docs/STAGE_01.md)
- [Stage 02: knowledge base and retrieval](docs/STAGE_02.md)
- [Stage 03: LLM and two answer blocks](docs/STAGE_03.md)
- [Stage 04: FastAPI and manager UI](docs/STAGE_04.md)
- [Stage 05: tests and Docker](docs/STAGE_05.md)
- [Stage 06: amoCRM integration](docs/STAGE_06.md)
- [Stage 07: CI and quality checks](docs/STAGE_07.md)
- [Stage 08: evaluations and access protection](docs/STAGE_08.md)
- [Demo walkthrough](docs/DEMO.md)
- [CI/CD and Docker guide](docs/CI_CD.md)
- [Наглядное руководство PDF](docs/guide/amocrm-sales-assistant-guide.pdf), [English PDF guide](docs/guide/amocrm-sales-assistant-guide-en.pdf), [их пересборка](docs/guide/README.md) и [архив прежних изданий](docs/guide/archive/README.md)
- [Полная проверка проекта](docs/VERIFICATION.md)
- [Восстановление после сбоев](docs/RECOVERY.md)
- [Обновление зависимостей](docs/DEPENDENCY_UPDATES.md)
- [Версии и выпуск сервиса и виджета](docs/RELEASES.md)

Design and history:

- [Solution approach](docs/APPROACH.md)
- [Architecture decisions](docs/adr/)
- [Development log](docs/DEVELOPMENT_LOG.md)
- [Состояние проекта на 27 октября 2026 года](docs/PROJECT_STATUS_2026-10-27.md)
