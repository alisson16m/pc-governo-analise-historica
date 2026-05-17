# Visão Geral — KPIs e Gráficos Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Atualizar `site-v3/index.html`, `site-v3/style.css` e `site-v3/app.js` para implementar os KPIs e gráficos aprovados no spec de 2026-05-17, transformando a página em "Observatório de Contas Municipais — Alagoas".

**Architecture:** Toda a lógica fica em `app.js` (vanilla JS, sem frameworks). O HTML fornece os containers com IDs conhecidos; o JS lê `data.json`, filtra por ano/município e renderiza HTML puro (sem Chart.js) em cada container. O CSS usa as variáveis já definidas em `style.css`.

**Tech Stack:** Vanilla JS ES2020+, HTML5, CSS3 com custom properties. Sem dependências externas novas. Preview: `python -m http.server -d site-v3 8003`.

---

## Mapa de arquivos

| Arquivo | O que muda |
|---|---|
| `site-v3/index.html` | Identidade, estrutura dos KPIs hero (3 cards), 4 cards secundários, filtros, grid de gráficos |
| `site-v3/style.css` | Estilos novos: KPI hero com delta, opinião KPI, 4-col secondary cards, barras empilhadas, pizza |
| `site-v3/app.js` | Label nav, renderIndex() completa: hero KPIs + deltas, cards secundários, 5 gráficos |

---

## Task 1: Atualizar `index.html` — identidade e estrutura

**Files:**
- Modify: `site-v3/index.html`

- [ ] **Step 1: Atualizar identidade do hero**

Substituir o bloco `.hero-inner` atual pelo seguinte (mantém os IDs que o JS já usa e adiciona os novos):

```html
<section class="hero">
  <div class="hero-inner">
    <p class="hero-super">Diretoria de Coordenação de Técnicos — DCT</p>
    <h1 class="hero-title">Observatório de Contas Municipais — Alagoas</h1>
    <p class="hero-sub">Análise dos Relatórios Técnicos Conclusivos das Prestações de Contas de Governo Municipal</p>
    <div class="hero-kpis">
      <div class="kpi-glass">
        <div class="kpi-value" id="kpi-relatorios">—</div>
        <div class="kpi-label">Relatórios analisados</div>
        <div class="kpi-delta" id="kpi-relatorios-delta"></div>
      </div>
      <div class="kpi-glass">
        <div class="kpi-opiniao" id="kpi-opiniao">—</div>
        <div class="kpi-label">Opinião mais frequente</div>
      </div>
      <div class="kpi-glass red">
        <div class="kpi-value" id="kpi-achados">—</div>
        <div class="kpi-label">Achados identificados</div>
        <div class="kpi-delta" id="kpi-achados-delta"></div>
      </div>
    </div>
    <p class="hero-anos" id="hero-anos"></p>
  </div>
</section>
```

- [ ] **Step 2: Adicionar 4 cards secundários e filtros**

Substituir o bloco `.page-content` atual pelo seguinte:

```html
<div class="page-content">
  <div class="filters">
    <div class="filter-group">
      <span class="filter-label">Ano</span>
      <select class="filter-select" id="f-ano">
        <option value="">Todos os anos</option>
      </select>
    </div>
    <div class="filter-group">
      <span class="filter-label">Município</span>
      <select class="filter-select" id="f-municipio">
        <option value="">Todos os municípios</option>
      </select>
    </div>
    <button class="filter-reset" id="btn-reset">Limpar filtros</button>
  </div>

  <div class="sec-cards-4">
    <div class="sec-card">
      <div class="sec-card-label">Municípios</div>
      <div class="sec-card-value blue" id="sc-municipios">—</div>
      <div class="sec-card-desc">com relatório no exercício</div>
    </div>
    <div class="sec-card">
      <div class="sec-card-label">Achados mantidos</div>
      <div class="sec-card-value red" id="sc-mantidos">—</div>
      <div class="sec-card-desc">situação mais frequente</div>
      <div class="sec-card-delta" id="sc-mantidos-delta"></div>
    </div>
    <div class="sec-card">
      <div class="sec-card-label">Achados sanados</div>
      <div class="sec-card-value green" id="sc-sanados">—</div>
      <div class="sec-card-desc">total + parcial + afastado</div>
      <div class="sec-card-delta" id="sc-sanados-delta"></div>
    </div>
    <div class="sec-card">
      <div class="sec-card-label">Defesa apresentada</div>
      <div class="sec-card-value blue" id="sc-defesa">—</div>
      <div class="sec-card-desc">achados com manifestação do gestor</div>
    </div>
  </div>

  <div class="section-header">
    <span class="section-title">Análise dos achados</span>
    <span class="section-badge" id="section-badge-ano"></span>
  </div>

  <div class="two-col" style="margin-bottom:1rem">
    <div class="card">
      <div class="card-header">
        <span class="card-title">Situação dos achados</span>
        <span class="card-badge" id="badge-total-sit">—</span>
      </div>
      <div class="card-body" id="chart-situacao"></div>
    </div>
    <div class="card">
      <div class="card-header">
        <span class="card-title">Evolução por ano</span>
      </div>
      <div class="card-body" id="chart-evolucao"></div>
    </div>
  </div>

  <div class="three-col">
    <div class="card">
      <div class="card-header">
        <span class="card-title">Achados por tipo</span>
      </div>
      <div class="card-body" id="chart-tipo"></div>
    </div>
    <div class="card">
      <div class="card-header">
        <span class="card-title">Top municípios</span>
        <span class="card-badge" id="badge-total-muni">—</span>
      </div>
      <div class="card-body" id="chart-municipios"></div>
    </div>
    <div class="card">
      <div class="card-header">
        <span class="card-title">Opinião da Auditoria</span>
      </div>
      <div class="card-body" id="chart-opiniao-pizza"></div>
    </div>
  </div>
</div>
```

