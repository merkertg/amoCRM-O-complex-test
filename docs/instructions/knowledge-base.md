# Knowledge base

[← README](../../README.md) · [All documentation](../../README.md#documentation)

The only source of facts about products, prices and terms. The Russian walkthrough is in the [Stage 02](../STAGE_02.md) guide.

## File

`data/knowledge_base.json`, UTF-8. Top level:

```json
{
  "company": {"name": "...", "description": "...", "working_hours": "..."},
  "products": [ ... ],
  "faq": [ ... ]
}
```

### `products[]`

| Field | Required | Meaning |
| --- | --- | --- |
| `id` | yes | Lowercase Latin letters, digits and `-`; unique; referenced by `related` |
| `type` | yes | `product` or `service` |
| `name`, `category`, `description` | yes | Shown to the model and in the UI |
| `features` | no | Main characteristics |
| `price` | no | `{"amount": 42900, "currency": "₽", "unit": "за комплект", "note": "..."}`; `"amount": null` means the price is not fixed and the assistant must not name one |
| `terms` | no | Conditions: warranty, timing, restrictions |
| `related` | no | Ids of related items: upsell candidates; must exist |
| `upsell_scenarios` | no | When the related items are worth offering; visible to the manager block only |
| `keywords` | no | Synonyms and colloquial words for retrieval |

### `faq[]`

`id`, `topic`, `answer`, `keywords` — general terms such as delivery, payment, warranty, service area, timing, repairs, returns.

## Edit without restart

1. Edit the JSON file and save it.
2. The next request notices the new modification time and reloads the file.
3. Check: `curl http://127.0.0.1:8000/api/v1/knowledge-base`.

If the new file is invalid (broken JSON, duplicate id, unknown `related` id), the service keeps the last valid version and reports the error:

```bash
curl -s http://127.0.0.1:8000/health
```

`"status": "degraded"` and `knowledge_base.last_error` describe the problem. At startup an invalid file stops the service with a clear message.

## How retrieval uses it

- Words are lowercased, `ё` becomes `е`, stop words are dropped, common Russian endings are cut and stems are limited to 6 letters: «установку», «установка», «установить» all become `устано`.
- A number after a word is glued to it: «Бриз 18» becomes `бриз#18`, so «комната 18 м²» does not match the «Бриз 18» model.
- Field weights: `name` and `keywords` ×3, `category` ×2, the rest ×1. The current message weighs 1.0, the last three customer messages 0.5.
- The top `KB_TOP_K` items go to the model with full facts; up to three `related` items are added as upsell candidates. The model also gets a catalogue of names without prices for clarifying questions.

## Tips

- Add colloquial words to `keywords` if a request does not find the right item — check with the UI «Источники» section.
- Write prices only in `price` or `terms`: amounts in the reply that are not in the file are flagged to the manager.
- Keep `upsell_scenarios` concrete: «клиент покупает кондиционер без монтажа → предложить монтаж».
