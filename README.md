# Portal de Prestações de Contas + Banco de Achados (TCE-AL)

Pipeline que extrai dados estruturados dos relatórios conclusivos de prestações de contas (PDFs) e publica um portal estático com indicadores e o Banco de Achados.

## Pré-requisitos

- Python 3.11+
- [uv](https://docs.astral.sh/uv/) (gerenciador de pacotes)
- Chave gratuita do Gemini API (https://aistudio.google.com/apikey) — apenas para relatórios pré-2024

## Setup

```bash
uv sync
cp .env.example .env   # preencha GEMINI_API_KEY
```

## Fluxo de uso

```bash
# 1. Coloque os PDFs em PDFs/2023/ ou PDFs/2024/
# 2. Extrair achados
uv run python -m src.cli extrair --ano 2024
uv run python -m src.cli extrair --ano 2023

# 3. Gerar planilha de revisão
uv run python -m src.cli revisar --gerar

# 4. Editar data/review.csv (marcar revisado=true nas linhas conferidas)
# 5. Aplicar revisão
uv run python -m src.cli revisar --aplicar

# 6. Construir o portal
uv run python -m src.cli build

# 7. Visualizar local
python -m http.server -d site 8000

# 8. Publicar no GitHub Pages
uv run python -m src.cli publicar
```

## Estrutura

- `src/` — pipeline Python
- `PDFs/AAAA/` — entrada (não versionada)
- `data/extracted/` — JSON bruto (não versionado)
- `data/final.json` — fonte da verdade pós-revisão
- `site/` — portal estático servido pelo GitHub Pages
- `.claude/` — skill `pipeline-achados` e subagente `extrator-achados`

Plano completo: ver `~/.claude/plans/os-relat-rios-das-presta-es-inherited-tower.md`.
