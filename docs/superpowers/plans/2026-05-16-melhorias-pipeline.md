# Melhorias do Pipeline PCG — Plano de Implementação

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Corrigir bugs de confiabilidade, adicionar observabilidade e evoluir o produto em três fases sequenciais sem quebrar o pipeline existente.

**Architecture:** Pipeline Python com 13 módulos em `src/`. Sem testes automatizados — smoke test padrão é `uv run python -m src.cli extrair --limite 3`. Cada tarefa termina com um smoke test e um commit. As fases são sequenciais; as tarefas dentro de cada fase são independentes entre si.

**Tech Stack:** Python 3.11+, uv, pdfplumber, Pydantic v2, Gemini API (google-genai), Rich, Typer, HTML+JS vanilla (site-v3)

**Spec:** `docs/superpowers/specs/2026-05-16-melhorias-pipeline-design.md`

---

## Mapa de arquivos

| Arquivo | Tarefas que o modificam |
|---|---|
| `src/rate_limit.py` | T1 (filelock), T11 (decorator) |
| `src/enrich.py` | T2 (município) |
| `src/cli.py` | T3 (RuntimeError), T8 (diagnosticar), T10 (paralelização) |
| `src/cache.py` | T4 (validação JSON) |
| `src/extract_text.py` | T5 (aviso tabela) |
| `pyproject.toml` | T1 (filelock dep) |
| `src/parse_legacy.py` | T11 (remover _coagir_situacao, usar decorator) |
| `src/parse_contraditorio.py` | T11 (usar decorator) |
| `docs/guia-revisao-csv.md` | T7 (arquivo novo) |
| `site-v3/achados.html` | T9 (busca) |
| `site-v3/app.js` | T9 (busca) |

---

## FASE 1 — Confiabilidade

---

### Tarefa 1: Adicionar filelock ao rate_limit.py

**O que faz:** Protege o arquivo `data/.gemini_state.json` contra escrita simultânea de dois processos.

**Arquivos:**
- Modificar: `pyproject.toml`
- Modificar: `src/rate_limit.py`

- [ ] **Passo 1: Adicionar `filelock` às dependências**

Abrir `pyproject.toml` e adicionar `"filelock>=3.13.0"` à lista `dependencies`, após `"openpyxl>=3.1.5"`:

```toml
dependencies = [
    "pdfplumber>=0.11.0",
    "pypdf>=4.3.0",
    "pydantic>=2.7.0",
    "google-genai>=1.0.0",
    "pandas>=2.2.0",
    "typer>=0.12.0",
    "python-dotenv>=1.0.1",
    "rich>=13.7.0",
    "openpyxl>=3.1.5",
    "filelock>=3.13.0",
]
```

- [ ] **Passo 2: Instalar a dependência**

```bash
uv sync
```

Esperado: linha `+ filelock X.Y.Z` na saída sem erros.

- [ ] **Passo 3: Adicionar FileLock ao rate_limit.py**

Substituir o conteúdo completo de `src/rate_limit.py` por:

```python
"""Rate-limit local para respeitar a cota gratuita do Gemini."""
from __future__ import annotations

import json
import os
import time
from datetime import date
from pathlib import Path

from filelock import FileLock

STATE = Path("data/.gemini_state.json")
_LOCK = FileLock(str(STATE) + ".lock")

_ESTADO_PADRAO = {"dia": "", "rpd": 0, "ultimo_request": 0.0, "esgotado": False}


def _ler() -> dict:
    with _LOCK:
        if not STATE.exists():
            return dict(_ESTADO_PADRAO)
        try:
            return json.loads(STATE.read_text(encoding="utf-8"))
        except Exception:
            return dict(_ESTADO_PADRAO)


def _escrever(d: dict) -> None:
    with _LOCK:
        STATE.parent.mkdir(parents=True, exist_ok=True)
        STATE.write_text(json.dumps(d), encoding="utf-8")


def aguardar() -> None:
    """Aguarda o intervalo mínimo entre requisições (RPM) e verifica a cota diária."""
    rpm = int(os.getenv("GEMINI_RPM", "15"))
    rpd = int(os.getenv("GEMINI_RPD", "1000"))
    minimo_intervalo = 60.0 / max(rpm, 1)
    hoje = date.today().isoformat()

    s = _ler()
    if s.get("dia") != hoje:
        s = {"dia": hoje, "rpd": 0, "ultimo_request": 0.0, "esgotado": False}
        _escrever(s)

    if s.get("esgotado"):
        raise RuntimeError("Cota diária do Gemini esgotada (erro 429 recebido). Tente amanhã.")

    if s["rpd"] >= rpd:
        raise RuntimeError(f"Cota diária do Gemini atingida ({rpd} req/dia). Tente amanhã.")

    delta = time.time() - float(s.get("ultimo_request") or 0.0)
    if delta < minimo_intervalo:
        time.sleep(minimo_intervalo - delta)


def marcar_sucesso() -> None:
    """Incrementa o contador após uma chamada bem-sucedida."""
    s = _ler()
    hoje = date.today().isoformat()
    if s.get("dia") != hoje:
        s = {"dia": hoje, "rpd": 0, "ultimo_request": 0.0, "esgotado": False}
    s["ultimo_request"] = time.time()
    s["rpd"] = int(s.get("rpd", 0)) + 1
    _escrever(s)


def marcar_esgotado() -> None:
    """Sinaliza que a cota diária foi esgotada (erro 429) para parar o processamento."""
    s = _ler()
    s["esgotado"] = True
    _escrever(s)


def estado_atual() -> dict:
    """Retorna o contador RPD do dia atual e o limite configurado."""
    rpd_max = int(os.getenv("GEMINI_RPD", "1000"))
    s = _ler()
    hoje = date.today().isoformat()
    rpd_usado = int(s.get("rpd", 0)) if s.get("dia") == hoje else 0
    return {"rpd_usado": rpd_usado, "rpd_max": rpd_max}


def aguardar_e_marcar() -> None:
    aguardar()
    marcar_sucesso()
```

- [ ] **Passo 4: Smoke test**

```bash
uv run python -m src.cli extrair --limite 3
```

Esperado: pipeline roda sem erros; arquivo `data/.gemini_state.json.lock` pode aparecer e ser removido automaticamente.

- [ ] **Passo 5: Commit**

```bash
git add pyproject.toml uv.lock src/rate_limit.py
git commit -m "fix: adiciona filelock ao rate_limit para evitar race condition"
```

---

### Tarefa 2: Corrigir detecção de município em enrich.py

**O que faz:** Ordena a lista de municípios por comprimento (mais específicos primeiro) e usa word boundary para evitar match parcial.

**Arquivos:**
- Modificar: `src/enrich.py`

- [ ] **Passo 1: Substituir a função `detectar_municipio`**

Localizar as linhas 66–75 de `src/enrich.py` (função `detectar_municipio`) e substituir por:

```python
# Ordena por comprimento decrescente para testar nomes mais específicos primeiro
# (ex: "São Luís do Quitunde" antes de "Luís").
_MUNICIPIOS_SORTED: tuple[str, ...] = tuple(
    sorted(MUNICIPIOS_AL, key=len, reverse=True)
)


def detectar_municipio(texto: str) -> Optional[str]:
    for m in _MUNICIPIOS_SORTED:
        if re.search(r"\b" + re.escape(m) + r"\b", texto, re.IGNORECASE):
            return m
    return None
```

**Atenção:** A variável `_MUNICIPIOS_SORTED` deve ser definida logo após a constante `MUNICIPIOS_AL` (linha ~37), antes da função. A função `detectar_municipio` substitui a que existia a partir da linha 66. Remova as linhas antigas da função.

- [ ] **Passo 2: Verificar manualmente com texto de teste**