- [ ] **Step 3: Atualizar `<title>`**

```html
<title>Observatório de Contas Municipais — TCE-AL</title>
```

- [ ] **Step 4: Verificar visualmente (servidor de preview)**

```bash
python -m http.server -d site-v3 8003
```

Abrir `http://localhost:8003`. Verificar: hero com 3 cards, 4 cards secundários brancos (valores "—"), 5 containers de gráficos vazios. Não deve haver erros de JS no console.

- [ ] **Step 5: Commit**

```bash
git add site-v3/index.html
git commit -m "feat: reestrutura index.html com identidade e containers do novo design"
```

---

## Task 2: Adicionar estilos CSS em `style.css`

**Files:**
- Modify: `site-v3/style.css`

- [ ] **Step 1: Estilos do hero KPI — delta e opinião**

Adicionar ao final de `style.css`:

```css
/* ── Hero KPIs — novo design ── */
.kpi-glass .kpi-value {
  font-family: 'Sora', sans-serif;
  font-size: 1.75rem;
  font-weight: 800;
  color: #fff;
  line-height: 1;
}
.kpi-delta {
  font-size: 0.72rem;
  font-weight: 600;
  margin-top: 0.5rem;
  min-height: 1rem;
}
.kpi-delta.up  { color: #4ade80; }
.kpi-delta.dn  { color: #f87171; }
.kpi-delta.neu { color: rgba(255,255,255,0.4); }

/* KPI opinião: nome + percentual em linha, mesmo tamanho */
.kpi-opiniao {
  display: flex;
  align-items: baseline;
  gap: 0.5rem;
  flex-wrap: wrap;
  font-family: 'Sora', sans-serif;
  font-size: 1.75rem;
  font-weight: 800;
  color: #fff;
  line-height: 1.2;
}
.kpi-opiniao .sep {
  font-size: 1.4rem;
  color: rgba(255,255,255,0.3);
}
```

- [ ] **Step 2: Estilos dos 4 cards secundários**

```css
/* ── Cards secundários ── */
.sec-cards-4 {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 1rem;
  margin-bottom: 1.75rem;
}
.sec-card {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 1.25rem 1.5rem;
  box-shadow: var(--shadow);
}
.sec-card-label {
  font-size: 0.65rem;
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--muted);
  margin-bottom: 0.375rem;
}
.sec-card-value {
  font-family: 'Sora', sans-serif;
  font-size: 1.9rem;
  font-weight: 800;
  line-height: 1;
}
.sec-card-value.red   { color: var(--red); }
.sec-card-value.green { color: var(--ok); }
.sec-card-value.blue  { color: var(--primary); }
.sec-card-desc {
  font-size: 0.78rem;
  color: var(--text-2);
  margin-top: 0.25rem;
  font-weight: 500;
}
.sec-card-delta {
  font-size: 0.72rem;
  font-weight: 600;
  margin-top: 0.5rem;
  min-height: 1rem;
}
.sec-card-delta.dn { color: var(--red); }
.sec-card-delta.up { color: var(--ok); }
```

- [ ] **Step 3: Estilos do cabeçalho de seção e grid de 3 colunas**

