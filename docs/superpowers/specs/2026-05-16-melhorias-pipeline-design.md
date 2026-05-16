# Spec: Melhorias do Pipeline PCG — Confiabilidade, Observabilidade e Evolução

**Data:** 2026-05-16
**Status:** Aprovado
**Escopo:** Três fases sequenciais de melhoria no pipeline de extração e no site do Portal de Controle do Governo (TCE-AL)

---

## Contexto

O projeto extrai achados de auditoria de PDFs do TCE-AL, estrutura os dados, permite revisão humana e publica um site estático. Com ~2000 linhas de Python, 13 módulos e nenhum teste automatizado, o pipeline funciona bem em alto nível mas apresenta fragilidades que podem corromper dados silenciosamente, dificultar diagnóstico de falhas e tornar a manutenção mais custosa ao longo do tempo.

O objetivo desta spec é orientar três fases de melhoria, em ordem de criticidade, sem quebrar interfaces existentes.

---

## Fase 1 — Confiabilidade

> Corrigir bugs que podem causar dados incorretos, perdidos ou corrompidos.

### 1.1 Race condition no `rate_limit.py`

**Problema:** O arquivo `data/.gemini_state.json` (que guarda contadores de uso da API Gemini) é lido e escrito sem mecanismo de exclusão mútua. Se dois processos Python rodarem ao mesmo tempo, um pode sobrescrever o trabalho do outro, fazendo os contadores ficarem desatualizados e a cota real ser ultrapassada.

**Solução:** Adicionar `filelock` como dependência e envolver as operações de leitura/escrita do state file com um lock de arquivo (`FileLock`). O lock é adquirido apenas durante I/O, não durante o `sleep()`, evitando bloqueio desnecessário.

**Arquivos afetados:** `src/rate_limit.py`, `pyproject.toml`

**Critério de conclusão:** Dois processos rodando simultaneamente não corrompem `data/.gemini_state.json`.

---

### 1.2 Detecção errada de município em `enrich.py`

**Problema:** A função `detectar_municipio()` busca os 102 municípios de AL por substring simples, sem word boundary. Isso permite matches parciais ("Mar" dentro de "Empresarial") e pode detectar o município errado se a lista não estiver ordenada por comprimento — nomes menores podem ser encontrados dentro de nomes maiores.

**Solução:**
1. Ordenar `MUNICIPIOS_AL` por comprimento decrescente antes de usar (`_MUNICIPIOS_SORTED`), garantindo que nomes mais específicos sejam testados primeiro.
2. Usar `re.search()` com `\b` (word boundary) em vez de `str.find()`, evitando matches dentro de palavras maiores.

**Arquivos afetados:** `src/enrich.py`

**Critério de conclusão:** Texto contendo "Empresarial" não detecta "Mar"; texto contendo "São Luís do Quitunde" não detecta "Luís" ou "São" como município isolado.

---

### 1.3 `except RuntimeError: pass` genérico em `cli.py`

**Problema:** O bloco que captura erros de cota Gemini usa `except RuntimeError: pass`, que silencia qualquer `RuntimeError` — incluindo erros de outros módulos que deveriam ser reportados.

**Solução:** Verificar a mensagem de erro antes de suprimir. Apenas mensagens contendo "cota" ou "quota" (case-insensitive) devem ser silenciadas; qualquer outra deve relançar a exceção.

**Arquivos afetados:** `src/cli.py`

**Critério de conclusão:** Um `RuntimeError` de outro módulo é propagado normalmente; erros de cota Gemini continuam sendo suprimidos.

---

### 1.4 Sem validação de JSON após salvar em `cache.py`

**Problema:** Após gerar o JSON de um relatório, o arquivo é escrito em disco sem verificar se o conteúdo é válido. Em edge cases (ex: tipo de dado inesperado), o JSON pode ser corrompido e o arquivo gravado assim mesmo, sem erro visível.

**Solução:** Após gerar a string JSON e antes de gravar no arquivo temporário, fazer `json.loads()` de volta. Se falhar, lançar `ValueError` com o nome do arquivo — impedindo que um JSON inválido seja salvo.

