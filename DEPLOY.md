# Deploy no GitHub Pages

## Primeira vez

1. Criar repositório público no GitHub.
2. Configurar remote e fazer push inicial:
   ```powershell
   git remote add origin https://github.com/<seu-usuario>/pc-governo-analise-historica.git
   git push -u origin main
   ```
3. Criar o branch `gh-pages` com os arquivos do site:
   ```powershell
   $sha = git subtree split --prefix site HEAD
   git push origin "${sha}:refs/heads/gh-pages"
   ```
4. No GitHub: **Settings → Pages**
   - Source: `Deploy from a branch`
   - Branch: `gh-pages` · `/` (raiz)
   - Salvar.
5. Aguardar ~1 min. URL: `https://<seu-usuario>.github.io/pc-governo-analise-historica/`.

## Atualizações periódicas

Sempre que processar novos PDFs:
```
uv run python -m src.cli extrair --ano 2024
uv run python -m src.cli revisar --gerar      # edita data/review.csv
uv run python -m src.cli revisar --aplicar
uv run python -m src.cli build
uv run python -m src.cli publicar             # faz push do main + atualiza gh-pages
```

O comando `publicar` atualiza automaticamente o branch `gh-pages` com o conteúdo de `site/`.

## Notas

- `data/extracted/` está no `.gitignore` (cache local). O que vai pro repositório é apenas `site/data.json` e `data/final.json` (revisados).
- `PC_Gov_*.xlsx`, `.env` e `.claude/` nunca entram no Git.
- O branch `gh-pages` contém exclusivamente os arquivos do portal estático.