```css
/* ── Cabeçalho de seção ── */
.section-header {
  display: flex;
  align-items: center;
  gap: 0.625rem;
  margin-bottom: 1.25rem;
}
.section-title {
  font-size: 1rem;
  font-weight: 700;
  color: var(--text);
}
.section-badge {
  background: var(--surface-2);
  border: 1px solid var(--border);
  border-radius: 20px;
  padding: 2px 0.625rem;
  font-size: 0.72rem;
  color: var(--muted);
  font-weight: 600;
}

/* ── Grid 3 colunas ── */
.three-col {
  display: grid;
  grid-template-columns: 1.4fr 1fr 1fr;
  gap: 1rem;
  margin-bottom: 2rem;
}
@media (max-width: 900px) {
  .sec-cards-4     { grid-template-columns: 1fr 1fr; }
  .three-col       { grid-template-columns: 1fr; }
}
```

- [ ] **Step 4: Estilos das barras empilhadas (evolução por ano)**

```css
/* ── Barras empilhadas — evolução por ano ── */
.stacked-wrap { display: flex; flex-direction: column; gap: 0.875rem; }
.stacked-row  { display: flex; align-items: center; gap: 0.625rem; }
.stacked-year {
  font-size: 0.78rem;
  font-weight: 700;
  color: var(--text-2);
  width: 36px;
  flex-shrink: 0;
}
.stacked-bar {
  flex: 1;
  display: flex;
  height: 22px;
  border-radius: 5px;
  overflow: hidden;
  gap: 1px;
}
.stacked-seg { height: 100%; }
.stacked-total {
  font-size: 0.72rem;
  color: var(--muted);
  width: 36px;
  text-align: right;
  flex-shrink: 0;
}
.stacked-legend {
  display: flex;
  flex-wrap: wrap;
  gap: 0.625rem;
  margin-top: 1rem;
}
.stacked-leg-item {
  display: flex;
  align-items: center;
  gap: 5px;
  font-size: 0.7rem;
  color: var(--text-2);
}
.stacked-leg-dot { width: 10px; height: 10px; border-radius: 2px; }
```

- [ ] **Step 5: Estilos do pizza chart (opinião)**

```css
/* ── Pizza chart — opinião ── */
.pie-wrap {
  display: flex;
  align-items: center;
  gap: 1.5rem;
  margin-top: 0.5rem;
}
.pie-legend { display: flex; flex-direction: column; gap: 0.625rem; }
.pie-item   { display: flex; align-items: center; gap: 0.5rem; font-size: 0.78rem; }
.pie-dot    { width: 10px; height: 10px; border-radius: 50%; flex-shrink: 0; }
.pie-item-label { color: var(--text-2); flex: 1; }
.pie-item-val   { font-weight: 700; color: var(--text); }
.pie-badges {
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem;
  margin-top: 1rem;
  padding-top: 0.75rem;
  border-top: 1px solid var(--border);
}
.pie-badge {
  font-size: 0.72rem;
  border-radius: 4px;
  padding: 2px 8px;
  font-weight: 600;
}
.pie-badge.ok   { background: #E8F5EE; color: var(--ok); }
.pie-badge.warn { background: #FFF4E5; color: var(--warn); }
.pie-badge.red  { background: #FBE9EB; color: var(--red); }
.pie-badge.neu  { background: var(--surface-2); color: var(--neutral); }
```

- [ ] **Step 6: Verificar visual no browser**

Recarregar `http://localhost:8003`. Os containers devem estar visíveis com layout correto mesmo sem dados (valores "—"). Não deve haver erros de CSS.

- [ ] **Step 7: Commit**

```bash
git add site-v3/style.css
git commit -m "feat: adiciona estilos dos KPIs hero, cards secundários e gráficos novos"
```

---

## Task 3: Atualizar `app.js` — nav, filtros e KPIs hero

**Files:**
- Modify: `site-v3/app.js`

- [ ] **Step 1: Atualizar label do nav**

Localizar em `NAV_ITEMS` o item com `id: 'index'` e alterar o label:

```js
{ id: 'index', href: 'index.html', label: 'Observatório de Contas',
  icon: '<path d="M3 9l9-7 9 7v11a2 2 0 01-2 2H5a2 2 0 01-2-2z"/><polyline points="9 22 9 12 15 12 15 22"/>' },
```

- [ ] **Step 2: Adicionar helper `opiniaoMaisFrequente`**

Adicionar após a função `bindSelect`:

```js
function opiniaoMaisFrequente(relatorios) {
  const cnt = {};
  relatorios.forEach(r => {
    const op = r.opiniao_auditoria || 'Não identificada';
    cnt[op] = (cnt[op] || 0) + 1;
  });
  const total = relatorios.length;
  if (!total) return { nome: '—', pct: '' };
  const [nome] = Object.entries(cnt).sort((a, b) => b[1] - a[1])[0];
  const p = Math.round(cnt[nome] / total * 100);
  return { nome, pct: p + '%' };
}
```

- [ ] **Step 3: Adicionar helper `calcDelta`**

Adicionar após `opiniaoMaisFrequente`:

```js
function calcDelta(atual, anterior, tipo = 'abs') {
  if (anterior == null || anterior === 0) return null;
  if (tipo === 'pp') {
    const diff = Math.round((atual - anterior) * 10) / 10;
    return { diff, dir: diff > 0 ? 'dn' : diff < 0 ? 'up' : 'neu' };
  }
  const diff = atual - anterior;
  return { diff, dir: diff > 0 ? 'dn' : diff < 0 ? 'up' : 'neu' };
}

function renderDelta(elId, delta, tipo = 'abs') {
  const el = $(elId);
  if (!el) return;
  if (!delta) { el.textContent = ''; el.className = 'kpi-delta'; return; }
  const sinal = delta.diff > 0 ? '↑' : delta.diff < 0 ? '↓' : '→';
  const abs = Math.abs(delta.diff);
  const sufixo = tipo === 'pp' ? ' p.p. vs ano anterior' : ' vs ano anterior';
  el.textContent = `${sinal} ${abs}${sufixo}`;
  el.className = `kpi-delta ${delta.dir}`;
}
```

- [ ] **Step 4: Adicionar helper `anosAnterior`**

```js
function anosData(anoAtual) {
  const anos = DATA.agregacoes.totais.anos ?? [];
  const idx  = anos.indexOf(Number(anoAtual));
  return { anos, anoAnterior: idx > 0 ? anos[idx - 1] : null };
}
```

- [ ] **Step 5: Reescrever início de `renderIndex()` — filtros e hero KPIs**

Substituir o trecho de `renderIndex()` que vai da linha `const ano = getNavYear()` até o final do bloco de KPIs (até `$('hero-anos').textContent = ...`) pelo seguinte:

```js
function renderIndex() {
  const ano  = getNavYear();
  const muni = $('f-municipio')?.value ?? '';
  const achados = filterAchados({ ano, municipio: muni });
  const total   = achados.length;

  // preencher f-ano e sincronizar com nav-year
  const anos = DATA.agregacoes.totais.anos ?? [];
  const fAno = $('f-ano');
  if (fAno && fAno.options.length === 1) {
    anos.forEach(a => {
      const o = document.createElement('option');
      o.value = a; o.textContent = a;
      fAno.appendChild(o);
    });
  }
  if (fAno && fAno.value !== ano) fAno.value = ano;
  if (!fAno?.dataset.bound) {
    if (fAno) fAno.dataset.bound = '1';
    fAno?.addEventListener('change', () => {
      const y = $('nav-year'); const yd = $('nav-year-drawer');
      if (y)  y.value  = fAno.value;
      if (yd) yd.value = fAno.value;
      renderIndex();
    });
  }

  // preencher f-municipio
  const allMunis = [...new Set(DATA.achados.map(a => a.municipio).filter(Boolean))].sort();
  populateSelect('f-municipio', allMunis);
  if (muni) $('f-municipio').value = muni;
  bindSelect('f-municipio', renderIndex);

  // botão limpar
  const rst = $('btn-reset');
  if (rst && !rst.dataset.bound) {
    rst.dataset.bound = '1';
    rst.addEventListener('click', () => {
      ['f-municipio', 'f-ano', 'nav-year', 'nav-year-drawer'].forEach(id => {
        const el = $(id); if (el) el.value = '';
      });
      renderIndex();
    });
  }

  // ── Hero KPIs ──
  const relIds = [...new Set(achados.map(a => a.relatorio_id))];
  $('kpi-relatorios').textContent = fmtN(relIds.length);
  $('kpi-achados').textContent    = fmtN(total);

  // Opinião mais frequente — baseada nos relatórios filtrados por ano/município
  const relsAtivos = DATA.relatorios.filter(r =>
    (!ano  || String(r.ano) === ano) &&
    (!muni || r.municipio === muni)
  );
  const { nome: opNome, pct: opPct } = opiniaoMaisFrequente(relsAtivos);
  const opEl = $('kpi-opiniao');
  if (opEl) opEl.innerHTML = `<span>${escHtml(opNome)}</span><span class="sep">·</span><span>${escHtml(opPct)}</span>`;

  // Deltas (só quando há ano selecionado e sem filtro de município)
  const { anoAnterior } = anosData(ano);
  const showDelta = ano && !muni;

  if (showDelta && anoAnterior) {
    const achAnt = filterAchados({ ano: String(anoAnterior), municipio: '' });
    const relAnt = [...new Set(achAnt.map(a => a.relatorio_id))];
    renderDelta('kpi-relatorios-delta', calcDelta(relIds.length, relAnt.length, 'abs'), 'abs');
    renderDelta('kpi-achados-delta',    calcDelta(total, achAnt.length, 'abs'), 'abs');
  } else {
    renderDelta('kpi-relatorios-delta', null);
    renderDelta('kpi-achados-delta',    null);
  }

  $('hero-anos').textContent = '· Anos disponíveis: ' + anos.join(' · ') + ' ·';
```