**Arquivos afetados:** `src/cache.py`

**Critério de conclusão:** Um objeto com tipo não-serializável lança erro antes de tocar o disco; arquivos válidos continuam sendo salvos normalmente.

---

### 1.5 Falha silenciosa ao extrair tabelas em `extract_text.py`

**Problema:** Quando `page.extract_tables()` lança exceção (PDF corrompido ou formato não suportado), o erro é capturado e a página continua sem tabela — sem nenhum aviso ao usuário. Achados podem ser perdidos sem que ninguém saiba.

**Solução:** No bloco `except`, emitir um aviso visível via Rich console indicando o nome do arquivo e o número da página afetada. O comportamento de fallback (continuar sem tabela) permanece o mesmo — apenas a transparência muda.

**Arquivos afetados:** `src/extract_text.py`

**Critério de conclusão:** Quando uma tabela não pode ser extraída, uma mensagem de aviso amarela aparece no terminal com o nome do PDF e a página.

---

## Fase 2 — Observabilidade

> Tornar visível o que acontece durante e após a execução do pipeline.

### 2.1 Logging estruturado com arquivo rotativo

**Problema:** O sistema usa `print()` e `console.print()` (Rich) para feedback. As mensagens aparecem na tela e somem quando o terminal é fechado. Não há registro persistido de execuções anteriores.

**Solução:** Configurar o módulo `logging` da biblioteca padrão do Python com dois handlers:
- **Console:** mantém o comportamento atual (Rich, colorido)
- **Arquivo:** `data/logs/pipeline.log` com rotação automática (máximo 5 arquivos de 1MB cada)

O formato do arquivo de log inclui data/hora, nível (INFO/WARN/ERROR) e mensagem. Todos os módulos do pipeline passam a usar `logger = logging.getLogger(__name__)` em vez de `print()`.

**Arquivos afetados:** `src/cli.py` (configuração central), todos os módulos `src/*.py` (substituição de prints críticos)

**Critério de conclusão:** Após rodar `extrair`, o arquivo `data/logs/pipeline.log` existe e contém os eventos da execução com timestamps.

---

### 2.2 Comando `diagnosticar`

**Problema:** Não existe forma rápida de ver o estado atual do pipeline — quantos PDFs foram processados, por qual método, quantos têm campos em branco, quantas revisões foram aplicadas.

**Solução:** Novo subcomando `diagnosticar` no CLI (`src/cli.py`) que lê os arquivos de cache em `data/extracted/` e o `data/review.csv` e exibe um painel resumido:

```
Total de relatórios em cache:        187
  ├─ Parser moderno (2024):           134
  ├─ IA Gemini (legados):              48
  └─ Pendentes (sem extração):          5

Achados com campos em branco:         23
Revisões marcadas como revisado=true: 61 de 89

Municípios sem nenhum relatório:      12
Anos cobertos:                     2018–2024
```

**Arquivos afetados:** `src/cli.py` (novo comando), leitura de `src/cache.py` e `src/review.py`

**Critério de conclusão:** `uv run python -m src.cli diagnosticar` exibe o painel sem erros.

---

### 2.3 Guia de revisão do `review.csv`

**Problema:** O arquivo `data/review.csv` é editado manualmente, mas não há documentação explicando quais colunas podem ser modificadas, quais são somente-leitura e quais valores são aceitos em cada campo.

**Solução:** Criar `docs/guia-revisao-csv.md` com:
- Tabela de colunas: nome, se é editável, valores válidos, exemplo
- Explicação do campo `revisado`: o que acontece quando é `true` vs. `false`
- Avisos sobre colunas que não devem ser alteradas (`relatorio_id`, `codigo`)
- Exemplo de fluxo completo: gerar CSV → editar → aplicar

**Arquivos afetados:** `docs/guia-revisao-csv.md` (arquivo novo)

**Critério de conclusão:** Um revisor sem conhecimento técnico consegue editar o CSV corretamente seguindo apenas o guia.

---

## Fase 3 — Evolução

> Melhorar desempenho, experiência de uso e manutenibilidade do código.