```bash
uv run python -c "
from src.enrich import detectar_municipio
# Não deve detectar nenhum município em palavras comuns
print(detectar_municipio('Empresarial'))          # esperado: None
print(detectar_municipio('Porto Real do Colégio')) # esperado: Porto Real do Colégio
print(detectar_municipio('São Luís do Quitunde'))  # esperado: São Luís do Quitunde
print(detectar_municipio('Maceió'))                # esperado: Maceió
"
```

Esperado: saídas conforme os comentários acima.

- [ ] **Passo 3: Smoke test**

```bash
uv run python -m src.cli extrair --limite 3
```

Esperado: sem erros; municípios nos relatórios continuam sendo detectados.

- [ ] **Passo 4: Commit**

```bash
git add src/enrich.py
git commit -m "fix: corrige detecção de município com word boundary e ordenação por comprimento"
```

---

### Tarefa 3: Tornar o except RuntimeError específico em cli.py

**O que faz:** Garante que erros inesperados de outros módulos não sejam silenciados junto com os erros de cota Gemini.

**Arquivos:**
- Modificar: `src/cli.py`

- [ ] **Passo 1: Localizar o bloco e substituir**

Localizar em `src/cli.py` as linhas (aproximadamente 139–149) dentro de `_aplicar_contraditorio`:

```python
            except RuntimeError:
                pass  # cota Gemini esgotada; resumos gerados depois via backfill-resumo
```

Substituir por:

```python
            except RuntimeError as _e:
                if "cota" in str(_e).lower() or "quota" in str(_e).lower():
                    pass  # cota Gemini esgotada; resumos via backfill-resumo
                else:
                    raise
```

- [ ] **Passo 2: Smoke test**

```bash
uv run python -m src.cli extrair --limite 3
```

Esperado: pipeline funciona normalmente.

- [ ] **Passo 3: Commit**

```bash
git add src/cli.py
git commit -m "fix: captura RuntimeError de cota Gemini de forma específica em cli.py"
```

---

### Tarefa 4: Validar JSON antes de salvar no cache

**O que faz:** Impede que um arquivo JSON inválido seja gravado em disco.

**Arquivos:**
- Modificar: `src/cache.py`

- [ ] **Passo 1: Adicionar import de json e substituir a função `salvar`**

No topo de `src/cache.py`, o import `json` já existe. Substituir a função `salvar` (linhas 29–35) por:

```python
def salvar(rel: Relatorio) -> Path:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    p = caminho(rel.id)
    tmp = p.with_suffix(".tmp")
    json_str = rel.model_dump_json(indent=2)
    try:
        json.loads(json_str)
    except json.JSONDecodeError as e:
        raise ValueError(f"JSON inválido gerado para {p.name}: {e}") from e
    tmp.write_text(json_str, encoding="utf-8")
    tmp.replace(p)
    return p
```

- [ ] **Passo 2: Smoke test**

```bash
uv run python -m src.cli extrair --limite 3
```

Esperado: pipeline funciona; arquivos de cache continuam sendo salvos.

- [ ] **Passo 3: Commit**

```bash
git add src/cache.py
git commit -m "fix: valida JSON gerado antes de gravar no cache"
```

---

### Tarefa 5: Avisar quando tabela de PDF não puder ser extraída

**O que faz:** Emite aviso visível no terminal quando uma tabela de PDF falha em vez de falhar silenciosamente.

**Arquivos:**
- Modificar: `src/extract_text.py`

- [ ] **Passo 1: Adicionar import de console e substituir o bloco try/except**

Adicionar ao topo de `src/extract_text.py` (após os imports existentes):

```python
from rich.console import Console as _Console
_console = _Console(legacy_windows=False)
```

Localizar o bloco try/except dentro de `extrair()` (aproximadamente linhas 49–52):

```python
            try:
                tabelas = page.extract_tables() or []
            except Exception:
                tabelas = []
```

Substituir por:

```python
            try:
                tabelas = page.extract_tables() or []
            except Exception as _exc:
                _console.print(
                    f"[yellow]⚠ Tabela ignorada: {caminho.name} p.{i} — {_exc}[/yellow]"
                )
                tabelas = []
```

- [ ] **Passo 2: Smoke test**