Nota: não feche o `}` ainda — o restante de `renderIndex()` vem nas tasks seguintes.

- [ ] **Step 6: Verificar no browser**

Recarregar `http://localhost:8003`. Os 3 KPIs hero devem mostrar números reais. Com ano 2024 selecionado, os deltas devem aparecer em verde/vermelho. Opinião deve mostrar "Reg. c/ Ressalvas · 72%" (ou o valor real do JSON).

- [ ] **Step 7: Commit**

```bash
git add site-v3/app.js
git commit -m "feat: atualiza nav e hero KPIs com deltas e opinião mais frequente"
```

---

## Task 4: Atualizar `app.js` — cards secundários

**Files:**
- Modify: `site-v3/app.js`

- [ ] **Step 1: Adicionar helpers `setText` e `renderSecDelta`**

Adicionar junto dos outros helpers (após `renderDelta`):

```js
function setText(id, val) {
  const el = $(id); if (el) el.textContent = val;
}

function renderSecDelta(id, diff, invertido = false) {
  const el = $(id);
  if (!el) return;
  if (diff === 0) { el.textContent = '→ Estável'; el.className = 'sec-card-delta'; return; }
  const sinal  = diff > 0 ? '↑' : '↓';
  const classe = diff > 0 ? (invertido ? 'up' : 'dn') : (invertido ? 'dn' : 'up');
  el.textContent = `${sinal} ${Math.abs(diff)} p.p. vs ${DATA.agregacoes.totais.anos.slice(-2)[0]}`;
  el.className   = `sec-card-delta ${classe}`;
}
```

Nota: `invertido = true` no `sc-sanados-delta` porque aumento em sanados é positivo (verde), ao contrário de mantidos onde aumento é ruim (vermelho).

- [ ] **Step 2: Renderizar os 4 cards secundários**

Adicionar imediatamente após o bloco `$('hero-anos').textContent = ...` dentro de `renderIndex()`:

```js
  // ── Badge de seção ──
  const secBadge = $('section-badge-ano');
  if (secBadge) secBadge.textContent = ano || 'Todos os anos';

  // ── Cards secundários ──
  const muniCount = [...new Set(achados.map(a => a.municipio).filter(Boolean))].length;
  const mantidos  = achados.filter(a => a.situacao === 'mantido').length;
  const sanados   = achados.filter(a =>
    a.situacao === 'sanado_total' || a.situacao === 'sanado_parcial' || a.situacao === 'afastado'
  ).length;
  const comDefesa = achados.filter(a => a.houve_defesa).length;

  const pctMantidos = total ? Math.round(mantidos / total * 100) : 0;
  const pctSanados  = total ? Math.round(sanados  / total * 100) : 0;
  const pctDefesa   = total ? Math.round(comDefesa / total * 100) : 0;

  setText('sc-municipios', fmtN(muniCount));
  setText('sc-mantidos',   total ? pctMantidos + '%' : '—');
  setText('sc-sanados',    total ? pctSanados  + '%' : '—');
  setText('sc-defesa',     total ? pctDefesa   + '%' : '—');

  // Deltas dos cards (só com ano ativo e sem filtro de município)
  if (showDelta && anoAnterior) {
    const achAnt = filterAchados({ ano: String(anoAnterior), municipio: '' });
    const totAnt = achAnt.length;
    const mantAnt = totAnt ? Math.round(achAnt.filter(a => a.situacao === 'mantido').length / totAnt * 100) : 0;
    const sanAnt  = totAnt ? Math.round(achAnt.filter(a =>
      a.situacao === 'sanado_total' || a.situacao === 'sanado_parcial' || a.situacao === 'afastado'
    ).length / totAnt * 100) : 0;

    renderSecDelta('sc-mantidos-delta', pctMantidos - mantAnt);
    renderSecDelta('sc-sanados-delta',  pctSanados  - sanAnt, true);
  } else {
    ['sc-mantidos-delta', 'sc-sanados-delta'].forEach(id => {
      const el = $(id); if (el) { el.textContent = ''; el.className = 'sec-card-delta'; }
    });
  }
```

