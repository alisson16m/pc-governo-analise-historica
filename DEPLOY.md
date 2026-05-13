# Deploy no GitHub Pages

## Primeira vez

1. Criar repositório público no GitHub (ex: `pc-governo-analise-historica`).
2. No diretório do projeto:
   ```powershell
   git init -b main
   git remote add origin https://github.com/<seu-usuario>/pc-governo-analise-historica.git
   git add .
   git commit -m "primeira versão"
   git push -u origin main
   ```
3. No GitHub: **Settings → Pages**
   - Source: `Deploy from a branch`
   - Branch: `main` · `/site`
   - Salvar.
4. Aguardar ~1 min. URL: `https://<seu-usuario>.github.io/pc-governo-analise-historica/`.

## Atualizações periódicas

Sempre que processar novos PDFs:
```
uv run python -m src.cli extrair --ano 2024
uv run python -m src.cli revisar --gerar      # edita data/review.csv
uv run python -m src.cli revisar --aplicar
uv run python -m src.cli build
uv run python -m src.cli publicar
```

## Notas

- `data/extracted/` está no `.gitignore` (cache local, contém SHA dos PDFs e dados brutos pré-revisão). O que vai pro repositório é apenas `site/data.json` e `data/final.json` (revisados).
- Se quiser que o cache fique versionado (para reproducibilidade), edite o `.gitignore` removendo `data/extracted/`.
- `.env` jamais entra no Git.