```bash
uv run python -m src.cli extrair --limite 3
```

Esperado: pipeline funciona; se alguma tabela falhar, aparece aviso amarelo em vez de silêncio.

- [ ] **Passo 3: Commit**

```bash
git add src/extract_text.py
git commit -m "fix: avisa no terminal quando tabela de PDF não pode ser extraída"
```

---

## FASE 2 — Observabilidade

---

### Tarefa 6: Logging estruturado com arquivo rotativo

**O que faz:** Salva todas as mensagens importantes do pipeline em `data/logs/pipeline.log` com data e hora, preservando o visual Rich no terminal.

**Arquivos:**
- Modificar: `src/cli.py`

- [ ] **Passo 1: Adicionar configuração de logging no topo de cli.py**

Logo após os imports existentes em `src/cli.py` (após a linha `_console = Console(...)`), adicionar:

```python
import logging
import logging.handlers

def _configurar_logging() -> None:
    logs_dir = Path("data/logs")
    logs_dir.mkdir(parents=True, exist_ok=True)
    handler_arquivo = logging.handlers.RotatingFileHandler(
        logs_dir / "pipeline.log",
        maxBytes=1 * 1024 * 1024,  # 1 MB
        backupCount=5,
        encoding="utf-8",
    )
    handler_arquivo.setFormatter(
        logging.Formatter("%(asctime)s  %(levelname)-7s  %(name)s — %(message)s")
    )
    logging.basicConfig(level=logging.INFO, handlers=[handler_arquivo])
```

- [ ] **Passo 2: Chamar `_configurar_logging()` no início do app**

Adicionar ao início da função `extrair()`, antes do `with Progress(...)`:

```python
    _configurar_logging()
    _log = logging.getLogger("pcg.extrair")
```

E dentro do loop, após a linha `fonte = _processar(...)`, adicionar:

```python
                _log.info("OK %s — fonte=%s", caminho.name, fonte)
```

E dentro do `except Exception as e`, adicionar:

```python
                _log.error("ERRO %s — %s", caminho.name, e)
```

- [ ] **Passo 3: Smoke test**

```bash
uv run python -m src.cli extrair --limite 3
```

Esperado: arquivo `data/logs/pipeline.log` criado com linhas de log com timestamp.

Verificar:
```bash
uv run python -c "
from pathlib import Path
log = Path('data/logs/pipeline.log')
print('Existe:', log.exists())
if log.exists():
    print(log.read_text(encoding='utf-8')[:500])
"
```

- [ ] **Passo 4: Commit**

```bash
git add src/cli.py
git commit -m "feat: logging estruturado com arquivo rotativo em data/logs/pipeline.log"
```

---

### Tarefa 7: Criar guia de revisão do review.csv

**O que faz:** Documenta em linguagem simples como editar o arquivo `data/review.csv` corretamente.

**Arquivos:**
- Criar: `docs/guia-revisao-csv.md`

- [ ] **Passo 1: Criar o arquivo de documentação**

Criar `docs/guia-revisao-csv.md` com o conteúdo abaixo. Para descobrir os valores válidos de `situacao`, consultar `src/schema.py` (enum `Situacao`). O arquivo deve ser:

