# ADR 0003: OpenAI-compatible client, structured output and server-side guards

- **Status:** Accepted
- **Date:** 2026-10-20

## Context

The specification requires an OpenAI-compatible LLM API, a structured JSON answer with `customer_reply`, `upsell_recommendation`, `upsell_reason`, `suggested_sales_phrase` and `upsell_applicable`, handling of API errors, timeouts and invalid model output, protection against prompt injection and a guarantee that internal recommendations do not reach the customer reply.

## Decision

- Call `POST {LLM_BASE_URL}/chat/completions` with HTTPX instead of a vendor SDK, so any compatible provider (OpenAI, OpenRouter, DeepSeek, Ollama, vLLM) works. `temperature`, `max_tokens` and `response_format: json_object` are configurable because some models reject them.
- Retry with exponential backoff on timeouts, network errors, 429 and 5xx; do not retry 401/403 and other 4xx. Each failure is an `LLMError` subclass with its HTTP status and message.
- Depend on an `LLMClient` protocol (`model`, `async complete(messages)`), not on the class.
- Ask for one JSON object; strip Markdown fences, extract the outer object, validate it with the `Suggestion` model. On failure send one repair message that names the problem; on a second failure return `502 llm_invalid_output`.
- Add `upsell_product_id` and `needs_clarification` to the required fields: the id lets the server check the recommendation against the knowledge base.
- Apply guards after validation: upsell only for an existing item (name taken from the file, fields cleared when not applicable); remove sentences with internal wording or copies of the hint from the customer reply; flag amounts and percentages that are neither in the knowledge base nor in the conversation (a sum of two known prices is accepted).
- Treat customer data as untrusted: tagged blocks, removal of prompt tags and control characters, heuristic injection detection that adds a warning and a notice to the model, PII masking before the LLM.

## Consequences

- Guards warn rather than block, so a manager still gets an answer when a heuristic fires; the final decision stays with the manager.
- Heuristics can miss new injection phrasings; the main protection is that the model has no tools and every answer is reviewed by a person.
- Answer quality depends on the chosen model and is not covered by the tests, which use a fake LLM.