- [ ] **Step 3: Verificar no browser**

Recarregar `http://localhost:8003`. Com filtro em 2024: 4 cards devem mostrar valores reais com percentuais. Os deltas de "Achados mantidos" e "Achados sanados" devem aparecer. Sem filtro de ano: deltas devem sumir.

- [ ] **Step 4: Commit**

```bash
git add site-v3/app.js
git commit -m "feat: renderiza cards secundários com percentuais e deltas"
```

---

## Task 5: Atualizar `app.js` — gráficos existentes (situação, tipo, municípios)

**Files:**
- Modify: `site-v3/app.js`

- [ ] **Step 1: Adicionar helper `buildBarListColor`**

Adicionar junto dos outros helpers de chart (após `buildBarList`):

```js
function buildBarListColor(items, maxVal) {
  if (!items.length) return '<div class="empty-state"><p>Sem dados</p></div>';
  return `<div class="bar-list">${items.map(([label, count, color]) => `
    <div class="bar-row">
      <div class="bar-meta">
        <span class="bar-name">${escHtml(label)}</span>
        <span class="bar-count">${fmtN(count)} · ${pct(count, maxVal)}</span>
      </div>
      <div class="bar-track">
        <div class="bar-fill" style="width:${pct(count, maxVal)};background:${color}"></div>
      </div>
    </div>`).join('')}</div>`;
}
```

- [ ] **Step 2: Atualizar renderização de "Situação dos achados"**

O gráfico de situação já existe mas usa `buildBarList` genérico. Garantir a ordenação correta (mantido primeiro) e cores semânticas. Localizar o trecho que popula `chart-situacao` e substituir por:

```js
  // ── Gráfico situação ──
  $('badge-total-sit').textContent = fmtN(total) + ' achados';
  const sitCount = {};
  achados.forEach(a => { const s = a.situacao || 'nao_consta'; sitCount[s] = (sitCount[s] || 0) + 1; });
  const sitOrder  = ['mantido', 'sanado_total', 'sanado_parcial', 'afastado', 'nao_consta'];
  const sitColorCss = { mantido: 'var(--red)', sanado_total: 'var(--ok)', sanado_parcial: 'var(--warn)', afastado: 'var(--neutral)', nao_consta: 'var(--muted)' };
  const sitItems  = sitOrder.filter(s => sitCount[s]).map(s => [SITUACAO_LABEL[s] || s, sitCount[s], sitColorCss[s]]);
  $('chart-situacao').innerHTML = buildBarListColor(sitItems, total);
```

- [ ] **Step 3: Atualizar "Achados por tipo"**

Localizar o trecho que popula `chart-tipo` e substituir por:

```js
  // ── Gráfico tipo ──
  const tipoCount = {};
  achados.forEach(a => { if (a.tipo) tipoCount[a.tipo] = (tipoCount[a.tipo] || 0) + 1; });
  const tipoItems = Object.entries(tipoCount)
    .sort((a, b) => b[1] - a[1])
    .slice(0, 10)
    .map(([label, count], i) => {
      const opacity = Math.max(0.25, 1 - i * 0.1).toFixed(2);
      return [label, count, `rgba(28,88,140,${opacity})`];
    });
  $('chart-tipo').innerHTML = buildBarListColor(tipoItems, total || 1);
```

- [ ] **Step 4: Atualizar "Top municípios"**

Localizar o trecho que popula `chart-municipios` e substituir por:

