/* Núcleo compartilhado entre páginas. */
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
  document.querySelectorAll("nav.menu a").forEach(a => {
    if (a.getAttribute("href") === path) a.classList.add("active");
  });
}

function montarChartBarras(canvas, labels, valores, titulo, cor = "#2c6cc4", horizontal = false) {
  return new Chart(canvas, {
    type: "bar",
    data: {
      labels,
      datasets: [{
        label: titulo,
        data: valores,
        backgroundColor: cor,
      }],
    },
    options: {
      indexAxis: horizontal ? "y" : "x",
      responsive: true,
      maintainAspectRatio: false,
      plugins: { legend: { display: false } },
      scales: { x: { ticks: { autoSkip: false, maxRotation: 30, minRotation: 0 } } },
    },
  });
}

function montarChartPizza(canvas, mapa) {
  const labels = Object.keys(mapa).map(k => SITUACAO_LABEL[k] || k);
  const valores = Object.values(mapa);
  const cores = Object.keys(mapa).map(k => SITUACAO_CORES[k] || "#888");
  return new Chart(canvas, {
    type: "doughnut",
    data: { labels, datasets: [{ data: valores, backgroundColor: cores }] },
    options: { responsive: true, maintainAspectRatio: false },
  });
}

function abrirModal(achado, relatorio) {
  const m = document.getElementById("modal-bg");
  document.getElementById("modal-titulo").textContent = `${achado.codigo} — ${achado.tipo}`;
  document.getElementById("modal-conteudo").innerHTML = `
    <dl>
      <dt>Situação</dt><dd>${badgeSituacao(achado.situacao)}</dd>
      <dt>Município</dt><dd>${achado.municipio || "—"}</dd>
      <dt>Ano</dt><dd>${achado.ano || "—"}</dd>
      <dt>Seção</dt><dd>${achado.secao || "—"}</dd>
      <dt>Houve defesa?</dt><dd>${achado.houve_defesa ? "Sim" : "Não"}</dd>
      <dt>Base normativa</dt><dd>${achado.base_normativa || "—"}</dd>
      <dt>Valor envolvido</dt><dd>${fmtMoeda(achado.valor_financeiro)}</dd>
      <dt>Auditor</dt><dd>${achado.auditor || "—"}</dd>
    </dl>
    <h4>Descrição</h4>
    <p>${achado.descricao || "—"}</p>
    ${achado.recomendacao ? `<h4>Recomendação</h4><p>${achado.recomendacao}</p>` : ""}
    ${achado.determinacao ? `<h4>Determinação</h4><p>${achado.determinacao}</p>` : ""}
  `;
  m.classList.add("show");
}
function fecharModal() {
  document.getElementById("modal-bg")?.classList.remove("show");
}

document.addEventListener("DOMContentLoaded", () => {
  marcarMenuAtivo();
  document.getElementById("modal-bg")?.addEventListener("click", e => {
    if (e.target.id === "modal-bg") fecharModal();
  });
  document.getElementById("modal-close")?.addEventListener("click", fecharModal);
});
