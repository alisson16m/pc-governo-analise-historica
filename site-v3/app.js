'use strict';

/* ── Estado global ── */
let DATA = null;
let FILTERED_ACHADOS = [];
let _achadoPage = 1;
const ACHADOS_PER_PAGE = 25;

const PAGE_IDS = {
  'index.html': 'index', '': 'index',
  'achados.html': 'achados',
  'municipios.html': 'municipios',
  'secoes.html': 'secoes',
  'defesa.html': 'defesa',
  'pareceres.html': 'pareceres',
  'insights.html': 'insights',
  'sobre.html': 'sobre',
};

const SITUACAO_LABEL = {
  mantido: 'Mantido',
  sanado_total: 'Sanado Total',
  sanado_parcial: 'Sanado Parcial',
  afastado: 'Afastado',
};
const SITUACAO_COLOR = {
  mantido: 'red', sanado_total: 'green', sanado_parcial: 'orange',
  afastado: 'gray',
};
const SITUACAO_BADGE = {
  mantido: 'badge-red', sanado_total: 'badge-green', sanado_parcial: 'badge-orange',
  afastado: 'badge-gray',
};

/* ── Utilitários ── */
function pct(n, total) { return total ? Math.round(n / total * 100) + '%' : '0%'; }
function fmtN(n) { return n == null ? '—' : n.toLocaleString('pt-BR'); }
function escHtml(s) {
  if (!s) return '';
  return String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}
function currentPage() {
  const path = location.pathname.split('/').pop();
  return PAGE_IDS[path] ?? 'index';
}
function getNavYear() { return document.getElementById('nav-year')?.value ?? ''; }
function $(id) { return document.getElementById(id); }

/* ── Filtrar achados ── */
function filterAchados({ ano = '', municipio = '', tipo = '', situacao = '', secao = '' } = {}) {
  return DATA.achados.filter(a =>
    (!ano       || String(a.ano) === ano) &&
    (!municipio || a.municipio === municipio) &&
    (!tipo      || a.tipo === tipo) &&
    (!situacao  || a.situacao === situacao) &&
    (!secao     || a.secao === secao)
  );
}

/* ── Bar chart ── */
function buildBarList(items, maxVal, colorFn) {
  if (!items.length) return '<div class="empty-state"><p>Sem dados para o filtro selecionado</p></div>';
  return `<div class="bar-list">${items.map(([label, count]) => `
    <div class="bar-row">
      <div class="bar-meta">
        <span class="bar-name">${escHtml(label)}</span>
        <span class="bar-count">${fmtN(count)} (${pct(count, maxVal)})</span>
      </div>
      <div class="bar-track">
        <div class="bar-fill ${colorFn(label)}" style="width:${pct(count, maxVal)}"></div>
      </div>
    </div>`).join('')}</div>`;
}

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

