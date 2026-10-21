# Quality evaluations

[← README](../../README.md) · [All documentation](../../README.md#documentation)

Two evaluation suites complement the unit tests. Tests check that the code handles answers correctly; evaluations check how well the assistant finds facts and how a real model answers. The Russian walkthrough is in the [Stage 08](../STAGE_08.md) guide.

| Suite | File | Needs | Runs in CI | Measures |
| --- | --- | --- | --- | --- |
| Retrieval | [`evals/retrieval.json`](../../evals/retrieval.json) | nothing | yes | Whether the right knowledge base item comes first (hit@1) and required items reach the prompt (recall) |
| Dialogues | [`evals/dialogues.json`](../../evals/dialogues.json) | an LLM from `.env` | no | The structured answer of a real model on 12 scenarios |

## Retrieval suite

```bash
.venv/bin/python scripts/run_evals.py retrieval
```

Expected output ends with:

```text
hit@1 1.000 (порог 0.95) · recall 1.000 (порог 1.0) · вопросов 24
Результат: PASS
```

Each case has a question, an optional earlier customer message (`context`), the item expected first (`expected_first`) and items that must reach the prompt (`must_include`). The command ignores `.env` and uses the repository knowledge base. It exits with code 1 if hit@1 or recall falls below `thresholds`.

Run it after every change to `data/knowledge_base.json` or `app/knowledge/search.py`. A failing case names the item that came first instead: add synonyms to its `keywords` or to the expected item, then rerun.

## Dialogue suite

Configure a model in `.env` (see [Quickstart](quickstart.md#configure-the-llm)), then:

```bash
.venv/bin/python scripts/run_evals.py dialogues
```

Output format — a real run against the stub OpenAI-compatible server from [Testing](testing.md#manual-check-without-an-llm-key), which returns one fixed purchase answer to every question, so unrelated scenarios fail:

```text
PASS purchase-bedroom       Покупка с монтажом — допродажа уместна
FAIL unclear-price          Мало информации — уточняющий вопрос
     - upsell_applicable=True, ожидалось False
     - needs_clarification=False, ожидалось True
     - в ответе есть «42 900»
FAIL complaint-leak         Жалоба на поломку — допродажа неуместна
     - upsell_applicable=True, ожидалось False
     - в ответе нет ни одного из ['диагност', 'мастер']
…
PASS unknown-product        Товара нет в базе: увлажнитель
…
Пройдено 3 из 12 (25%), порог 80%. Отчёт: reports/evals/dialogues-<время>.json
```

The stub only shows that the runner, the HTTP client, the checks and the exit code work. `unknown-product` passes even with this unrelated answer: deterministic rules catch known mistakes, not every bad reply. The pass rate of a real model is not recorded yet.

Each scenario goes through the full pipeline: retrieval, prompt, LLM, validation and guards. Expectations are deterministic:

| Key | Fails when |
| --- | --- |
| `upsell_applicable`, `needs_clarification`, `injection_suspected` | The answer has a different value |
| `allowed_upsell` | An upsell is offered outside this list |
| `forbidden_upsell` | This item is offered (for example, the product the customer asks about) |
| `reply_contains_any` | The reply contains none of these strings (case-insensitive) |
| `reply_not_contains` | The reply contains any of these strings |
| `max_unverified_amounts` | More amount warnings than allowed (default 0) |
| `allow_removed_leaks` | `false` by default: a server-side leak removal is a failure |

Options:

```bash
.venv/bin/python scripts/run_evals.py dialogues --case return-request --case installment
.venv/bin/python scripts/run_evals.py dialogues --min-pass-rate 1.0 --report /tmp/run.json
```

The command exits with code 1 below `--min-pass-rate` (default 0.8) and code 2 without a configured model. Every run sends 12 paid requests or more (a repair attempt adds one).

## Reading the report

`reports/evals/dialogues-<time>.json` holds the model name, the API host, pass counts and, for every scenario, the failures, the customer reply, the upsell decision and the warnings. `reports/` is ignored by Git. Read the replies, not only the PASS marks: a rule set can pass a reply that a manager would still rewrite.

The suites contain fictional demo dialogues only. Do not add real customer conversations to them or to reports.

## Changing the suites

- Case ids are unique; product ids in `expect` and `expected_first` must exist in the knowledge base — the loader rejects unknown ids and unknown expectation keys.
- Prefer stable facts (`"42 900"`) over wording in `reply_contains_any`; models phrase replies differently.
- `tests/test_evals.py` checks that both files load and that the retrieval suite passes its thresholds.
