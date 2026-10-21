# Testing and verification

[← README](../../README.md) · [All documentation](../../README.md#documentation)

Automated tests, manual checks without a real LLM and the Docker smoke check. Results of the last verification are in [VERIFICATION.md](../VERIFICATION.md); the Russian walkthrough is in the [Stage 05](../STAGE_05.md) guide.

## Verify

```bash
source .venv/bin/activate
pytest
```

Expected output:

```text
95 passed in 0.3s
```

Tests need no network and no keys: the LLM is replaced by `FakeLLM` (`tests/conftest.py`), the LLM provider and amoCRM HTTP calls by `httpx.MockTransport`.

| File | Tests | What it checks |
| --- | --- | --- |
| `tests/test_knowledge_base.py` | 19 | Schema validation, hot reload, broken file, stemming, retrieval ranking, related items |
| `tests/test_guards.py` | 24 | Prompt injection detection and false positives, sanitising, PII masking, leak stripping, unverified amounts, upsell rules, history parsing |
| `tests/test_assistant.py` | 13 | The whole pipeline: both blocks, too little information, inappropriate upsell, invented prices, JSON repair, injection isolation, PII before LLM |
| `tests/test_llm_client.py` | 13 | Payload, retries on 429/5xx/timeouts, no retry on 401/400, malformed provider answers, no secrets in logs |
| `tests/test_api.py` | 10 | REST API, error codes, no input echo, no personal data in logs, UI and docs served |
| `tests/test_amocrm.py` | 16 | Webhook parsing and deduplication, widget JWT checks, context from webhooks, amoCRM API failures |

Run one file or one test:

```bash
pytest tests/test_assistant.py -v
pytest -k injection -v
```

## Manual check without an LLM key

A stub OpenAI-compatible server lets you click through the UI. Save as `/tmp/stub_llm.py`:

```python
import json

from fastapi import FastAPI

app = FastAPI()
ANSWER = {
    "customer_reply": "Здравствуйте! «Бриз 09» стоит 42 900 ₽, монтаж — 9 900 ₽.",
    "needs_clarification": False,
    "upsell_applicable": True,
    "upsell_product_id": "wifi-module",
    "upsell_recommendation": "Wi-Fi модуль",
    "upsell_reason": "При монтаже модуль ставится бесплатно.",
    "suggested_sales_phrase": "Можем сразу поставить Wi-Fi модуль за 3 500 ₽.",
}


@app.post("/v1/chat/completions")
def completions() -> dict:
    content = json.dumps(ANSWER, ensure_ascii=False)
    return {"choices": [{"message": {"content": content}}]}
```

```bash
uvicorn --app-dir /tmp stub_llm:app --port 9100
LLM_BASE_URL=http://127.0.0.1:9100/v1 LLM_MODEL=stub uvicorn app.main:app --port 8000
```

Run the two commands in separate terminal tabs, then open <http://127.0.0.1:8000>.

## Docker smoke check

```bash
docker build -t amocrm-sales-assistant:test .
docker run -d --rm --name assistant-smoke -p 18000:8000 amocrm-sales-assistant:test
curl -s http://127.0.0.1:18000/health
docker exec assistant-smoke id
docker stop assistant-smoke
```

Expected: `/health` answers `"status":"ok"`, `id` shows `uid=10001(appuser)` — the service does not run as root.

## Widget archive

```bash
python scripts/build_widget.py
unzip -l dist/widget.zip
```

The script fails if a required file or a locale from `manifest.json` is missing.

## PDF guide

See [docs/guide/README.md](../guide/README.md): build both languages, render every page and check them visually.

```bash
.venv/bin/python -m pip install -r requirements-guide.txt
.venv/bin/python scripts/build_guide.py
.venv/bin/python scripts/check_docs.py
```

The link checker verifies local Markdown targets and heading anchors without
network access. The guide builder collects tests to check the recorded count;
it does not run pytest or repeat the recorded browser/Docker checks. Guide
examples use repository defaults, ignoring `.env` and environment overrides.

## CI and code quality

The same local checks run in [GitHub Actions](../../.github/workflows/ci.yml):

```bash
.venv/bin/python -m ruff check app tests scripts
.venv/bin/python -m mypy app
.venv/bin/python -m pytest
.venv/bin/python scripts/check_docs.py
.venv/bin/python scripts/build_widget.py
```

Install `requirements-dev.txt` first. Ruff checks code errors and import
ordering across the application, tests and scripts. Mypy requires typed
function signatures and checks bodies across all application modules;
tests and PDF scripts are outside its initial scope.
See [CI instructions](ci.md) and the Russian [Stage 07 guide](../STAGE_07.md).
Remote Actions results are recorded separately from local checks.