function buildStackedBars(rows) {
  const LEGEND = [
    { key: 'mantido',       color: 'var(--red)',     label: 'Mantido' },
    { key: 'sanado_total',  color: 'var(--ok)',      label: 'Sanado total' },
    { key: 'sanado_parcial',color: 'var(--warn)',    label: 'Sanado parcial' },
    { key: 'afastado',      color: 'var(--neutral)', label: 'Afastado' },
  ];
  const rowsHtml = rows.map(r => {
    const segs = LEGEND.map(l => {
      const count = r.sit[l.key] || 0;
      const w = r.total ? Math.round(count / r.total * 100) : 0;
      const tip = `${l.label} · ${fmtN(count)} achados (${r.total ? Math.round(count / r.total * 100) : 0}%)`;
      return w ? `<div class="stacked-seg" style="width:${w}%;background:${l.color}" data-tip="${tip}"></div>` : '';
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

function buildColumnChart(items, maxVal) {
  const BAR_H = 150;
  if (!items.length) return '<div class="empty-state"><p>Sem dados para o filtro selecionado</p></div>';
  return `<div class="col-chart">${items.map(([label, count, color]) => {
    const h = maxVal ? Math.round(count / maxVal * BAR_H) : 0;
    const short = label.length > 18 ? label.slice(0, 16) + '…' : label;
    return `<div class="col-item">
      <span class="col-count">${fmtN(count)}</span>
      <div class="col-bar" style="height:${h}px;background:${color}"></div>
      <span class="col-name" title="${escHtml(label)}">${escHtml(short)}</span>
    </div>`;
  }).join('')}</div>`;
}

function buildPieChart(entries) {
  const total = entries.reduce((s, e) => s + e.count, 0);
  if (!total) return '<div class="empty-state"><p>Sem dados</p></div>';

  const R = 15.9;
  let offset = 0;
  const slices = entries.map(e => {
    const pctVal = e.count / total;
    const dash   = (pctVal * 100).toFixed(1);
    const gap    = (100 - pctVal * 100).toFixed(1);
    const rot    = -90 + (offset / 100) * 360;
    const svg = `<circle cx="21" cy="21" r="${R}" fill="transparent"
      stroke="${e.color}" stroke-width="10"
      stroke-dasharray="${dash} ${gap}"
      stroke-dashoffset="0"
      transform="rotate(${rot} 21 21)"/>`;
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

/* ── Populate select ── */
function populateSelect(id, values, labelMap = {}) {
  const el = $(id);
  if (!el || el.options.length > 1) return;
  values.forEach(v => {
    const o = document.createElement('option');
    o.value = v; o.textContent = labelMap[v] || v;
    el.appendChild(o);
  });
}

function bindSelect(id, fn) {
  const el = $(id);
  if (el && !el.dataset.bound) { el.dataset.bound = '1'; el.addEventListener('change', fn); }
}

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

function anosData(anoAtual) {
  const anos = DATA.agregacoes.totais.anos ?? [];
  const idx  = anos.indexOf(Number(anoAtual));
  return { anos, anoAnterior: idx > 0 ? anos[idx - 1] : null };
}

/* ── Nav ── */
const NAV_ITEMS = [
  { id: 'index',      href: 'index.html',     label: 'Visão Geral',
    icon: '<path d="M3 9l9-7 9 7v11a2 2 0 01-2 2H5a2 2 0 01-2-2z"/><polyline points="9 22 9 12 15 12 15 22"/>' },
  { id: 'achados',    href: 'achados.html',    label: 'Banco de Achados',
    icon: '<line x1="8" y1="6" x2="21" y2="6"/><line x1="8" y1="12" x2="21" y2="12"/><line x1="8" y1="18" x2="21" y2="18"/><circle cx="3" cy="6" r="1.5" fill="currentColor" stroke="none"/><circle cx="3" cy="12" r="1.5" fill="currentColor" stroke="none"/><circle cx="3" cy="18" r="1.5" fill="currentColor" stroke="none"/>' },
  { id: 'municipios', href: 'municipios.html', label: 'Municípios',
    icon: '<path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0118 0z"/><circle cx="12" cy="10" r="3"/>' },
  { id: 'secoes',     href: 'secoes.html',     label: 'Por Seção',
    icon: '<polygon points="12 2 2 7 12 12 22 7 12 2"/><polyline points="2 17 12 22 22 17"/><polyline points="2 12 12 17 22 12"/>' },
  { id: 'defesa',     href: 'defesa.html',     label: 'Defesa do Gestor',
    icon: '<path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/>' },
  { id: 'pareceres',  href: 'pareceres.html',  label: 'Opinião do Auditor',
    icon: '<path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="9" y1="13" x2="15" y2="13"/>' },
  { id: 'insights',   href: 'insights.html',   label: 'Insights',
    icon: '<circle cx="12" cy="12" r="5"/><line x1="12" y1="1" x2="12" y2="3"/><line x1="12" y1="21" x2="12" y2="23"/><line x1="4.22" y1="4.22" x2="5.64" y2="5.64"/><line x1="18.36" y1="18.36" x2="19.78" y2="19.78"/>' },
  { id: 'sobre',      href: 'sobre.html',      label: 'Sobre',
    icon: '<circle cx="12" cy="12" r="10"/><line x1="12" y1="16" x2="12" y2="12"/><line x1="12" y1="8" x2="12.01" y2="8"/>' },
];

function buildNav() {
  const active = currentPage();
  const anos = DATA.agregacoes.totais.anos ?? [];
  const yearOpts = ['<option value="">Todos os anos</option>',
    ...anos.map(a => `<option value="${a}">${a}</option>`)].join('');

  const linkHtml = NAV_ITEMS.map(item => `
    <a href="${item.href}" class="nav-link${item.id === active ? ' active' : ''}">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">${item.icon}</svg>
      ${item.label}
    </a>`).join('');

  $('nav-links').innerHTML = linkHtml;
  $('nav-drawer-links').innerHTML = linkHtml;
  $('nav-year').innerHTML = yearOpts;
  $('nav-year-drawer').innerHTML = yearOpts;

  // hamburger
  $('nav-hamburger').addEventListener('click', () => $('nav-drawer').classList.toggle('open'));

  // sync year selectors & re-render
  function syncYear(src, dst) {
    $(dst).value = $(src).value;
    onYearChange();
  }
  $('nav-year').addEventListener('change', () => syncYear('nav-year', 'nav-year-drawer'));
  $('nav-year-drawer').addEventListener('change', () => syncYear('nav-year-drawer', 'nav-year'));

  // apply ?municipio= URL param
  const params = new URLSearchParams(location.search);
  const muniParam = params.get('municipio');
  if (muniParam) {
    const sel = $('f-municipio');
    if (sel) sel.value = muniParam;
  }
}

function onYearChange() {
  const pg = currentPage();
  if (pg === 'index')      renderIndex();
  if (pg === 'achados')    renderAchados();
  if (pg === 'municipios') renderMunicipios();
  if (pg === 'secoes')     renderSecoes();
  if (pg === 'defesa')     renderDefesa();
  if (pg === 'pareceres')  renderPareceres();
}

/* ════════════════════════════════════════
   HOMEPAGE — index.html
════════════════════════════════════════ */
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

  // ── Badge de seção ──
  const secBadge = $('section-badge-ano');
  if (secBadge) secBadge.textContent = ano || 'Todos os anos';

  // ── Cards secundários ──
  const muniSetCount = [...new Set(achados.map(a => a.municipio).filter(Boolean))].length;
  const mantidos  = achados.filter(a => a.situacao === 'mantido').length;
  const sanados   = achados.filter(a =>
    a.situacao === 'sanado_total' || a.situacao === 'sanado_parcial' || a.situacao === 'afastado'
  ).length;
  const comDefesa = achados.filter(a => a.houve_defesa).length;

  const pctMantidos = total ? Math.round(mantidos / total * 100) : 0;
  const pctSanados  = total ? Math.round(sanados  / total * 100) : 0;
  const pctDefesa   = total ? Math.round(comDefesa / total * 100) : 0;

  setText('sc-municipios', fmtN(muniSetCount));
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

  // ── Gráfico situação ──
  $('badge-total-sit').textContent = fmtN(total) + ' achados';
  const sitCount = {};
  achados.forEach(a => { const s = a.situacao || 'nao_consta'; sitCount[s] = (sitCount[s] || 0) + 1; });
  const sitColorCss = { mantido: 'var(--red)', sanado_total: 'var(--ok)', sanado_parcial: 'var(--warn)', afastado: 'var(--neutral)' };
  const sitItems = Object.entries(sitCount)
    .filter(([s]) => sitColorCss[s])
    .sort((a, b) => b[1] - a[1])
    .map(([s, n]) => [SITUACAO_LABEL[s] || s, n, sitColorCss[s]]);
  $('chart-situacao').innerHTML = buildBarListColor(sitItems, total);

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
  const tipoMax = tipoItems[0]?.[1] || 1;
  $('chart-tipo').innerHTML = buildColumnChart(tipoItems, tipoMax);

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
    .slice(0, 5);
  $('badge-total-muni').textContent = muniTop.length + ' municípios';
  $('chart-municipios').innerHTML = muniTop.length
    ? `<div class="bar-list">${muniTop.map(([nome, d], i) => {
        const w = pct(d.total, muniTop[0][1].total);
        return `<div class="bar-row" style="cursor:pointer" onclick="location.href='achados.html?municipio=${encodeURIComponent(nome)}'">
          <div class="bar-meta">
            <span class="bar-name">${i+1}. ${escHtml(nome)}</span>
            <span class="bar-count">${fmtN(d.total)}</span>
          </div>
          <div class="bar-track"><div class="bar-fill blue" style="width:${w}"></div></div>
        </div>`;
      }).join('')}</div>`
    : '<div class="empty-state"><p>Sem dados</p></div>';

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
}

/* ════════════════════════════════════════
   BANCO DE ACHADOS — achados.html
════════════════════════════════════════ */
function renderAchados() {
  const ano    = getNavYear();
  const allMunis  = [...new Set(DATA.achados.map(a => a.municipio))].sort();
  const allTipos  = [...new Set(DATA.achados.map(a => a.tipo))].sort();
  const allSecoes = [...new Set(DATA.achados.map(a => a.secao))].sort();

  populateSelect('f-municipio', allMunis);
  populateSelect('f-tipo', allTipos);
  populateSelect('f-situacao', Object.keys(SITUACAO_LABEL), SITUACAO_LABEL);
  populateSelect('f-secao', allSecoes);

  // ler URL param na primeira vez
  const params = new URLSearchParams(location.search);
  const muniParam = params.get('municipio');
  if (muniParam && $('f-municipio') && !$('f-municipio').dataset.paramApplied) {
    $('f-municipio').value = muniParam;
    $('f-municipio').dataset.paramApplied = '1';
  }

  const termoBusca = (document.getElementById('f-busca')?.value || '').toLowerCase().trim();

  FILTERED_ACHADOS = filterAchados({
    ano,
    municipio: $('f-municipio')?.value ?? '',
    tipo:      $('f-tipo')?.value ?? '',
    situacao:  $('f-situacao')?.value ?? '',
    secao:     $('f-secao')?.value ?? '',
  }).filter(a => {
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
    return true;
  });

  $('badge-achados').textContent = fmtN(FILTERED_ACHADOS.length) + ' achados';
  renderAchadosPage(1);

  ['f-municipio', 'f-tipo', 'f-situacao', 'f-secao'].forEach(id =>
    bindSelect(id, () => { _achadoPage = 1; renderAchados(); })
  );
  const fBusca = document.getElementById('f-busca');
  if (fBusca && !fBusca.dataset.bound) {
    fBusca.dataset.bound = '1';
    fBusca.addEventListener('input', () => { _achadoPage = 1; renderAchados(); });
  }

  const rst = $('btn-reset');
  if (rst && !rst.dataset.bound) {
    rst.dataset.bound = '1';
    rst.addEventListener('click', () => {
      ['f-municipio', 'f-tipo', 'f-situacao', 'f-secao', 'nav-year', 'nav-year-drawer']
        .forEach(id => { const el = $(id); if (el) el.value = ''; });
      document.getElementById('f-busca').value = '';
      _achadoPage = 1; renderAchados();
    });
  }
}

function renderAchadosPage(page) {
  _achadoPage = page;
  const start = (page - 1) * ACHADOS_PER_PAGE;
  const slice = FILTERED_ACHADOS.slice(start, start + ACHADOS_PER_PAGE);
  const tbody = $('achados-body');

  tbody.innerHTML = slice.map((a, i) => {
    const idx = start + i;
    return `
    <tr class="accordion-row" onclick="openAchadoModal(${idx})">
      <td>${escHtml(a.municipio)}</td>
      <td>${a.ano}</td>
      <td class="mono">${escHtml(a.codigo)}</td>
      <td>${escHtml(a.tipo)}</td>
      <td><span class="badge ${SITUACAO_BADGE[a.situacao] || 'badge-gray'}">${SITUACAO_LABEL[a.situacao] || a.situacao}</span></td>
      <td style="width:32px"><span class="row-open-icon">↗</span></td>
    </tr>`;
  }).join('');

  // paginação
  const total = FILTERED_ACHADOS.length;
  const pages = Math.ceil(total / ACHADOS_PER_PAGE);
  const pag = $('achados-pag');
  if (pages <= 1) { pag.innerHTML = ''; return; }

  const btns = [];
  btns.push(`<button class="page-btn" onclick="renderAchadosPage(${page - 1})" ${page <= 1 ? 'disabled' : ''}>‹</button>`);
  for (let p = Math.max(1, page - 2); p <= Math.min(pages, page + 2); p++) {
    btns.push(`<button class="page-btn${p === page ? ' active' : ''}" onclick="renderAchadosPage(${p})">${p}</button>`);
  }
  btns.push(`<button class="page-btn" onclick="renderAchadosPage(${page + 1})" ${page >= pages ? 'disabled' : ''}>›</button>`);
  btns.push(`<span class="page-info">${fmtN(total)} resultados · página ${page} de ${pages}</span>`);
  pag.innerHTML = btns.join('');
}

const SITUACAO_MODAL_CLASS = {
  mantido: 'mantido', sanado_total: 'sanado', sanado_parcial: 'sanado-parcial',
  afastado: 'afastado', nao_consta: 'afastado',
};

function openAchadoModal(idx) {
  const a = FILTERED_ACHADOS[idx];
  if (!a) return;

  function set(id, text) { const el = $(id); if (el) el.textContent = text ?? ''; }
  function show(id, vis) { const el = $(id); if (el) el.style.display = vis ? '' : 'none'; }

  set('modal-super',     `Achado · ${a.ano}`);
  set('modal-municipio', a.municipio);
  set('modal-code',      a.codigo);
  set('modal-tipo',      a.tipo);

  const sitEl = $('modal-sit');
  sitEl.textContent = SITUACAO_LABEL[a.situacao] || a.situacao;
  sitEl.className   = `modal-badge-sit ${SITUACAO_MODAL_CLASS[a.situacao] || ''}`;

  set('modal-descricao', a.descricao);

  show('modal-wrap-rec',  !!a.recomendacao);
  if (a.recomendacao)  set('modal-recomendacao', a.recomendacao);

  show('modal-wrap-det',  !!a.determinacao);
  if (a.determinacao)  set('modal-determinacao', a.determinacao);

  show('modal-wrap-norm', !!a.base_normativa);
  if (a.base_normativa) set('modal-normativa', a.base_normativa);

  const temDefesa = a.defesa_gestor || a.analise_tecnica;
  show('modal-divider-def', !!temDefesa);

  show('modal-wrap-def', !!a.defesa_gestor);
  if (a.defesa_gestor)   set('modal-defesa-gestor', a.defesa_gestor);

  show('modal-wrap-ana', !!a.analise_tecnica);
  if (a.analise_tecnica) set('modal-analise-tecnica', a.analise_tecnica);

  set('modal-secao',    a.secao    || '—');
  set('modal-processo', a.numero_processo || '—');
  set('modal-relator',  a.relator  || '—');

  show('modal-wrap-sem-defesa', !a.houve_defesa);
  show('modal-sep-def',         !a.houve_defesa);

  $('modal-backdrop').style.display = 'flex';
  document.body.style.overflow = 'hidden';
}

function closeAchadoModal() {
  $('modal-backdrop').style.display = 'none';
  document.body.style.overflow = '';
}

function onModalBackdropClick(e) {
  if (e.target === $('modal-backdrop')) closeAchadoModal();
}

document.addEventListener('keydown', e => { if (e.key === 'Escape') closeAchadoModal(); });

/* ════════════════════════════════════════
   MUNICÍPIOS — municipios.html
════════════════════════════════════════ */
function renderMunicipios() {
  const ano = getNavYear();
  const achados = filterAchados({ ano });
  const munis = [...new Set(achados.map(a => a.municipio))].sort();
  const phSub = $('ph-sub');
  if (phSub) phSub.textContent = fmtN(munis.length) + ' municípios' + (ano ? ` · ${ano}` : '');

  const muniData = munis.map(nome => {
    const items = achados.filter(a => a.municipio === nome);
    const sit = {};
    items.forEach(a => { sit[a.situacao] = (sit[a.situacao] || 0) + 1; });
    const rel = DATA.relatorios.find(r => r.municipio === nome && (!ano || String(r.ano) === ano));
    return { nome, total: items.length, sit, opiniao: rel?.opiniao_auditoria };
  }).sort((a, b) => b.total - a.total);

  const opinBadge = o => o === 'Irregular' ? 'badge-red' : o === 'Regular' ? 'badge-green' : 'badge-orange';
  const SEG_COLORS = {
    mantido: 'var(--red)', sanado_total: 'var(--ok)',
    sanado_parcial: 'var(--warn)', afastado: 'var(--neutral)',
  };

  const grid = $('muni-grid');
  grid.innerHTML = muniData.map(m => {
    const segs = Object.entries(SEG_COLORS).map(([k, color]) => {
      const w = m.total ? Math.round((m.sit[k] || 0) / m.total * 100) : 0;
      return w ? `<div class="muni-bar-seg" style="width:${w}%;background:${color}" title="${SITUACAO_LABEL[k]}: ${m.sit[k] || 0}"></div>` : '';
    }).join('');
    return `
    <div class="muni-card" onclick="location.href='achados.html?municipio=${encodeURIComponent(m.nome)}'">
      <div class="muni-name">${escHtml(m.nome)}</div>
      <div class="muni-count">${fmtN(m.total)} achados</div>
      <div class="muni-bar-track">${segs}</div>
      <div class="muni-badges">
        ${m.opiniao ? `<span class="badge ${opinBadge(m.opiniao)}">${escHtml(m.opiniao)}</span>` : ''}
      </div>
    </div>`;
  }).join('') || '<div class="empty-state"><p>Nenhum município para o filtro selecionado</p></div>';
}

/* ════════════════════════════════════════
   SEÇÕES — secoes.html
════════════════════════════════════════ */
function renderSecoes() {
  const ano = getNavYear();
  const achados = filterAchados({ ano });
  const secCount = {};
  achados.forEach(a => { secCount[a.secao] = (secCount[a.secao] || 0) + 1; });
  const secItems = Object.entries(secCount).sort((a, b) => b[1] - a[1]);
  const secMax = secItems[0]?.[1] || 1;

  $('badge-secoes').textContent = fmtN(secItems.length) + ' seções';
  $('chart-secoes').innerHTML = buildBarList(secItems, secMax, () => 'blue');

  // Tipo por seção (top 5)
  const top5 = secItems.slice(0, 5);
  $('chart-tipo-secao').innerHTML = top5.map(([sec]) => {
    const items = achados.filter(a => a.secao === sec);
    const tipos = {};
    items.forEach(a => { tipos[a.tipo] = (tipos[a.tipo] || 0) + 1; });
    const shortSec = sec.replace(/^\d+\.\s*/, '').substring(0, 35);
    const rows = Object.entries(tipos).sort((a, b) => b[1] - a[1]);
    return `
    <div style="margin-bottom:1.25rem">
      <div style="font-size:0.78rem;font-weight:600;color:var(--text);margin-bottom:0.4rem">${escHtml(shortSec)}</div>
      <div class="bar-list" style="gap:0.4rem">${rows.map(([tipo, cnt]) => `
        <div class="bar-row">
          <div class="bar-meta">
            <span class="bar-name" style="font-size:0.76rem">${escHtml(tipo)}</span>
            <span class="bar-count" style="font-size:0.72rem">${cnt}</span>
          </div>
          <div class="bar-track" style="height:5px">
            <div class="bar-fill blue" style="width:${pct(cnt, items.length)}"></div>
          </div>
        </div>`).join('')}
      </div>
    </div>`;
  }).join('') || '<div class="empty-state"><p>Sem dados</p></div>';
}

/* ════════════════════════════════════════
   DEFESA DO GESTOR — defesa.html
════════════════════════════════════════ */
function renderDefesa() {
  const ano = getNavYear();
  const achados = filterAchados({ ano });
  const total  = achados.length;
  const comDef = achados.filter(a => a.houve_defesa);
  const semDef = achados.filter(a => !a.houve_defesa);

  $('defesa-narrative').innerHTML = `
    <div class="narrative-stat"><div class="narrative-n">${fmtN(total)}</div><div class="narrative-l">total de achados</div></div>
    <div class="narrative-stat"><div class="narrative-n">${fmtN(comDef.length)}</div><div class="narrative-l">com defesa (${pct(comDef.length, total)})</div></div>
    <div class="narrative-stat"><div class="narrative-n red">${fmtN(semDef.length)}</div><div class="narrative-l">sem defesa (${pct(semDef.length, total)})</div></div>`;

  function situacaoChart(items, containerId) {
    const sit = {};
    items.forEach(a => { sit[a.situacao] = (sit[a.situacao] || 0) + 1; });
    const rows = Object.entries(sit).sort((a, b) => b[1] - a[1]);
    const max = rows[0]?.[1] || 1;
    $(containerId).innerHTML = buildBarList(
      rows.map(([k, v]) => [SITUACAO_LABEL[k] || k, v]),
      max,
      l => { const k = Object.entries(SITUACAO_LABEL).find(([, v]) => v === l)?.[0]; return SITUACAO_COLOR[k] || 'gray'; }
    );
  }
  situacaoChart(comDef, 'chart-com-defesa');
  situacaoChart(semDef, 'chart-sem-defesa');
}

/* ════════════════════════════════════════
   OPINIÃO DO AUDITOR — pareceres.html
════════════════════════════════════════ */
function renderPareceres() {
  const ano = getNavYear();
  const rels = DATA.relatorios.filter(r => !ano || String(r.ano) === ano);
  $('badge-rel').textContent = fmtN(rels.length) + ' relatórios';

  // opiniões
  const opinCount = {};
  rels.forEach(r => { if (r.opiniao_auditoria) opinCount[r.opiniao_auditoria] = (opinCount[r.opiniao_auditoria] || 0) + 1; });
  const opinItems = Object.entries(opinCount).sort((a, b) => b[1] - a[1]);
  const opinMax = opinItems[0]?.[1] || 1;
  const opinColor = l => l === 'Irregular' ? 'red' : l === 'Regular' ? 'green' : 'orange';
  $('chart-opiniao-par').innerHTML = buildBarList(opinItems, opinMax, opinColor);

  // relatores
  const relCount = {};
  rels.forEach(r => { if (r.relator) relCount[r.relator] = (relCount[r.relator] || 0) + 1; });
  const relItems = Object.entries(relCount).sort((a, b) => b[1] - a[1]);
  const relMax = relItems[0]?.[1] || 1;
  $('chart-relator').innerHTML = buildBarList(relItems, relMax, () => 'blue');

  // tabela
  const opinBadge = o => o === 'Irregular' ? 'badge-red' : o === 'Regular' ? 'badge-green' : 'badge-orange';
  $('rel-body').innerHTML = rels.map(r => `
    <tr>
      <td>${escHtml(r.municipio)}</td>
      <td>${r.ano}</td>
      <td class="mono" style="font-size:0.75rem">${escHtml(r.numero_processo)}</td>
      <td>${escHtml(r.relator || '—')}</td>
      <td><span class="badge ${opinBadge(r.opiniao_auditoria)}">${escHtml(r.opiniao_auditoria || '—')}</span></td>
    </tr>`).join('');
}

/* ════════════════════════════════════════
   INSIGHTS — insights.html
════════════════════════════════════════ */
function renderInsights() {
  const ag = DATA.agregacoes;
  const t  = ag.totais;
  const sitAg = ag.por_situacao;
  const pctMantido  = Math.round((sitAg.mantido || 0) / t.achados * 100);
  const pctSaneado  = Math.round(((sitAg.sanado_total || 0) + (sitAg.sanado_parcial || 0) + (sitAg.afastado || 0)) / t.achados * 100);
  const topMuni  = Object.entries(ag.por_municipio).sort((a, b) => b[1] - a[1])[0];
  const topTipo  = Object.entries(ag.por_tipo).sort((a, b) => b[1] - a[1])[0];
  const topSecao = Object.entries(ag.por_secao).sort((a, b) => b[1] - a[1])[0];
  const comDefPct = Math.round(t.com_defesa / t.achados * 100);
  const defMantido = ag.defesa_x_situacao?.com_defesa?.mantido || 0;
  const defMantidoPct = t.com_defesa ? Math.round(defMantido / t.com_defesa * 100) : 0;
  const irregular = DATA.relatorios.filter(r => r.opiniao_auditoria === 'Irregular').length;

  const insights = [
    { cor: 'red',
      titulo: `${pctMantido}% dos achados foram mantidos`,
      texto: `De ${fmtN(t.achados)} achados analisados, ${fmtN(sitAg.mantido)} permanecem como irregularidade confirmada. Isso indica que a maioria das falhas identificadas não foi corrigida dentro do prazo do contraditório.` },
    { cor: 'green',
      titulo: `${pctSaneado}% foram saneados`,
      texto: `${fmtN((sitAg.sanado_total || 0) + (sitAg.sanado_parcial || 0) + (sitAg.afastado || 0))} achados foram corrigidos (total ou parcialmente) ou afastados após análise da defesa, demonstrando que o processo de contraditório produz resultados relevantes em parcela dos casos.` },
    { cor: '',
      titulo: `${escHtml(topMuni?.[0])} lidera em achados`,
      texto: `O município de ${escHtml(topMuni?.[0])} concentra ${fmtN(topMuni?.[1])} achados — o maior volume entre todos os municípios analisados no período.` },
    { cor: '',
      titulo: `"${escHtml(topTipo?.[0])}" é o tipo mais frequente`,
      texto: `${fmtN(topTipo?.[1])} achados (${pct(topTipo?.[1] || 0, t.achados)}) são classificados como ${escHtml(topTipo?.[0])}, sendo a categoria de achado dominante nas prestações de contas municipais.` },
    { cor: '',
      titulo: `Seção mais crítica: ${escHtml(topSecao?.[0]?.replace(/^\d+\.\s*/, '') || '')}`,
      texto: `A seção "${escHtml(topSecao?.[0])}" concentra ${fmtN(topSecao?.[1])} achados — a área de maior fragilidade nos controles municipais auditados pelo TCE-AL.` },
    { cor: 'red',
      titulo: `${comDefPct}% apresentaram defesa, mas ${defMantidoPct}% foram mantidos mesmo assim`,
      texto: `${fmtN(t.com_defesa)} achados tiveram manifestação de defesa do gestor. Destes, ${fmtN(defMantido)} (${defMantidoPct}%) foram mantidos, indicando que as justificativas raramente revertem as conclusões técnicas.` },
    { cor: irregular > 2 ? 'red' : 'green',
      titulo: `${irregular} relatório(s) com parecer Irregular`,
      texto: `De ${fmtN(t.relatorios)} relatórios analisados, ${irregular} receberam parecer "Irregular" — a classificação mais grave na escala de opiniões de auditoria do TCE-AL.` },
  ];

  $('insight-grid').innerHTML = insights.map(ins => `
    <div class="insight-card ${ins.cor}">
      <div class="insight-title">${ins.titulo}</div>
      <div class="insight-body">${ins.texto}</div>
    </div>`).join('');
}

/* ════════════════════════════════════════
   SOBRE — sobre.html
════════════════════════════════════════ */
function renderSobre() {
  const el = $('gerado-em');
  if (el && DATA.gerado_em) {
    el.textContent = new Date(DATA.gerado_em).toLocaleDateString('pt-BR', { dateStyle: 'long' });
  }
}

/* ════════════════════════════════════════
   TOOLTIP FLUTUANTE
════════════════════════════════════════ */
function initTooltip() {
  const tip = document.createElement('div');
  tip.id = 'seg-tip';
  tip.style.cssText = [
    'position:fixed', 'display:none', 'pointer-events:none', 'z-index:9999',
    'background:#18293C', 'color:#fff', 'font-size:0.72rem', 'font-weight:600',
    'padding:5px 10px', 'border-radius:6px', 'white-space:nowrap',
    'box-shadow:0 2px 8px rgba(0,0,0,0.25)',
  ].join(';');
  document.body.appendChild(tip);

  document.addEventListener('mouseover', e => {
    const el = e.target.closest('[data-tip]');
    if (!el) return;
    tip.textContent = el.dataset.tip;
    tip.style.display = 'block';
  });
  document.addEventListener('mouseout', e => {
    if (e.target.closest('[data-tip]')) tip.style.display = 'none';
  });
  document.addEventListener('mousemove', e => {
    if (tip.style.display === 'none') return;
    tip.style.left = (e.clientX + 14) + 'px';
    tip.style.top  = (e.clientY - 36) + 'px';
  });
}

/* ════════════════════════════════════════
   BOOTSTRAP
════════════════════════════════════════ */
async function init() {
  try {
    const res = await fetch('data.json');
    DATA = await res.json();
  } catch (e) {
    document.body.innerHTML = '<div style="padding:2rem;font-family:sans-serif;color:#A6121F"><h2>Erro ao carregar dados</h2><p>Inicie o servidor: <code>python -m http.server -d site-v3 8003</code></p></div>';
    return;
  }
  initTooltip();
  buildNav();
  const pg = currentPage();
  if (pg === 'index')      renderIndex();
  if (pg === 'achados')    renderAchados();
  if (pg === 'municipios') renderMunicipios();
  if (pg === 'secoes')     renderSecoes();
  if (pg === 'defesa')     renderDefesa();
  if (pg === 'pareceres')  renderPareceres();
  if (pg === 'insights')   renderInsights();
  if (pg === 'sobre')      renderSobre();
}

document.addEventListener('DOMContentLoaded', init);
