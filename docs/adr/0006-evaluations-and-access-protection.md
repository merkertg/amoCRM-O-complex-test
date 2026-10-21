# ADR 0006: Quality evaluations and access protection

- **Status:** Accepted
- **Date:** 2026-10-21

## Context

Unit tests use `FakeLLM`: they prove that the code handles answers, not that retrieval finds the right facts or that a real model answers well. Retrieval quality changes whenever a manager edits `data/knowledge_base.json`. Answer quality changes with the provider, the model and the prompt, and had never been measured.

The service must run on a public HTTPS address for amoCRM. The manager UI, `/api/v1/suggest` and `/docs` had no authentication, so anyone who found the address could spend the LLM budget. The amoCRM endpoints were already protected by the widget JWT and the webhook secret.

## Decision

- An `evals/` package with two suites:
  - `retrieval.json` — 24 questions with the item expected first and items that must reach the prompt. `scripts/run_evals.py retrieval` runs the real `KnowledgeIndex` offline and exits non-zero below `min_hit_at_1` (0.95) or `min_recall` (1.0). It is a CI step.
  - `dialogues.json` — 12 scenarios with deterministic expectations: upsell decision, clarification, injection flag, allowed and forbidden upsell items, required and forbidden strings, unverified amounts, server-side leak removal. `scripts/run_evals.py dialogues` runs them through the full pipeline with the LLM from `.env` and writes a JSON report with every reply to `reports/evals/`, ignored by Git. It is not a CI step, because it needs a key and costs money.
- The loaders reject unknown knowledge base ids and unknown expectation keys, so a renamed product cannot silently weaken a suite.
- HTTP Basic login for everything except `/health` and `/api/v1/amocrm/*`, enabled by `UI_BASIC_AUTH_USERNAME` and `UI_BASIC_AUTH_PASSWORD` (both or neither, checked at startup). It is a pure ASGI middleware; the browser's own sign-in window means no UI change. Credentials are compared in constant time and never logged.
- A sliding-window `RateLimiter` (default 30 generations per minute) keyed by client IP for `/api/v1/suggest` and by amoCRM account and user for `/api/v1/amocrm/suggest`. Over the limit: `429 rate_limited` with `Retry-After`. Counters live in process memory with a bounded number of keys.

## Consequences

- A knowledge base edit that breaks retrieval fails CI with the name of the item that came first instead.
- The dialogue suite gives a repeatable pass rate for a model, but deterministic rules can pass a reply that a manager would rewrite; the report keeps every reply for review. No live pass rate is recorded yet.
- HTTP Basic is simple and adequate for a small team behind HTTPS. Per-manager accounts, roles or SSO would need a real user store.
- Rate-limit counters, like the amoCRM message cache, require one process and reset on restart; behind a proxy `FORWARDED_ALLOW_IPS` must include the proxy so the client IP is used.
