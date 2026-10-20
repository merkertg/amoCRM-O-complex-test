# ADR 0001: Application layout and tooling

- **Status:** Accepted
- **Date:** 2026-10-20

## Context

The specification asks for a simple working MVP on Python 3.12+, FastAPI, Pydantic, HTTPX, pytest and Docker, with business logic, API, knowledge base access, LLM client and amoCRM integration in independent modules, and without agents, microservices, queues or vector databases.

## Decision

- One FastAPI service; the code lives in the `app/` package at the repository root and is started with `uvicorn app.main:app`.
- Modules by responsibility: `api` (HTTP), `core` (business logic), `knowledge` (knowledge base), `llm` (model client), `integrations/amocrm` (CRM adapter). Dependencies point inwards: `core` imports neither FastAPI nor HTTPX nor amoCRM code.
- `DialogContext` is the only input of the business logic; the API and the amoCRM adapter both build it.
- `AppError` subclasses carry the HTTP status, a machine code and a message for the manager; one exception handler turns them into `{"error": {"code", "message"}}`.
- `create_app(settings, llm_client, amocrm_client)` wires dependencies explicitly so tests pass fakes without monkeypatching.
- Settings come from the environment and `.env` through pydantic-settings; secrets are `SecretStr`.
- Dependencies are pinned in `requirements.txt` (runtime) and `requirements-dev.txt` (+ pytest) and installed with pip into `.venv` or the Docker image.
- pytest finds the package through `[tool.pytest.ini_options] pythonpath = ["."]`.

## Consequences

- No build step and no packaging; the same commands work in `.venv` and in Docker.
- pip does not lock transitive dependencies. If reproducibility of the whole tree becomes important, move to uv with `uv.lock`, as in the other AI Forge projects.
- There is no linter, type checker or CI yet; they are listed as next steps.