```js
  // ── Gráfico top municípios ──
  const muniAgg = {};
  achados.forEach(a => {
    if (!a.municipio) return;
    if (!muniAgg[a.municipio]) muniAgg[a.municipio] = { total: 0, sit: {} };
    muniAgg[a.municipio].total++;
    const s = a.situacao || 'nao_consta';
    muniAgg[a.municipio].sit[s] = (muniAgg[a.municipio].sit[s] || 0) + 1;
  });
  const muniTop = Object.entries(muniAgg)
    .sort((a, b) => b[1].total - a[1].total)
    .slice(0, 10);
  $('badge-total-muni').textContent = muniTop.length + ' municípios';
  $('chart-municipios').innerHTML = muniTop.length
    ? `<div class="bar-list">${muniTop.map(([nome, d], i) => {
        const dom = Object.entries(d.sit).sort((a,b) => b[1]-a[1])[0]?.[0] ?? 'nao_consta';
        const barColor = { mantido:'var(--red)', sanado_total:'var(--ok)', sanado_parcial:'var(--warn)', afastado:'var(--neutral)', nao_consta:'var(--muted)' }[dom] ?? 'var(--muted)';
        const w = pct(d.total, muniTop[0][1].total);
        return `<div class="bar-row" style="cursor:pointer" onclick="location.href='achados.html?municipio=${encodeURIComponent(nome)}'">
          <div class="bar-meta">
            <span class="bar-name">${i+1}. ${escHtml(nome)}</span>
            <span class="bar-count">${fmtN(d.total)}</span>
          </div>
          <div class="bar-track"><div class="bar-fill" style="width:${w};background:${barColor}"></div></div>
        </div>`;
      }).join('')}</div>`
    : '<div class="empty-state"><p>Sem dados</p></div>';
```

- [ ] **Step 5: Verificar no browser**

Recarregar `http://localhost:8003`. Os 3 gráficos (situação, tipo, municípios) devem renderizar com dados reais e cores corretas.

- [ ] **Step 6: Commit**

```bash
git add site-v3/app.js
git commit -m "feat: atualiza gráficos de situação, tipo e municípios com cores semânticas"
```

---

## Task 6: Atualizar `app.js` — novos gráficos (evolução e pizza)

**Files:**
- Modify: `site-v3/app.js`

- [ ] **Step 1: Adicionar helper `buildStackedBars`**

```js
function buildStackedBars(rows) {
  // rows: [{ano, segs: [{color, pct}], total}]
  const LEGEND = [
    { key: 'mantido',      color: 'var(--red)',     label: 'Mantido' },
    { key: 'sanado_total', color: 'var(--ok)',      label: 'Sanado total' },
    { key: 'sanado_parcial',color:'var(--warn)',    label: 'Sanado parcial' },
    { key: 'afastado',     color: 'var(--neutral)', label: 'Afastado' },
    { key: 'nao_consta',   color: 'var(--muted)',   label: 'Não consta' },
  ];
  const rowsHtml = rows.map(r => {
    const segs = LEGEND.map(l => {
      const w = r.total ? Math.round(r.sit[l.key] / r.total * 100) : 0;
      return w ? `<div class="stacked-seg" style="width:${w}%;background:${l.color}"></div>` : '';
    }).join('');
    return `<div class="stacked-row">
      <div class="stacked-year">${r.ano}</div>
      <div class="stacked-bar">${segs}</div>
      <div class="stacked-total">${fmtN(r.total)}</div>
    </div>`;
  }).join('');
  const legendHtml = LEGEND.map(l =>
    `<div class="stacked-leg-item">
      <div class="stacked-leg-dot" style="background:${l.color}"></div>${l.label}
    </div>`).join('');
  return `<div class="stacked-wrap">${rowsHtml}</div><div class="stacked-legend">${legendHtml}</div>`;
}
```

- [ ] **Step 2: Adicionar helper `buildPieChart`**

```js
function buildPieChart(entries) {
  // entries: [{label, count, color, badgeClass}]
  const total = entries.reduce((s, e) => s + e.count, 0);
  if (!total) return '<div class="empty-state"><p>Sem dados</p></div>';

  // SVG doughnut com stroke-dasharray
  const R = 15.9, CIRC = 2 * Math.PI * R;
  let offset = 25; // começar do topo
  const slices = entries.map(e => {
    const pctVal = e.count / total;
    const dash   = (pctVal * 100).toFixed(1);
    const svg = `<circle cx="21" cy="21" r="${R}" fill="transparent"
      stroke="${e.color}" stroke-width="10"
      stroke-dasharray="${dash} ${(100 - pctVal * 100).toFixed(1)}"
      stroke-dashoffset="${offset > 0 ? -offset + 25 : 25}"
      transform="rotate(-90 21 21)"/>`;
    offset += pctVal * 100;
    return svg;
  }).join('');

  const legendHtml = entries.map(e => {
    const p = Math.round(e.count / total * 100);
    return `<div class="pie-item">
      <div class="pie-dot" style="background:${e.color}"></div>
      <div class="pie-item-label">${escHtml(e.label)}</div>
      <div class="pie-item-val">${p}%</div>
    </div>`;
  }).join('');

  const badgesHtml = entries.map(e =>
    `<span class="pie-badge ${e.badgeClass}">${fmtN(e.count)} ${escHtml(e.label.split(' ')[0].toLowerCase())}</span>`
  ).join('');

  return `<div class="pie-wrap">
    <svg width="110" height="110" viewBox="0 0 42 42" style="flex-shrink:0">
      <circle cx="21" cy="21" r="${R}" fill="transparent" stroke="var(--border)" stroke-width="10"/>
      ${slices}
      <circle cx="21" cy="21" r="11" fill="white"/>
      <text x="21" y="23.5" text-anchor="middle" font-size="5"
        font-family="Sora,sans-serif" font-weight="800" fill="#18293C">${fmtN(total)}</text>
    </svg>
    <div class="pie-legend">${legendHtml}</div>
  </div>
  <div class="pie-badges">${badgesHtml}</div>`;
}
```

