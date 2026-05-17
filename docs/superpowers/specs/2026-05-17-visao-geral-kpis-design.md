# Visão Geral — KPIs e Gráficos (site-v3)

**Data:** 2026-05-17  
**Projeto:** Portal PCG · TCE-AL — Banco de Achados  
**Escopo:** Define os KPIs e gráficos da aba `index.html` do site-v3. Não altera outras páginas nem `build_site.py`.

---

## Contexto

Público-alvo: auditores e técnicos do TCE-AL. A página deve responder de relance:

1. Qual é o volume de trabalho? (relatórios, achados)
2. Qual é o diagnóstico rápido? (opinião dominante, situação dominante)
3. O cenário está melhorando? (evolução por ano, deltas)
4. Onde e o quê concentra os problemas? (municípios, tipos, situação)

---

## Estrutura da página

```
[ HERO — 3 KPI cards glassmorphism ]

[ CARDS SECUNDÁRIOS — linha 1: 2 cards grandes ]
[ CARDS SECUNDÁRIOS — linha 2: 2 cards menores ]

[ GRÁFICOS — grid de 5 ]
```

---

## Hero — 3 KPI cards glassmorphism

Layout: linha única, 3 cards com `flex: 1`. Fundo do hero: `linear-gradient(135deg, #1C588C, #0e3a60, #0a2540)`.

| Posição | Label | Valor principal | Fonte no `data.json` | Comparação anual |
|---|---|---|---|---|
| 1 | Relatórios analisados | `totais.relatorios` | `agregacoes.totais.relatorios` | `↑/↓ N vs [ano-1]` |
| 2 | Opinião mais frequente | `%` da opinião mais recorrente + nome curto | `agregacoes.por_opiniao` → maior valor ÷ total de relatórios | — sem comparação |
| 3 | Achados identificados | `totais.achados` | `agregacoes.totais.achados` | `↑/↓ N vs [ano-1]` |

O card 3 usa fundo `--red-dim` (`rgba(166,18,31,0.18)`) e borda `rgba(166,18,31,0.35)` para destacar visualmente o volume de achados como métrica de atenção.

**Comparação anual:**
- Filtro de ano ativo (ex: 2024): delta = valor(2024) − valor(2023), calculado a partir de `agregacoes.por_ano`.
- Filtro "Todos os anos": deltas ocultados.
- Filtro de município ativo: deltas ocultados (granularidade insuficiente para comparação confiável).

---

## Cards secundários

### Linha 1 — 2 cards grandes (50/50)

**Card: Situação dominante**
- Valor: percentual da situação com maior contagem + nome da situação
- Fonte: `agregacoes.por_situacao` → situação com maior valor ÷ `totais.achados`
- Comparação: `↑/↓ N p.p. vs ano anterior` (quando filtro de ano ativo)
- Cor do número: semântica por situação
  - `mantido` → `--red` (`#A6121F`)
  - `sanado_total` → `--ok` (`#1B7A4A`)
  - `sanado_parcial` → `--warn` (`#B86A10`)
  - `afastado` / `nao_consta` → `--neutral` (`#6B7E99`)

**Card: Municípios**
- Valor: número de municípios distintos cobertos
- Fonte: `agregacoes.totais.municipios`
- Comparação: sem comparação
- Cor do número: `--primary` (`#1C588C`)

### Linha 2 — 2 cards menores (50/50)

**Card: Achados sanados**
- Valor: % de achados com situação `sanado_total` + `sanado_parcial` + `afastado`
- Fonte: `(por_situacao.sanado_total + por_situacao.sanado_parcial + por_situacao.afastado) ÷ totais.achados`
- Comparação: `↑/↓ N p.p. vs ano anterior`
- Cor do número: `--ok` (`#1B7A4A`)

**Card: Com defesa apresentada**
- Valor: % de achados com `houve_defesa = true`
- Fonte: `totais.com_defesa ÷ totais.achados`
- Comparação: sem comparação
- Cor do número: `--primary` (`#1C588C`)

---

## Gráficos

Todos os gráficos reagem ao filtro de ano e município. Biblioteca: **Chart.js** (já usada no site-v2) ou barras em HTML/CSS puro — a consistência com o restante do site-v3 prevalece.

### 1. Situação dos achados — barras horizontais

- Dados: `agregacoes.por_situacao`
- Exibe: mantido, sanado_total, sanado_parcial, afastado, nao_consta
- Cada barra: label + barra colorida proporcional + contagem + percentual
- Cores: `--red`, `--ok`, `--warn`, `--neutral`, `--muted`
- Ordenação: mantido primeiro (situação mais crítica), depois sanados, depois demais

### 2. Evolução por ano — barras empilhadas

- Dados: `agregacoes.por_ano` + `agregacoes.por_municipio_por_ano[ano].situacao_por_municipio` (agregado)
- Eixo X: anos disponíveis (ex: 2023, 2024)
- Eixo Y: quantidade de achados
- Empilhamento: mantido (vermelho) + sanado_total (verde) + sanado_parcial (laranja) + afastado (cinza) + nao_consta (muted)
- Quando filtro de município ativo: filtra os dados pelo município antes de agregar por ano
- Nota: com apenas 2 anos o gráfico já é útil; torna-se mais rico conforme anos acumulam

### 3. Achados por tipo — barras horizontais

- Dados: `agregacoes.por_tipo` (top 10)
- Exibe: tipo + contagem + percentual
- Cor única: `--primary` com opacidade decrescente por rank
- Ordenação: do maior para o menor

### 4. Top municípios — lista rankeada com mini-barra

- Dados: `agregacoes.por_municipio` (top 10)
- Cada linha: número ordinal + nome do município + mini-barra + contagem
- Cor da mini-barra: baseada na situação dominante do município (`agregacoes.situacao_por_municipio`)
  - Dominante = mantido → `--red`
  - Dominante = sanado → `--ok`
  - Dominante = afastado/nao_consta → `--neutral`
- Clique na linha navega para `achados.html?municipio=<nome>`

### 5. Opinião da Auditoria — pizza (pie chart)

- Dados: `agregacoes.por_opiniao`
- Fatias: cada valor único de `opiniao_auditoria` + percentual
- Cores sugeridas:
  - "Regular" → `--ok` (`#1B7A4A`)
  - "Regular com Ressalvas" → `--warn` (`#B86A10`)
  - "Irregular" → `--red` (`#A6121F`)
  - Demais → `--neutral`
- Legenda abaixo do gráfico com contagem absoluta
- Baseado em relatórios (não em achados)

---

## Filtros globais

Posicionados logo abaixo do hero, em linha:

| Filtro | Fonte das opções | Efeito |
|---|---|---|
| Ano | `agregacoes.totais.anos` | Refiltra todos os KPIs e gráficos |
| Município | Lista distinta de `relatorios[].municipio` | Refiltra todos os KPIs e gráficos |

Botão "Limpar filtros" reseta ambos para "Todos".

---

## Fora de escopo

- Alterações em `build_site.py` ou `data.json`
- Dark mode
- Novas páginas ou abas
- Outras páginas do site-v3 (achados, municípios, seções etc.)
