# Site v3 — Design Spec

**Data:** 2026-05-16  
**Projeto:** Portal PCG · TCE-AL — Banco de Achados  
**Escopo:** Criar pasta `site-v3/` com todos os arquivos do novo design. Não altera `site/` nem `site-v2/`.

---

## Decisões de design validadas

| Dimensão | Escolha |
|---|---|
| Layout | Top nav horizontal fixo + conteúdo full-width |
| Composição da homepage | Hero grande escuro com 3 KPIs glassmorphism + 2 colunas |
| Tratamento visual | Moderno & analítico (glassmorphism, bold pesado, sombras suaves) |
| Paleta | `#F2F2F2` bg · `#1C588C` primário · `#A6121F` vermelho |

---

## Arquitetura de arquivos

A v3 cria uma **nova pasta `site-v3/`**. As pastas `site/` e `site-v2/` não são tocadas.

```
site-v3/
  index.html       ← Visão Geral (homepage)
  achados.html     ← Banco de Achados (tabela filtrável)
  municipios.html  ← Por Município
  secoes.html      ← Por Seção
  defesa.html      ← Defesa do Gestor
  pareceres.html   ← Opinião do Auditor
  insights.html    ← Insights
  sobre.html       ← Sobre
  style.css        ← novo design completo
  app.js           ← novo JS completo
  data.json        ← symlink ou cópia de site/data.json
```

O servidor de preview é iniciado com `python -m http.server -d site-v3 8003` e o link entregue ao usuário ao final.

---

## Sistema de design

### Paleta de cores

```css
--bg:              #F2F2F2;   /* fundo da página */
--surface:         #FFFFFF;   /* cards e painéis */
--surface-2:       #F7F7F7;   /* zebra / hover */
--primary:         #1C588C;   /* nav, hero, botões primários */
--primary-dark:    #0e3a60;   /* gradiente hero */
--primary-darker:  #0a2540;   /* gradiente hero fundo */
--red:             #A6121F;   /* achados mantidos, badges negativos */
--red-dim:         rgba(166,18,31,0.15); /* KPI glassmorphism vermelho */
--text:            #18293C;
--text-2:          #4A6080;
--muted:           #8A9BB5;
--border:          #DDE5F0;
--shadow:          0 2px 10px rgba(20,52,100,0.08);
--shadow-lg:       0 8px 32px rgba(20,52,100,0.14);
--radius:          10px;
--radius-sm:       6px;
```

Aliases semânticos (usados no JS/HTML):
- `--ok` → verde `#1B7A4A` (sanado total)
- `--warn` → laranja `#B86A10` (sanado parcial)
- `--bad` → `var(--red)` (mantido / irregular)
- `--neutral` → `#6B7E99` (afastado / não consta)

### Tipografia

- **Display / headings:** `Sora` (700, 800) — números grandes do hero
- **Corpo / labels:** `DM Sans` (400, 500, 600) — tabelas, filtros, textos
- **Mono:** `JetBrains Mono` (400) — códigos de processo, SHA

### Ícones

SVG inline (sem dependências externas), mesmo conjunto da v2.

---

## Layout global

```
┌──────────────────────────────────────────────────────┐
│  TOP NAV (full-width, #1C588C, 56px, position:fixed) │
│  [Logo TCE-AL]  [nav links]  [filtro de ano]         │
└──────────────────────────────────────────────────────┘
│  HERO (full-width, gradiente azul)                    │
│    inner: max-width 1280px, margin auto               │
├──────────────────────────────────────────────────────┤
│  PAGE CONTENT (max-width: 1280px, margin: auto)       │
└──────────────────────────────────────────────────────┘
```

O hero ocupa 100% da largura do viewport. O conteúdo interno (texto, KPIs) fica centralizado com `max-width: 1280px`. As páginas secundárias seguem o mesmo padrão com o page-header menor.

### Top Nav (componente compartilhado)

- Fundo `#1C588C`, altura `56px`, `position: fixed`, `z-index: 100`
- Esquerda: logo `[TC]` (quadrado vermelho 28px) + texto `TCE-AL` bold branco + separador `·` + `Portal PCG` muted
- Centro: links de navegação — texto branco 0.85rem, link ativo sublinhado com linha branca 2px na base
- Direita: seletor de ano global (dropdown pill branco transparente) + ícone hambúrguer no mobile
- Mobile (< 768px): links somem, hambúrguer abre drawer lateral

---

## Página: Visão Geral (`index.html`)

### Seção 1 — Hero

