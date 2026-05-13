# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Common commands

```bash
# Install dependencies
uv sync

# Run any pipeline step
uv run python -m src.cli extrair --ano 2024
uv run python -m src.cli extrair --pdf PDFs/2024/relatorio.pdf
uv run python -m src.cli extrair --limite 3   # smoke test (first 3 PDFs)
uv run python -m src.cli listar
uv run python -m src.cli revisar --gerar
uv run python -m src.cli revisar --aplicar
uv run python -m src.cli build
uv run python -m src.cli publicar

# Preview site locally
python -m http.server -d site 8000
```

There are no automated tests. Smoke-test a change with `--limite 3` on a small PDF set.

## Architecture

### Data flow

```
PDFs/AAAA/*.pdf
  → extract_text.py  (pdfplumber → RelatorioTexto)
  → enrich.py        (regex heuristics → município, órgão, gestor, auditor, relator)
  → parse_2024.py    (deterministic table parser)  ← tries first
       └─ returns None if no 2024-format table found
  → parse_legacy.py  (Gemini API fallback for pre-2024 heterogeneous formats)
  → cache.salvar()   → data/extracted/<sha256>.json

data/extracted/*.json
  → review.py        → data/review.csv   (human edits; key = relatorio_id + codigo)
  → review.py        ← data/review.csv   (only rows with revisado=true are applied back)
  → build_site.py    → site/data.json + data/final.json   (pre-computed aggregations)

site/data.json  ← single payload consumed by the static frontend (vanilla JS)
```

### Parser duality (`parse_2024` vs `parse_legacy`)

- `parse_2024.parse()` returns **`None`** (not an empty list) when no matching table is found — that `None` is the explicit signal to fall through to Gemini. An empty list `[]` means a table was found but had no valid achados.
- `parse_legacy.parse()` sends the relevant PDF text to `gemini-2.0-flash` (or the model in `GEMINI_MODEL`) with a structured JSON prompt. Rate limits are enforced by `rate_limit.py` using `GEMINI_RPM` / `GEMINI_RPD` from `.env`.

### Core data model (`src/schema.py`)

All inter-module contracts go through Pydantic models:
- `RelatorioTexto` — raw PDF extraction (pages, tables, full text, SHA-256)
- `Relatorio` — one report: metadata + list of `Achado` + `fonte_extracao` (`"parser_2024"` | `"gemini_legacy"` | `"pendente_legacy"`)
- `Achado` — one audit finding; `codigo` follows the `III.NN` pattern; `situacao` is the `Situacao` enum that drives all analytics
- `Situacao` enum values: `sanado_total`, `sanado_parcial`, `afastado`, `mantido`, `nao_consta`

### Cache

The cache is keyed by SHA-256 of the PDF file (`data/extracted/<sha256>.json`). Reprocessing is skipped unless `--forcar` is passed. The cache directory is gitignored — only `data/final.json` and `site/` are committed.

### Frontend

The static site (`site/`) is pure HTML + vanilla JS consuming `site/data.json`. `build_site.py` pre-computes all aggregations (by município, tipo, situação, auditor, ano, etc.) so the frontend does no server-side work. GitHub Pages serves the `/site` folder from the `main` branch.

## Claude tooling

- **Skill `pipeline-achados`**: handles all pipeline commands (`extrair`, `revisar`, `build`, `publicar`).
- **Subagent `extrator-achados`**: use during human review when a specific PDF excerpt needs classification (tipo, situação, recomendação, determinação).

## Key conventions

- Package manager: **`uv`** — always use `uv run` or `uv sync`, never bare `pip`.
- All domain identifiers are in **Portuguese** (municipio, achado, relatorio, gestor, etc.).
- `enrich.py` uses regex heuristics on the first ~8 000 chars of the PDF; the municipality list covers AL's 102 municipalities by substring match.
- `data/review.csv` edits are additive: only rows with `revisado=true` overwrite cache entries; unedited rows are left intact on re-generation.
- `.env` is never committed. Copy `.env.example` and fill `GEMINI_API_KEY`.