```markdown
# Guia de Revisão — review.csv

Este guia explica como editar o arquivo `data/review.csv` para corrigir ou confirmar os achados extraídos automaticamente dos PDFs.

## Fluxo de trabalho

1. Gerar o CSV: `uv run python -m src.cli revisar --gerar`
2. Abrir `data/review.csv` em um editor de planilhas (Excel, LibreOffice Calc, etc.)
3. Editar as linhas que precisam de correção
4. Marcar `revisado` como `true` nas linhas corrigidas
5. Salvar o arquivo (manter formato CSV com codificação UTF-8)
6. Aplicar as edições: `uv run python -m src.cli revisar --aplicar`
7. Reconstruir o site: `uv run python -m src.cli build`

## Colunas do arquivo

| Coluna | Pode editar? | Valores válidos | Exemplo |
|---|---|---|---|
| `relatorio_id` | **NÃO** | SHA-256 interno | `a3f8c1...` |
| `codigo` | **NÃO** | Código do achado | `III.01` |
| `municipio` | SIM | Nome do município de AL | `Maceió` |
| `ano_exercicio` | SIM | Ano com 4 dígitos | `2023` |
| `tipo` | SIM | Ver tabela abaixo | `Irregularidade` |
| `situacao` | SIM | Ver tabela abaixo | `sanado_total` |
| `descricao` | SIM | Texto livre | `Despesa sem...` |
| `recomendacao` | SIM | Texto livre ou vazio | |
| `determinacao` | SIM | Texto livre ou vazio | |
| `valor_financeiro` | SIM | Número decimal (ponto) ou vazio | `15000.00` |
| `houve_defesa` | SIM | `true` ou `false` | `true` |
| `revisado` | SIM | `true` ou `false` | `true` |

## Valores válidos para `tipo`

| Valor | Quando usar |
|---|---|
| `Irregularidade` | Infração a norma legal com potencial de dano |
| `Impropriedade` | Descumprimento de norma sem caracterizar dano |
| `Inconsistência` | Divergência entre documentos ou dados |

## Valores válidos para `situacao`

| Valor | Significado |
|---|---|
| `sanado_total` | Problema totalmente resolvido pelo gestor |
| `sanado_parcial` | Problema parcialmente resolvido |
| `afastado` | Achado afastado após análise do contraditório |
| `mantido` | Achado mantido após análise |
| `nao_consta` | Situação não informada no relatório |

## Regras importantes

- **Não altere** `relatorio_id` nem `codigo` — são as chaves que identificam cada achado no sistema.
- Apenas linhas com `revisado=true` serão aplicadas ao banco. Deixe `false` nas linhas que não precisam de alteração.
- O campo `valor_financeiro` usa **ponto** como separador decimal (ex: `15000.00`), não vírgula.
- Salve o arquivo em **UTF-8** para preservar caracteres especiais (ã, ç, é, etc.). No Excel: "Salvar como" → "CSV UTF-8 (delimitado por vírgulas)".

## Exemplo de linha editada

```
relatorio_id,codigo,municipio,ano_exercicio,tipo,situacao,...,revisado
a3f8c1...,III.03,Maceió,2023,Irregularidade,sanado_total,...,true
```
```

- [ ] **Passo 2: Verificar que o arquivo foi criado**

```bash
uv run python -c "
from pathlib import Path
p = Path('docs/guia-revisao-csv.md')
print('Existe:', p.exists(), '— tamanho:', p.stat().st_size, 'bytes')
"
```

- [ ] **Passo 3: Commit**

```bash
git add docs/guia-revisao-csv.md
git commit -m "docs: guia de revisão do review.csv para revisores não técnicos"
```

---

### Tarefa 8: Adicionar comando `diagnosticar`

**O que faz:** Novo subcomando `diagnosticar` que exibe um painel resumido do estado atual do pipeline.

**Arquivos:**
- Modificar: `src/cli.py`

- [ ] **Passo 1: Adicionar o comando ao final de cli.py (antes de `if __name__ == "__main__"`)**

