# ADR 0004: amoCRM widget with one-time JWT and a webhook message cache

- **Status:** Accepted
- **Date:** 2026-10-20

## Context

The main scenario is a manager calling the assistant while working with a conversation, with both blocks shown inside amoCRM. The official documentation shows:

- REST API v4 returns leads, contacts, notes; the Talks API returns talk metadata only; the Events API returns `incoming_chat_message` / `outgoing_chat_message` with a message id but no text.
- The Chats API returns history only for the integration's own registered channel.
- Webhooks `message[add]` and `outgoing_message[add]` carry the message text, the contact and the linked entity; amoCRM waits up to 2 seconds and disables a hook after repeated failures.
- Widgets run JavaScript in documented locations (`lcard`, `ccard`, `card_sdk`, `everywhere`, ...). There is no location inside the chat window and no documented API to put text into the chat input. `this.$authorizedAjax()` adds `X-Auth-Token`, a JWT signed with the integration secret key (HS256) with `iss`, `aud`, `jti`, `iat`, `nbf`, `exp`, `account_id`, `user_id`, `client_uuid`.

## Decision

- A widget in the lead card right panel (`lcard-1`) with an optional text field and a «generate» button; it calls `POST /api/v1/amocrm/suggest` through `$authorizedAjax` and renders model text with `.text()` / `.val()` only.
- The backend verifies the token signature, expiry, `client_uuid == AMOCRM_CLIENT_ID` and the `iss` host against `AMOCRM_BASE_URL`.
- A webhook endpoint stores incoming and outgoing chat messages in an in-memory `MessageStore` keyed by lead and contact, with deduplication, a per-key limit and a TTL; it never calls the LLM.
- `AmoCRMAdapter` builds `DialogContext`: the field text or the trailing customer messages as the current message, cached history, and only the first name of the main contact from REST API v4. If the API fails, it continues with a warning.
- The webhook secret is a query parameter; access logs drop query strings and client IPs.

## Consequences

- The manager copies the reply into the chat; this also enforces «the manager sends».
- History exists only from the moment webhooks were enabled; older messages are pasted manually.
- The cache requires a single process; Redis is needed for replicas.
- Not verified on a real amoCRM account; verified with tests and a page that loads the real `script.js`, signs a JWT and calls the backend from another origin.