- [ ] **Step 3: Renderizar gráfico de evolução por ano**

Adicionar dentro de `renderIndex()`, após o bloco dos cards secundários:

```js
  // ── Evolução por ano ──
  const anosDisp = DATA.agregacoes.totais.anos ?? [];
  const evolRows = anosDisp.map(a => {
    const achAno = filterAchados({ ano: String(a), municipio: muni });
    const sit = {};
    achAno.forEach(x => { const s = x.situacao || 'nao_consta'; sit[s] = (sit[s] || 0) + 1; });
    return { ano: a, sit, total: achAno.length };
  });
  $('chart-evolucao').innerHTML = evolRows.length
    ? buildStackedBars(evolRows)
    : '<div class="empty-state"><p>Sem dados</p></div>';
```

- [ ] **Step 4: Renderizar gráfico de pizza (opinião)**

Adicionar imediatamente após o bloco de evolução:

```js
  // ── Pizza opinião da auditoria ──
  const OPINIAO_CONFIG = [
    { match: v => /regular\s+c(om|\/)\s*ressalva/i.test(v), color: 'var(--warn)', badgeClass: 'warn' },
    { match: v => /^regular$/i.test(v.trim()),               color: 'var(--ok)',   badgeClass: 'ok'   },
    { match: v => /irregular/i.test(v),                      color: 'var(--red)',  badgeClass: 'red'  },
  ];
  const opinionAgg = {};
  relsAtivos.forEach(r => {
    const op = r.opiniao_auditoria || 'Não identificada';
    opinionAgg[op] = (opinionAgg[op] || 0) + 1;
  });
  const pizzaEntries = Object.entries(opinionAgg)
    .sort((a, b) => b[1] - a[1])
    .map(([label, count]) => {
      const cfg = OPINIAO_CONFIG.find(c => c.match(label));
      return { label, count, color: cfg?.color ?? 'var(--neutral)', badgeClass: cfg?.badgeClass ?? 'neu' };
    });
  $('chart-opiniao-pizza').innerHTML = buildPieChart(pizzaEntries);
```

- [ ] **Step 5: Fechar o `}` de `renderIndex()` e remover código antigo**

Certificar que o `}` que fecha `renderIndex()` está ao final do bloco. Remover quaisquer referências antigas a `kpi-saneados`, `chart-opiniao` (o antigo de barras), e qualquer `$('chart-municipios')` duplicado dos blocos anteriores que o `renderIndex` original tinha.

- [ ] **Step 6: Smoke test completo**

```bash
python -m http.server -d site-v3 8003
```

Verificar:
1. Hero: 3 KPIs com valores reais. Com 2024: deltas visíveis. Sem ano: deltas somem.
2. Cards secundários: 4 cards com percentuais reais na ordem correta.
3. Gráfico situação: barras coloridas, mantido primeiro.
4. Gráfico evolução: barras empilhadas por ano.
5. Gráfico tipo: barras azuis com opacidade decrescente.
6. Top municípios: 10 municípios com mini-barra colorida. Clique navega para achados.html.
7. Pizza: fatias coloridas com legenda e badges.
8. Filtro município: todos os 7 itens acima rerenderizam.
9. Botão "Limpar filtros": reseta ano e município, rerenderiza.
10. Sem erros no console do browser.

- [ ] **Step 7: Commit final**

```bash
git add site-v3/app.js
git commit -m "feat: adiciona gráficos de evolução por ano e pizza de opinião da auditoria"
```