```python
@app.command()
def diagnosticar() -> None:
    """Exibe painel de diagnóstico do estado atual do pipeline."""
    from rich.table import Table
    from rich.panel import Panel
    import csv

    rels = cache.listar()

    total = len(rels)
    por_fonte: dict[str, int] = {}
    anos: set[int] = set()
    municipios_com_relatorio: set[str] = set()
    achados_com_campo_vazio = 0

    for r in rels:
        por_fonte[r.fonte_extracao] = por_fonte.get(r.fonte_extracao, 0) + 1
        if r.ano_exercicio:
            anos.add(r.ano_exercicio)
        if r.municipio:
            municipios_com_relatorio.add(r.municipio)
        for a in r.achados:
            if not a.descricao or not a.tipo or not a.situacao:
                achados_com_campo_vazio += 1

    # Lê review.csv
    from . import review as _review
    csv_path = _review.CSV_PATH
    total_csv = revisados = 0
    if csv_path.exists():
        with csv_path.open(encoding="utf-8", newline="") as f:
            for row in csv.DictReader(f):
                total_csv += 1
                if row.get("revisado", "").strip().lower() == "true":
                    revisados += 1

    anos_str = f"{min(anos)}–{max(anos)}" if anos else "—"

    _console.print()
    _console.print(Panel.fit(
        f"[bold]Total de relatórios em cache:[/bold]         {total}\n"
        f"  ├─ Parser moderno (2024):           {por_fonte.get('parser_2024', 0)}\n"
        f"  ├─ IA Gemini (legados):             {por_fonte.get('gemini_legacy', 0)}\n"
        f"  └─ Pendentes (sem extração):        {por_fonte.get('pendente_legacy', 0)}\n\n"
        f"[bold]Achados com campos em branco:[/bold]         {achados_com_campo_vazio}\n"
        f"[bold]Revisões marcadas como revisado=true:[/bold] {revisados} de {total_csv}\n\n"
        f"[bold]Municípios com relatório:[/bold]             {len(municipios_com_relatorio)}\n"
        f"[bold]Anos cobertos:[/bold]                        {anos_str}",
        title="[bold cyan]Diagnóstico do Pipeline PCG[/bold cyan]",
        border_style="cyan",
    ))
    _console.print()
```

- [ ] **Passo 2: Verificar que `review.CSV_PATH` existe**

```bash
uv run python -c "from src import review; print(review.CSV_PATH)"
```

Se não existir o atributo `CSV_PATH` em `review.py`, localizar a constante de caminho do CSV nesse arquivo e ajustar a referência no comando acima para o nome correto.

- [ ] **Passo 3: Rodar o comando**

```bash
uv run python -m src.cli diagnosticar
```

Esperado: painel formatado exibido sem erros, mesmo se o cache estiver vazio.

- [ ] **Passo 4: Commit**

```bash
git add src/cli.py
git commit -m "feat: adiciona comando diagnosticar com painel de estado do pipeline"
```

---

## FASE 3 — Evolução

---

### Tarefa 9: Busca por texto em site-v3/achados.html

**O que faz:** Adiciona caixa de busca que filtra a tabela de achados em tempo real, sem precisar de servidor.

**Arquivos:**
- Modificar: `site-v3/achados.html`
- Modificar: `site-v3/app.js`

- [ ] **Passo 1: Adicionar campo de busca ao HTML**

Em `site-v3/achados.html`, localizar o bloco `<div class="filters">` (que começa na linha ~42) e adicionar um novo `filter-group` com a caixa de busca **antes** do filtro de Município:

```html
    <div class="filter-group">
      <span class="filter-label">Buscar</span>
      <input
        type="search"
        class="filter-select"
        id="f-busca"
        placeholder="Digite para filtrar..."
        style="min-width:200px"
      />
    </div>
```

- [ ] **Passo 2: Localizar a função de filtro em app.js**

Abrir `site-v3/app.js` e localizar a função responsável por filtrar a tabela de achados (provavelmente chamada `filtrar`, `renderAchados`, ou similar — buscar por `f-municipio` para encontrar onde os filtros são lidos).

- [ ] **Passo 3: Adicionar leitura do campo de busca na função de filtro**

Dentro da função de filtro, junto com a leitura dos outros filtros (município, tipo, situação, seção), adicionar:

```javascript
const termoBusca = (document.getElementById('f-busca')?.value || '').toLowerCase().trim();
```

E na condição de filtragem de cada achado, adicionar a verificação de busca. O bloco de filtro deve ter formato similar a:

```javascript
// adicionar após as outras condições de filtro
if (termoBusca) {
  const textoAchado = [
    a.tipo || '',
    a.descricao || '',
    a.recomendacao || '',
    a.determinacao || '',
    a.base_normativa || '',
  ].join(' ').toLowerCase();
  if (!textoAchado.includes(termoBusca)) return false;
}
```

