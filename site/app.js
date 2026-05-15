/* Núcleo compartilhado entre páginas. */

if (typeof Chart !== 'undefined' && typeof ChartDataLabels !== 'undefined') {
  Chart.register(ChartDataLabels);
}

const SITUACAO_LABEL = {
  sanado_total: "Sanado totalmente",
  sanado_parcial: "Sanado parcialmente",
  afastado: "Afastado",
  mantido: "Mantido",
  nao_consta: "Não consta",
};
const SITUACAO_CORES = {
  sanado_total: "#2e8b57",
  sanado_parcial: "#d18b1d",
  afastado: "#2c6cc4",
  mantido: "#b94a48",
  nao_consta: "#a0a8b8",
};

let DATA = null;

async function carregarDados() {
  if (DATA) return DATA;
  const r = await fetch("data.json", { cache: "no-cache" });
  if (!r.ok) throw new Error("Falha ao carregar data.json");
  DATA = await r.json();
  const vEl = document.getElementById("sidebar-version");
  if (vEl && DATA.versao) vEl.textContent = "v" + DATA.versao;
  return DATA;
}

function fmtNum(n) {
  return new Intl.NumberFormat("pt-BR").format(n || 0);
}
function fmtMoeda(n) {
  if (n == null) return "—";
  return new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" }).format(n);
}
function pct(n, total) {
  if (!total) return "0%";
  return ((n / total) * 100).toFixed(1) + "%";
}
function badgeSituacao(s) {
  if (!s) s = "nao_consta";
  return `<span class="badge ${s}">${SITUACAO_LABEL[s] || s}</span>`;
}

function marcarMenuAtivo() {
  const path = location.pathname.split("/").pop() || "index.html";
  document.querySelectorAll(".nav-link").forEach(a => {
    if (a.getAttribute("href") === path) a.classList.add("active");
  });
}

function montarChartBarras(canvas, labels, valores, titulo, cor, horizontal) {
  if (cor === undefined) cor = "#1C588C";
  if (horizontal === undefined) horizontal = false;

  const isHorizontal = horizontal;

  return new Chart(canvas, {
    type: "bar",
    data: {
      labels,
      datasets: [{
        label: titulo,
        data: valores,
        backgroundColor: cor,
        borderRadius: 4,
        borderSkipped: false,
      }],
    },
    options: {
      indexAxis: isHorizontal ? "y" : "x",
      responsive: true,
      maintainAspectRatio: false,
      layout: {
        padding: isHorizontal ? { right: 48 } : { top: 20 },
      },
      plugins: {
        legend: { display: false },
        datalabels: {
          color: "#1a2233",
          font: { size: 11, weight: "600" },
          anchor: isHorizontal ? "end" : "end",
          align: isHorizontal ? "end" : "end",
          formatter: (v) => fmtNum(v),
          clip: false,
        },
      },
      scales: {
        x: {
          ticks: {
            autoSkip: !isHorizontal,
            maxRotation: isHorizontal ? 0 : 30,
            minRotation: 0,
            font: { size: 11 },
          },
          grid: { color: "rgba(0,0,0,0.05)" },
        },
        y: {
          ticks: { font: { size: 11 } },
          grid: { color: "rgba(0,0,0,0.05)" },
        },
      },
    },
  });
}

function montarChartPizza(canvas, mapa) {
  const entries = Object.entries(mapa).sort((a, b) => b[1] - a[1]);
  const labels = entries.map(([k]) => SITUACAO_LABEL[k] || k);
  const valores = entries.map(([, v]) => v);
  const cores = entries.map(([k]) => SITUACAO_CORES[k] || "#888");
  const total = valores.reduce((a, b) => a + b, 0);

  return new Chart(canvas, {
    type: "doughnut",
    data: { labels, datasets: [{ data: valores, backgroundColor: cores, borderWidth: 2 }] },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: {
          display: true,
          position: "right",
          labels: { font: { size: 11 }, boxWidth: 12, padding: 10 },
        },
        datalabels: {
          color: "#fff",
          font: { size: 11, weight: "700" },
          formatter: (v) => {
            if (!total) return "";
            const p = (v / total * 100).toFixed(1);
            return p < 5 ? "" : p + "%";
          },
        },
      },
    },
  });
}

function abrirModal(achado, relatorio) {
  const m = document.getElementById("modal-bg");
  if (!m) return;
  document.getElementById("modal-titulo").textContent = `${achado.codigo} — ${achado.tipo}`;
  document.getElementById("modal-conteudo").innerHTML = `
    <dl>
      <dt>Situação</dt><dd>${badgeSituacao(achado.situacao)}</dd>
      <dt>Município</dt><dd>${achado.municipio || "—"}</dd>
      <dt>Ano</dt><dd>${achado.ano || "—"}</dd>
      <dt>Seção</dt><dd>${achado.secao || "—"}</dd>
      ${!achado.houve_defesa ? "<dt>Houve defesa?</dt><dd>Não</dd>" : ""}
      <dt>Nº do processo</dt><dd>${achado.numero_processo || relatorio?.numero_processo || "—"}</dd>
      <dt>Relator</dt><dd>${achado.relator || relatorio?.relator || "—"}</dd>
      <dt>Base normativa</dt><dd>${achado.base_normativa || "—"}</dd>
      <dt>Valor envolvido</dt><dd>${fmtMoeda(achado.valor_financeiro)}</dd>
      <dt>Auditor</dt><dd>${achado.auditor || "—"}</dd>
    </dl>
    <h4>Descrição</h4>
    <p>${achado.descricao || "—"}</p>
    ${achado.recomendacao ? `<h4>Recomendação</h4><p>${achado.recomendacao}</p>` : ""}
    ${achado.determinacao ? `<h4>Determinação</h4><p>${achado.determinacao}</p>` : ""}
    ${achado.resumo_defesa
      ? `<h4>Defesa do Gestor</h4><p>${achado.resumo_defesa}</p>`
      : achado.defesa_gestor
        ? `<h4>Defesa do Gestor</h4><p>${achado.defesa_gestor}</p>`
        : ""}
    ${achado.resumo_analise
      ? `<h4>Análise Técnica</h4><p>${achado.resumo_analise}</p>`
      : achado.analise_tecnica
        ? `<h4>Análise Técnica</h4><p>${achado.analise_tecnica}</p>`
        : ""}
  `;
  m.classList.add("show");
}

function fecharModal() {
  document.getElementById("modal-bg")?.classList.remove("show");
}

/* ── Sidebar hamburguer ── */
function initSidebar() {
  const toggle = document.getElementById("menu-toggle");
  const sidebar = document.getElementById("sidebar");
  const overlay = document.getElementById("sidebar-overlay");
  if (!toggle || !sidebar || !overlay) return;

  toggle.addEventListener("click", () => {
    sidebar.classList.toggle("open");
    overlay.classList.toggle("open");
  });
  overlay.addEventListener("click", () => {
    sidebar.classList.remove("open");
    overlay.classList.remove("open");
  });
}

document.addEventListener("DOMContentLoaded", () => {
  marcarMenuAtivo();
  initSidebar();
  document.getElementById("modal-bg")?.addEventListener("click", e => {
    if (e.target.id === "modal-bg") fecharModal();
  });
  document.getElementById("modal-close")?.addEventListener("click", fecharModal);
});