### 3.1 Paralelização da extração de PDFs

**Problema:** O comando `extrair` processa PDFs sequencialmente. Com 200 PDFs e ~10 segundos cada, a extração leva ~33 minutos. Não há razão técnica para não processar vários ao mesmo tempo.

**Solução:** Usar `concurrent.futures.ThreadPoolExecutor` com 4 workers (configurável via variável de ambiente `PCG_WORKERS`, padrão 4). O rate-limiter existente já serializa as chamadas ao Gemini, então não há risco de ultrapassar cota. O cache SHA-256 garante que dois workers não processem o mesmo PDF.

**Arquivos afetados:** `src/cli.py` (loop de extração)

**Critério de conclusão:** `extrair --limite 12` com 4 workers termina em ~1/3 do tempo do sequencial; nenhum cache é corrompido.

---

### 3.2 Busca por texto no site-v3

**Problema:** O site exibe achados com filtros de município e ano, mas não há campo de busca. Para encontrar achados sobre um tema específico (ex: "licitação"), o usuário precisa ler manualmente.

**Solução:** Adicionar uma caixa de busca no topo do site que filtra os achados em tempo real (client-side, sem servidor) enquanto o usuário digita. A busca opera sobre os campos `tipo`, `descricao`, `recomendacao` e `determinacao` de cada achado. Funciona em conjunto com os filtros existentes de município e ano.

**Arquivos afetados:** `site-v3/index.html` (ou equivalente), JavaScript da página

**Critério de conclusão:** Digitar "licitação" na caixa de busca filtra a lista para achados que contêm essa palavra em qualquer campo de texto.

---

### 3.3 Eliminar código duplicado

**Problema A — `normalizar_situacao` duplicada:** A lógica de converter texto livre para o enum `Situacao` existe em `schema.py` (`normalizar_situacao`) e em `parse_legacy.py` (`_coagir_situacao`). São quase idênticas; manter as duas significa que uma pode ser corrigida e a outra não.

**Solução A:** Remover `_coagir_situacao` de `parse_legacy.py` e usar `schema.normalizar_situacao` diretamente.

**Problema B — Bloco de rate-limit repetido:** `parse_legacy.py` e `parse_contraditorio.py` repetem o mesmo padrão `aguardar() → chamar_gemini() → marcar_sucesso()`. Se esse padrão precisar mudar, precisa ser alterado em dois lugares.

**Solução B:** Criar um decorator `@com_rate_limit` em `rate_limit.py` que encapsula o padrão. As funções que chamam o Gemini apenas declaram `@com_rate_limit` e o comportamento é aplicado automaticamente.

**Arquivos afetados:** `src/rate_limit.py`, `src/parse_legacy.py`, `src/parse_contraditorio.py`, `src/schema.py`

**Critério de conclusão:** Nenhum teste de regressão quebra (smoke test com `--limite 3`); o código duplicado é removido.

---

## Ordem de implementação recomendada

```
Fase 1 (qualquer ordem entre si, todas independentes):
  1.2 → Município (risco de dados errados, mais simples)
  1.3 → RuntimeError (1 linha de mudança)
  1.5 → Tabela silenciosa (1 linha de mudança)
  1.4 → Validação JSON (baixo risco, alta segurança)
  1.1 → Race condition (requer nova dependência: filelock)

Fase 2 (após Fase 1):
  2.3 → Guia CSV (sem código, só documentação)
  2.2 → Comando diagnosticar (leitura apenas, sem risco)
  2.1 → Logging (maior impacto, mais arquivos afetados)

Fase 3 (após Fase 2):
  3.3 → Eliminar duplicatas (refatoração segura)
  3.1 → Paralelização (testar bem com --limite)
  3.2 → Busca no site (frontend isolado)
```

---

## O que esta spec NÃO cobre

- Testes automatizados (seria uma spec separada, dado o impacto)
- Redesign do schema de dados (estável, sem necessidade)
- Novas features de parsing (ex: novos capítulos de relatório)
- Infraestrutura de deploy além do GitHub Pages atual
