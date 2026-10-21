# CI and code quality

[← README](../../README.md) · [All documentation](../../README.md#documentation)

Run the same checks locally and in GitHub Actions. The detailed Russian
walkthrough is [Stage 07](../STAGE_07.md). The workflow is
[`.github/workflows/ci.yml`](../../.github/workflows/ci.yml); tool settings
are in [`pyproject.toml`](../../pyproject.toml).

## Local check

From the project root, create a Python 3.12 environment if needed:

```bash
python3.12 -m venv .venv
.venv/bin/python -m pip install -r requirements-dev.txt
.venv/bin/python -m ruff check app tests scripts
.venv/bin/python -m mypy app
.venv/bin/python -m pytest
.venv/bin/python scripts/check_docs.py
.venv/bin/python scripts/build_widget.py
```

Installing dependencies needs network access unless the packages are already
available in a local cache. The checks use no LLM or amoCRM credentials.
Tests replace the LLM with `FakeLLM` and HTTP with `httpx.MockTransport`;
`TestClient` invokes the application without a listening network port.

## What each check covers

| Check | Scope | A successful result means |
| --- | --- | --- |
| Ruff 0.17.1 | `app`, `tests`, `scripts`; `E4`, `E7`, `E9`, `F`, `I` | No selected syntax, code-error or import-order violations; no formatter gate is enabled |
| mypy 2.4.0 | All 27 Python modules in `app` | Function definitions are annotated and function bodies are checked under the configured options; tests and PDF scripts are outside this type-checking scope |
| pytest | The six files under `tests` | The current 95 service tests pass using fakes and mock transports |
| Documentation links | `README.md`, `AGENTS.md`, Markdown under `docs` | Local destinations and Markdown anchors exist; external URLs are skipped |
| Widget archive | `amocrm_widget` | Required files and locale JSON exist and parse; `dist/widget.zip` is created |

Ruff and mypy are development dependencies pinned in
[`requirements-dev.txt`](../../requirements-dev.txt). A type-check pass does
not prove the factual quality of model responses. Packaging the widget does
not verify installation in a real amoCRM account.

## GitHub Actions

The workflow runs on every `push`, every `pull_request` and manual
`workflow_dispatch`; there is no branch filter. The single job uses
`ubuntu-latest`, Python 3.12 and a ten-minute timeout. A newer run cancels an
older run for the same workflow and ref.

Checkout and Python setup actions are pinned to full commit SHAs; their
version comments identify v7. The workflow has `contents: read` permission,
does not persist checkout credentials and does not use application secrets.
It installs `requirements-dev.txt`, then runs the five checks in the order
shown above. If a step fails, later checks are skipped.

After pushing, open [the repository's Actions page](https://github.com/merkertg/amoCRM-O-complex-test/actions),
select **CI**, choose the run for the intended commit and inspect every
step. A local pass and a workflow file do not establish a remote CI pass;
record the actual run result in [VERIFICATION.md](../VERIFICATION.md).

## If a check fails

| Failure | Next action |
| --- | --- |
| Dependency installation | Check the Python version, package index availability and the first pip error; later checks have not run |
| Ruff `I001` | Review import ordering; `python -m ruff check app tests scripts --fix` may help, but review its diff and rerun the checks |
| Another Ruff error | Read the file, line and rule code; fix the cause rather than disabling the whole rule group |
| mypy error | Read the expected and actual types; add annotations or narrow an optional value before using it |
| pytest failure | Reproduce with `python -m pytest path/to/test_file.py -v`; keep real LLM and amoCRM calls out of tests |
| Broken documentation link | Fix the relative destination or heading anchor shown by `check_docs.py` |
| Widget build failure | Restore the required file or valid locale/manifest JSON, then rebuild |
| Cancelled run | Open the newer run for the same ref; cancellation is not a passing result |

## Separate manual checks

PDF generation and page-by-page visual review remain manual: follow
[the guide rebuild instructions](../guide/README.md). CI does not install
the PDF authoring requirements or render PDFs. Live LLM quality, a real
amoCRM account, browser scenarios and Docker checks require their own
verification; see [testing](testing.md) and [VERIFICATION.md](../VERIFICATION.md).