- [ ] **Passo 4: Registrar o event listener para a caixa de busca**

Na seção onde os outros filtros são inicializados (buscar por `f-municipio` com `addEventListener`), adicionar:

```javascript
document.getElementById('f-busca')?.addEventListener('input', filtrar);
```

(Substituindo `filtrar` pelo nome real da função de filtro encontrada no Passo 2.)

- [ ] **Passo 5: Limpar a busca no botão "Limpar filtros"**

Localizar o handler do botão de reset (buscar por `btn-reset`) e adicionar:

```javascript
document.getElementById('f-busca').value = '';
```

junto com o reset dos outros campos.

- [ ] **Passo 6: Testar no navegador**

```bash
python -m http.server -d site-v3 8001
```

Abrir `http://localhost:8001/achados.html`. Digitar "licitação" na caixa de busca. Esperado: a tabela filtra para mostrar apenas achados que contenham "licitação" em qualquer campo de texto.

Testar também:
- Busca em combinação com filtro de município
- Botão "Limpar" zera a busca
- Busca vazia mostra todos os achados

- [ ] **Passo 7: Commit**

```bash
git add site-v3/achados.html site-v3/app.js
git commit -m "feat: adiciona busca por texto em tempo real no Banco de Achados (site-v3)"
```

---

### Tarefa 10: Paralelizar extração de PDFs

**O que faz:** Processa múltiplos PDFs ao mesmo tempo usando `ThreadPoolExecutor`, reduzindo o tempo total de extração.

**Arquivos:**
- Modificar: `src/cli.py`

- [ ] **Passo 1: Adicionar import**

No topo de `src/cli.py`, após os imports existentes, adicionar:

```python
import concurrent.futures
```

- [ ] **Passo 2: Substituir o loop sequencial da função `extrair`**

Localizar em `src/cli.py` o bloco dentro de `extrair()`:

```python
    with Progress(SpinnerColumn(spinner_name="line"), TextColumn("{task.description}"), console=_console) as prog:
        for caminho, ano_pasta in alvos:
            t = prog.add_task(f"[cyan]{caminho.name}", total=None)
            try:
                fonte = _processar(caminho, ano_pasta, forcar=forcar)
                ...
            except Exception as e:
                prog.update(t, description=f"[red]ERRO {caminho.name}: {e}")
```

Substituir por:

```python
    workers = int(os.getenv("PCG_WORKERS", "4"))

    def _processar_com_prog(args: tuple) -> None:
        caminho, ano_pasta = args
        t = prog.add_task(f"[cyan]{caminho.name}", total=None)
        try:
            fonte = _processar(caminho, ano_pasta, forcar=forcar)
            if fonte == "gemini_legacy":
                from .rate_limit import estado_atual
                est = estado_atual()
                prog.update(t, description=f"[green]OK {caminho.name} [dim]({est['rpd_usado']}/{est['rpd_max']} req Gemini)[/]")
            else:
                prog.update(t, description=f"[green]OK {caminho.name}")
        except Exception as e:
            prog.update(t, description=f"[red]ERRO {caminho.name}: {e}")

    with Progress(SpinnerColumn(spinner_name="line"), TextColumn("{task.description}"), console=_console) as prog:
        with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as executor:
            list(executor.map(_processar_com_prog, alvos))
```

Também adicionar `import os` ao topo do arquivo se ainda não existir (verificar antes).

- [ ] **Passo 3: Smoke test com limite e verificar ausência de erros de concorrência**

```bash
uv run python -m src.cli extrair --limite 6
```

Esperado: 6 PDFs processados sem erros. Verificar que o cache não foi corrompido:

```bash
uv run python -m src.cli diagnosticar
```

Esperado: painel mostra os relatórios corretamente.

- [ ] **Passo 4: Commit**

```bash
git add src/cli.py
git commit -m "feat: paraleliza extração de PDFs com ThreadPoolExecutor (padrão 4 workers)"
```

---

