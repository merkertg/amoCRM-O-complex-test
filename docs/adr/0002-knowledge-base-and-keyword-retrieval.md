# ADR 0002: JSON knowledge base and keyword retrieval

- **Status:** Accepted
- **Date:** 2026-10-20

## Context

The knowledge base holds tens of products, services and general terms. It must be editable without changing Python code. The model must use only its facts, and the server must be able to check recommendations and prices against it. The specification says a full vector database is not needed for a small knowledge base.

## Decision

- Store the knowledge base in `data/knowledge_base.json` and validate it with Pydantic models: required fields, `id` format, unique ids, `related` ids that exist, `price.amount` may be `null` for prices that are not fixed.
- Reload the file when its modification time changes; if the new file is invalid, keep serving the last valid version and expose the error in `/health`. An invalid file at startup stops the service.
- Retrieve with a weighted keyword index: lowercase, `ё → е`, stop words, a light Russian stemmer (cut one common ending, keep up to 6 letters), word + number glued into one token (`бриз#18`), field weights (name and keywords ×3, category ×2, other ×1), IDF, and lower weight for the previous customer messages.
- Add up to three `related` items of the matched products as upsell candidates and give the model a names-only catalogue for clarifying questions.

## Consequences

- Retrieval is deterministic, explainable and fast; results are visible to the manager as «sources».
- Synonyms must be added to `keywords`; there is no semantic matching of unseen words.
- For thousands of items, move to a full-text engine or embeddings behind the same `KnowledgeIndex.search()` interface.
