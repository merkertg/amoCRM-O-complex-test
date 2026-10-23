# Rebuild and verify the PDF guides

[Project README](../../README.md) · [Verification report](../VERIFICATION.md)

The [Russian guide](amocrm-sales-assistant-guide.pdf) and
[English guide](amocrm-sales-assistant-guide-en.pdf) explain stages 01–08 in
30 sections. They include diagrams, actual repository excerpts, commands,
troubleshooting, self-check questions and the recorded verification results.
The contents page and PDF outline link to every section.

## Earlier editions

The [archive](archive/README.md) preserves earlier PDF editions and identifies
their dates. Use the current guides linked above for the latest instructions.

## Build

Use Python 3.12 or newer from the project root:

```bash
python3.12 -m venv .venv
.venv/bin/python -m pip install -r requirements-guide.txt
.venv/bin/python scripts/build_guide.py
```

For an existing environment, skip its creation. The default builds both
languages; `--lang ru` or `--lang en` rebuilds one. Outputs always go to this
directory, regardless of the working directory.

The builder needs Cyrillic fonts: PT Sans and PT Mono in macOS system fonts,
or DejaVu Sans and DejaVu Sans Mono in `/usr/share/fonts/truetype/dejavu`
on Linux (`fonts-dejavu-core`). Missing fonts cause an explicit build error.
Windows font discovery is not implemented or verified.

## Sources and evidence

- `scripts/build_guide.py`: CLI, cover, introduction and page navigation.
- `scripts/guide/stages_core.py`: sections 03–13.
- `scripts/guide/stages_delivery.py`: sections 14–23.
- `scripts/guide/reference.py`: commands, errors, self-check and results (24–27).
- `scripts/guide/quality.py`: Stage 07 CI and local quality checks (section 28).
- `scripts/guide/evaluation.py`: Stage 08 evaluations and access protection (section 29); runs the offline retrieval suite at build time.
- `scripts/guide/documentation.py`: documentation layers and reading paths (section 30), aligned with AI Support Agent.
- `scripts/guide/diagrams.py`, `layout.py`, `toc.py`, `i18n.py`: drawing,
  layout, headings and language selection.
- `scripts/guide/sources.py`: code excerpts, default settings, retrieval and
  guard examples from the actual repository. Synthetic examples and recorded
  outputs contain fictional data only. Application environment variables and
  `.env` are excluded from the generated examples.
- [verification.json](verification.json): dated check results and limitations.
  `checks` and `http` preserve the original service run, `base_commit` identifies
  its code, and `current_run` describes the latest explicitly executed checks
  against `current_base_commit` plus working changes. A new PDF build does not
  repeat historical browser or Docker checks.

Every new narrative string must be a Russian–English pair through `tr()` or
`{"ru": ..., "en": ...}` in the JSON. Code, prompts, interface text and knowledge
base excerpts remain in their original language in both editions.

The build collects tests to check the count against `verification.json`; it
does **not** execute them. Run pytest separately before refreshing the summary.
Code excerpts wrap long lines for display. Copy executable examples from
the Markdown instructions or source files.

## Verify after changes

Run the service tests and the offline Markdown link checker:

```bash
.venv/bin/python -m pytest
.venv/bin/python scripts/check_docs.py
```

Install Poppler if needed (`brew install poppler` on macOS or
`apt-get install poppler-utils` on Debian/Ubuntu). Render every page:

```bash
mkdir -p /tmp/amocrm-guide-review/ru /tmp/amocrm-guide-review/en
pdfinfo docs/guide/amocrm-sales-assistant-guide.pdf
pdfinfo docs/guide/amocrm-sales-assistant-guide-en.pdf
pdftoppm -r 110 -png docs/guide/amocrm-sales-assistant-guide.pdf /tmp/amocrm-guide-review/ru/page
pdftoppm -r 110 -png docs/guide/amocrm-sales-assistant-guide-en.pdf /tmp/amocrm-guide-review/en/page
pdftotext -layout docs/guide/amocrm-sales-assistant-guide.pdf /tmp/amocrm-guide-review/ru.txt
pdftotext -layout docs/guide/amocrm-sales-assistant-guide-en.pdf /tmp/amocrm-guide-review/en.txt
```

Inspect **all** page images in both languages. Check Cyrillic, arrows, code
line wrapping, table boundaries, diagram labels, headings, page numbers and
blank/orphan pages. Test the contents links and PDF outline; compare the 30
section titles and test count with the sources. Text extraction alone does
not verify layout. Fix issues, rebuild and render again.

Record only completed checks in [VERIFICATION.md](../VERIFICATION.md),
[DEVELOPMENT_LOG.md](../DEVELOPMENT_LOG.md) and `verification.json`. Keep real
LLM, real amoCRM, CI and host-platform limitations explicit. After updating
the summary, rebuild both PDFs and inspect their final pages again. Keep
rendered images in a temporary directory rather than Git.
Generated PDFs are marked binary in `.gitattributes`; review their source
changes and rendered pages instead of a text diff of PDF internals.