### Tarefa 11: Eliminar código duplicado (normalizar_situacao e rate-limit)

**O que faz:** Remove a função `_coagir_situacao` de `parse_legacy.py` (duplicata de `normalizar_situacao`) e cria um decorator `@com_rate_limit` em `rate_limit.py` para encapsular o padrão repetido.

**Arquivos:**
- Modificar: `src/rate_limit.py`
- Modificar: `src/parse_legacy.py`
- Modificar: `src/parse_contraditorio.py`

- [ ] **Passo 1: Verificar que `_coagir_situacao` é de fato duplicata**

```bash
uv run python -c "
from src.schema import normalizar_situacao
from src.schema import Situacao
# testa valores que parse_legacy usa
for v in ['sanado_total', 'mantido', 'afastado', 'nao_consta', 'sanado_parcial']:
    print(v, '->', normalizar_situacao(v))
"
```

Esperado: todos os valores retornam o enum correto.

- [ ] **Passo 2: Remover `_coagir_situacao` de parse_legacy.py**

Localizar em `src/parse_legacy.py` a função `_coagir_situacao` e removê-la completamente. Localizar todos os usos de `_coagir_situacao(...)` no mesmo arquivo e substituir por `normalizar_situacao(...)` (já importada via `from .schema import Achado, Situacao, normalizar_situacao`).

- [ ] **Passo 3: Adicionar decorator `com_rate_limit` em rate_limit.py**

Adicionar ao final de `src/rate_limit.py`:

```python
import functools
from typing import Callable, TypeVar

_F = TypeVar("_F", bound=Callable)


def com_rate_limit(func: _F) -> _F:
    """Decorator: aguarda rate-limit antes da chamada e marca sucesso ao terminar."""
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        aguardar()
        resultado = func(*args, **kwargs)
        marcar_sucesso()
        return resultado
    return wrapper  # type: ignore[return-value]
```

- [ ] **Passo 4: Verificar se parse_legacy.py e parse_contraditorio.py chamam aguardar/marcar_sucesso diretamente**

```bash
uv run python -c "
import ast, pathlib
for f in ['src/parse_legacy.py', 'src/parse_contraditorio.py']:
    src = pathlib.Path(f).read_text(encoding='utf-8')
    print(f, '— aguardar:', src.count('aguardar()'), '— marcar_sucesso:', src.count('marcar_sucesso()'))
"
```

Se os contadores forem > 0, os próximos passos substituem esses padrões. Se já forem 0, pular os passos 5 e 6.

- [ ] **Passo 5: Substituir padrão em parse_legacy.py**

Localizar em `src/parse_legacy.py` os blocos:

```python
aguardar()
# ... chamada à API Gemini ...
marcar_sucesso()
```

Adicionar `from .rate_limit import com_rate_limit` ao bloco de imports do arquivo. Aplicar o decorator `@com_rate_limit` à função interna que faz a chamada à API Gemini, removendo as chamadas manuais a `aguardar()` e `marcar_sucesso()`.

- [ ] **Passo 6: Substituir padrão em parse_contraditorio.py**

Aplicar a mesma mudança do Passo 5 em `src/parse_contraditorio.py`.

- [ ] **Passo 7: Smoke test**

```bash
uv run python -m src.cli extrair --limite 3
```

Esperado: pipeline funciona; nenhuma regressão.

- [ ] **Passo 8: Commit**

```bash
git add src/rate_limit.py src/parse_legacy.py src/parse_contraditorio.py
git commit -m "refactor: remove _coagir_situacao duplicada e adiciona decorator com_rate_limit"
```

---

## Checklist final

Após todas as tarefas, executar a verificação completa:

- [ ] `uv run python -m src.cli extrair --limite 3` — sem erros
- [ ] `uv run python -m src.cli diagnosticar` — painel exibido corretamente
- [ ] `uv run python -m src.cli listar` — lista relatórios do cache
- [ ] `python -m http.server -d site-v3 8001` + abrir achados.html — busca funciona
- [ ] `cat data/logs/pipeline.log` — log com timestamps existe
