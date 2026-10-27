# ADR 0005: shared local and CI quality checks

- **Status:** Accepted
- **Date:** 2026-10-20

## Context

Stages 01–06 provide the MVP, offline tests and local verification procedures. The repository also needs repeatable code and type checks before further changes. Local success must remain distinguishable from a successful GitHub Actions run and from integration checks against real services.

## Decision

- Add [.github/workflows/ci.yml](../../.github/workflows/ci.yml) for pushes, pull requests and manual dispatch. Use one Ubuntu job on Python 3.12, matching the Docker runtime, with a ten-minute timeout and cancellation of superseded runs for the same workflow/ref.
- Use the official `actions/checkout` and `actions/setup-python` actions pinned to full commit SHAs, with release comments for readability. Grant only `contents: read` and disable checkout credential persistence. Updating an action requires deliberately updating its pinned revision.
- Pin Ruff and mypy in `requirements-dev.txt` alongside pytest; share their configuration through `pyproject.toml`. The workflow installs these development dependencies, then runs the same commands documented for local use.
- Run Ruff over `app`, `tests` and `scripts` with `E4`, `E7`, `E9`, `F` and `I`: code-error and import checks without requiring unrelated formatting changes or line-length changes to prompts and teaching examples.
- Run mypy over all application modules. Check function bodies and signatures, unused ignores, redundant casts and equality comparisons; require an error code on any ignore. Fix optional-value handling and annotate validators, the lifespan generator and FastAPI response metadata. Do not hide modules or missing imports with blanket exclusions. Test fixtures and PDF authoring scripts are outside this initial type-checking scope.
- Run pytest with `FakeLLM` and `httpx.MockTransport`, then validate local documentation links and build `dist/widget.zip`. Tests do not call external services. Installing packages and downloading actions still require network access.
- Keep Docker builds, PDF generation and visual inspection, and real LLM/amoCRM checks outside this workflow. They have separate dependencies or access requirements and remain explicitly recorded in the verification report.

## Consequences

- Developers can reproduce the quality commands locally using [CI and quality checks](../instructions/ci-and-delivery.md). CI requires no provider keys, amoCRM tokens or customer data.
- A successful workflow checks Python code, application typing, the offline test suite, documentation targets and widget packaging. It does not prove model answer quality, operation in a real amoCRM account, container health or PDF layout.
- Local verification passed with Ruff 0.17.1, mypy 2.4.0 over 27 application files and 95 pytest tests. Remote GitHub Actions execution has not yet been verified: the available connector could not read workflow runs and the logged-out browser returned 404 for the repository. This limitation remains separate from local check results.
- Redis for multiple application replicas remains a later change; this stage retains the in-memory message cache and the manager's manual control over customer messages.