- Fundo: `linear-gradient(135deg, #1C588C 0%, #0e3a60 55%, #0a2540 100%)`
- Elemento decorativo: círculo vermelho `rgba(166,18,31,0.18)` de 200px, posicionado canto superior direito, `overflow: hidden`
- Conteúdo:
  - Supertítulo: `PRESTAÇÃO DE CONTAS · ALAGOAS` — 0.7rem, letter-spacing 2px, `rgba(255,255,255,0.5)`
  - Título: `Banco de Achados TCE-AL` — `Sora` 2rem bold branco
  - Subtítulo: `Análise de achados das prestações de contas municipais` — 0.875rem muted
  - 3 KPI cards glassmorphism (fundo `rgba(255,255,255,0.10)`, borda `rgba(255,255,255,0.18)`, blur 8px):
    - **Relatórios** — número grande branco
    - **Achados** — número grande, card com fundo `var(--red-dim)`, borda `rgba(166,18,31,0.35)`
    - **Municípios** — número grande branco
  - Badge abaixo dos KPIs: `· Anos disponíveis: 2023 · 2024 ·`

### Seção 2 — Conteúdo (2 colunas, 60/40)

**Coluna esquerda (60%):** Situação dos Achados
- Cabeçalho de seção: título + badge de total
- Barras horizontais para cada situação (mantido, sanado_total, sanado_parcial, afastado)
- Barras coloridas: vermelho, azul, azul-claro, cinza
- Cada barra mostra: label, barra proporcional, contagem e percentual

**Coluna direita (40%):** Top Municípios
- Lista rankeada com número de achados
- Cada linha: número ordinal, nome do município, badge de contagem, mini-barra
- Link para página de município

### Seção 3 — Grid de análise (abaixo das 2 colunas, full-width)

- **Card 1 (50%):** Achados por Tipo — barras horizontais (Impropriedade, Inconsistência, Irregularidade)
- **Card 2 (50%):** Distribuição por Opinião de Auditoria — barras horizontais (Regular, Regular c/ Ressalvas, Irregular)

### Filtros globais

- Seletor de `Ano` e `Município` no topo da área de conteúdo (logo abaixo do hero), em linha
- Ao mudar, todos os gráficos e números da página atualizam via JS (leitura de `data.json`)

---

## Páginas secundárias

Todas compartilham o mesmo top nav e estrutura geral. O hero é substituído por um **page-header** menor (fundo `#1C588C`, altura ~100px) com título e subtítulo da página.

### `achados.html` — Banco de Achados

- Filtros: Ano, Município, Tipo, Situação, Seção — linha de pills/selects acima da tabela
- Tabela responsiva com colunas: Município · Ano · Código · Tipo · Situação · Ações
- Badge colorido para situação (vermelho=mantido, azul=sanado, etc.)
- Linha expansível (accordion) mostrando descrição completa do achado
- Paginação client-side (25 por página)

### `municipios.html` — Por Município

- Grid de cards de município (2–3 colunas)
- Cada card: nome, contagem de achados, barra de situação (proporcional), badge de opinião
- Clique no card navega para `achados.html` com o filtro de município pré-aplicado via query string (`?municipio=Maceio`)

### `secoes.html` — Por Seção

- Tabela agrupada por seção (I, II, III...) com contagem e distribuição de tipos
- Expansível para ver achados da seção

### `defesa.html` — Defesa do Gestor

- Barras de `defesa_x_situacao`: quais achados tiveram defesa e qual foi o resultado
- Narrativa textual com os números mais relevantes

### `pareceres.html` — Opinião do Auditor

- Distribuição de opiniões (Regular, Regular c/ Ressalvas, Irregular) por relator e por ano
- Tabela de relatórios com link para processo

### `insights.html` — Insights

- Cards de insight textual pré-computados (tendências, destaques, anomalias)
- Mantém estrutura existente

### `sobre.html` — Sobre

- Texto institucional + descrição da metodologia
- Mantém estrutura existente

---

## Interatividade (JavaScript)

- **Arquivo único:** `app.js` — sem frameworks, vanilla JS ES2020+
- **Carregamento de dados:** `fetch('data.json')` uma vez, cache em variável global
- **Filtros reativos:** evento `change` nos selects re-renderiza os componentes afetados
- **Accordion de achados:** toggle de classe CSS, sem animações complexas
- **Paginação:** state local por página, re-renderiza a tabela
- **Mobile nav:** toggle de classe no `<body>` para drawer

---

## Responsividade

- `< 768px`: top nav vira hambúrguer + drawer; hero KPIs em coluna; 2 colunas vira 1 coluna
- `768px–1024px`: colunas 50/50; grid de 2 cards
- `> 1024px`: layout completo conforme descrito

---

## O que NÃO muda

- `site/` e `site-v2/` — intocados
- `data.json` de `site/` — apenas copiado para `site-v3/`
- Lógica de `build_site.py` — mantida
- Estrutura de agregações em `data.json` — mantida

---

## Fora de escopo

- Dark mode
- Autenticação
- Backend / API
- Internacionalização
- Novos tipos de agregação no `data.json`
