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
  nao_consta: 'Não Consta',
};
const SITUACAO_COLOR = {
  mantido: 'red', sanado_total: 'green', sanado_parcial: 'orange',
  afastado: 'gray', nao_consta: 'gray',
};
const SITUACAO_BADGE = {
  mantido: 'badge-red', sanado_total: 'badge-green', sanado_parcial: 'badge-orange',
  afastado: 'badge-gray', nao_consta: 'badge-gray',
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

function anosData(anoAtual) {
  const anos = DATA.agregacoes.totais.anos ?? [];
  const idx  = anos.indexOf(Number(anoAtual));
  return { anos, anoAnterior: idx > 0 ? anos[idx - 1] : null };
}

/* ── Nav ── */
const NAV_ITEMS = [
  { id: 'index',      href: 'index.html',     label: 'Observatório de Contas',
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

  // ── Cards secundários (placeholder — serão preenchidos na Task 4) ──

  // ── Gráfico situação ──
  $('badge-total-sit').textContent = fmtN(total) + ' achados';
  const sitCount = {};
  achados.forEach(a => { const s = a.situacao || 'nao_consta'; sitCount[s] = (sitCount[s] || 0) + 1; });
  const sitOrder  = ['mantido', 'sanado_total', 'sanado_parcial', 'afastado', 'nao_consta'];
  const sitItems  = sitOrder.filter(s => sitCount[s]).map(s => [SITUACAO_LABEL[s] || s, sitCount[s]]);
  $('chart-situacao').innerHTML = buildBarList(sitItems, total, l => {
    const k = Object.entries(SITUACAO_LABEL).find(([, v]) => v === l)?.[0];
    return SITUACAO_COLOR[k] || 'gray';
  });

  // ── Gráfico tipo ──
  const tipoCount = {};
  achados.forEach(a => { if (a.tipo) tipoCount[a.tipo] = (tipoCount[a.tipo] || 0) + 1; });
  const tipoItems = Object.entries(tipoCount).sort((a, b) => b[1] - a[1]);
  const tipoMax = tipoItems[0]?.[1] || 1;
  $('chart-tipo').innerHTML = buildBarList(tipoItems, tipoMax, () => 'blue');

  // ── Gráfico top municípios ──
  const muniCount = {};
  achados.forEach(a => { muniCount[a.municipio] = (muniCount[a.municipio] || 0) + 1; });
  const muniItems = Object.entries(muniCount).sort((a, b) => b[1] - a[1]).slice(0, 8);
  const munis    = [...new Set(achados.map(a => a.municipio))];
  $('badge-total-muni').textContent = fmtN(munis.length) + ' municípios';
  $('chart-municipios').innerHTML = muniItems.length
    ? `<div class="rank-list">${muniItems.map(([nome, cnt], i) => `
        <div class="rank-row" onclick="location.href='achados.html?municipio=${encodeURIComponent(nome)}'">
          <span class="rank-num">${i + 1}</span>
          <span class="rank-name">${escHtml(nome)}</span>
          <span class="rank-count">${fmtN(cnt)}</span>
        </div>`).join('')}</div>`
    : '<div class="empty-state"><p>Sem dados para o filtro selecionado</p></div>';

  // ── Opinião (placeholder — pizza na Task 6) ──
  const opinCount = {};
  achados.forEach(a => {
    const rel = DATA.relatorios.find(r => r.id === a.relatorio_id);
    if (rel?.opiniao_auditoria) opinCount[rel.opiniao_auditoria] = (opinCount[rel.opiniao_auditoria] || 0) + 1;
  });
  const opinItems = Object.entries(opinCount).sort((a, b) => b[1] - a[1]);
  const opinMax = opinItems[0]?.[1] || 1;
  const opinColor = l => l === 'Irregular' ? 'red' : l === 'Regular' ? 'green' : 'orange';
  const opinionPizzaEl = $('chart-opiniao-pizza');
  if (opinionPizzaEl) opinionPizzaEl.innerHTML = buildBarList(opinItems, opinMax, opinColor);
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
    const uid = `acc-${start + i}`;
    return `
    <tr class="accordion-row" data-uid="${uid}" onclick="toggleAccordion('${uid}')">
      <td>${escHtml(a.municipio)}</td>
      <td>${a.ano}</td>
      <td class="mono">${escHtml(a.codigo)}</td>
      <td>${escHtml(a.tipo)}</td>
      <td><span class="badge ${SITUACAO_BADGE[a.situacao] || 'badge-gray'}">${SITUACAO_LABEL[a.situacao] || a.situacao}</span></td>
      <td style="width:32px"><span class="accordion-toggle">▶</span></td>
    </tr>
    <tr class="accordion-detail" id="${uid}">
      <td colspan="6">
        <div class="accordion-content">
          <strong>Descrição:</strong> ${escHtml(a.descricao)}<br><br>
          ${a.recomendacao ? `<strong>Recomendação:</strong> ${escHtml(a.recomendacao)}<br><br>` : ''}
          ${a.determinacao ? `<strong>Determinação:</strong> ${escHtml(a.determinacao)}<br><br>` : ''}
          ${a.base_normativa ? `<strong>Base normativa:</strong> ${escHtml(a.base_normativa)}<br><br>` : ''}
          <strong>Seção:</strong> ${escHtml(a.secao)}
          &nbsp;·&nbsp; <strong>Processo:</strong> <span class="mono">${escHtml(a.numero_processo)}</span>
          &nbsp;·&nbsp; <strong>Defesa:</strong> ${a.houve_defesa ? 'Sim' : 'Não'}
        </div>
      </td>
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

function toggleAccordion(uid) {
  const detail = $(uid);
  const row = document.querySelector(`[data-uid="${uid}"]`);
  const isOpen = detail.classList.contains('open');
  document.querySelectorAll('.accordion-detail.open').forEach(el => {
    el.classList.remove('open');
    document.querySelector(`[data-uid="${el.id}"]`)?.classList.remove('open');
  });
  if (!isOpen) { detail.classList.add('open'); row?.classList.add('open'); }
}

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
  const pctSaneado  = Math.round(((sitAg.sanado_total || 0) + (sitAg.sanado_parcial || 0)) / t.achados * 100);
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
      texto: `${fmtN((sitAg.sanado_total || 0) + (sitAg.sanado_parcial || 0))} achados foram total ou parcialmente corrigidos, demonstrando que o processo de contraditório produz resultados relevantes em parcela dos casos.` },
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
