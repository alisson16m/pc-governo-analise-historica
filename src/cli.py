"""CLI do pipeline (Typer)."""
from __future__ import annotations

import sys

# Garante UTF-8 no stdout/stderr no Windows (Python 3.7+)
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        try:
            _stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn
import logging
import logging.handlers

_console = Console(legacy_windows=False)
print = _console.print


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

from . import cache, enrich, extract_text, parse_2024, parse_contraditorio
from .schema import Relatorio

app = typer.Typer(add_completion=False, help="Pipeline de extração e publicação do Banco de Achados.")

PDFS_DIR = Path("PDFs")


def _coletar_pdfs(ano: Optional[int]) -> list[tuple[Path, Optional[int]]]:
    out: list[tuple[Path, Optional[int]]] = []
    if ano:
        for p in (PDFS_DIR / str(ano)).glob("*.pdf"):
            out.append((p, ano))
        return out
    if not PDFS_DIR.exists():
        return out
    for sub in sorted(PDFS_DIR.iterdir()):
        if sub.is_dir() and sub.name.isdigit():
            for p in sub.glob("*.pdf"):
                out.append((p, int(sub.name)))
    return out


@app.command()
def extrair(
    ano: Optional[int] = typer.Option(None, help="Ex: 2024"),
    limite: Optional[int] = typer.Option(None, help="Processa apenas N PDFs"),
    forcar: bool = typer.Option(False, "--forcar", help="Ignora cache"),
    pdf: Optional[Path] = typer.Option(None, help="Processa um PDF específico"),
) -> None:
    """Extrai achados dos PDFs em PDFs/AAAA/."""
    _configurar_logging()
    _log = logging.getLogger("pcg.extrair")
    if pdf:
        alvos = [(pdf, None)]
    else:
        alvos = _coletar_pdfs(ano)
    if limite:
        alvos = alvos[:limite]
    if not alvos:
        print("[yellow]Nenhum PDF encontrado.[/]")
        raise typer.Exit(0)

    with Progress(SpinnerColumn(spinner_name="line"), TextColumn("{task.description}"), console=_console) as prog:
        for caminho, ano_pasta in alvos:
            t = prog.add_task(f"[cyan]{caminho.name}", total=None)
            try:
                fonte = _processar(caminho, ano_pasta, forcar=forcar)
                if fonte == "gemini_legacy":
                    from .rate_limit import estado_atual
                    est = estado_atual()
                    prog.update(t, description=f"[green]OK {caminho.name} [dim]({est['rpd_usado']}/{est['rpd_max']} req Gemini)[/]")
                else:
                    prog.update(t, description=f"[green]OK {caminho.name}")
                _log.info("OK %s — fonte=%s", caminho.name, fonte)
            except Exception as e:
                prog.update(t, description=f"[red]ERRO {caminho.name}: {e}")
                _log.error("ERRO %s — %s", caminho.name, e)


def _processar(caminho: Path, ano_pasta: Optional[int], *, forcar: bool) -> str:
    sha = extract_text.sha256_arquivo(caminho)
    if not forcar:
        if cache.carregar(sha) is not None:
            return "cache"
    texto = extract_text.extrair(caminho)
    meta = enrich.metadados(texto, ano_pasta)

    achados = parse_2024.parse(texto)
    fonte = "parser_2024"
    if achados is None:
        try:
            from . import parse_legacy  # type: ignore
            achados = parse_legacy.parse(texto)
            fonte = "gemini_legacy"
        except Exception:
            achados = []
            fonte = "pendente_legacy"

    contraditorio = parse_contraditorio.extrair(texto)
    achados_final = _aplicar_contraditorio(achados or [], contraditorio)

    rel = Relatorio(
        id=sha,
        arquivo=str(caminho),
        ano_exercicio=int(meta.get("ano_exercicio") or 0),
        municipio=meta.get("municipio"),
        gestor=meta.get("gestor"),
        auditor=meta.get("auditor"),
        relator=meta.get("relator"),
        opiniao_auditoria=enrich.detectar_opiniao_auditoria(texto),
        fonte_extracao=fonte,
        achados=achados_final,
    )
    # Não persiste pendente_legacy: garante que o próximo `extrair` (sem --forcar)
    # ainda tente processar o PDF quando a cota Gemini estiver disponível.
    if fonte != "pendente_legacy":
        cache.salvar(rel)
    return fonte


def _aplicar_contraditorio(achados: list, contraditorio: dict) -> list:
    if not contraditorio:
        return achados
    # Caso 1: gestor não apresentou defesa para nenhum achado
    if contraditorio.get("_sem_defesa_global"):
        for a in achados:
            a.houve_defesa = False
        return achados
    # Casos 2 e 3: por achado
    for a in achados:
        bloco = contraditorio.get(a.codigo)
        if bloco:
            a.defesa_gestor = bloco.get("defesa_gestor")
            a.analise_tecnica = bloco.get("analise_tecnica")
            if bloco.get("houve_defesa") is False:
                a.houve_defesa = False
            elif a.defesa_gestor:
                a.houve_defesa = True
            try:
                if a.defesa_gestor and a.resumo_defesa is None:
                    a.resumo_defesa = parse_contraditorio.resumir_texto(
                        a.defesa_gestor, "defesa do gestor"
                    )
                if a.analise_tecnica and a.resumo_analise is None:
                    a.resumo_analise = parse_contraditorio.resumir_texto(
                        a.analise_tecnica, "análise técnica do auditor"
                    )
            except RuntimeError as _e:
                if "cota" in str(_e).lower() or "quota" in str(_e).lower():
                    pass  # cota Gemini esgotada; resumos via backfill-resumo
                else:
                    raise
    return achados


@app.command()
def backfill_contraditorio() -> None:
    """Preenche defesa_gestor e analise_tecnica nos achados já em cache (sem re-executar Gemini)."""
    rels = cache.listar()
    atualizados = sem_pdf = sem_cap = 0
    for r in rels:
        pdf = Path(r.arquivo)
        if not pdf.exists():
            sem_pdf += 1
            continue
        try:
            texto = extract_text.extrair(pdf)
            contraditorio = parse_contraditorio.extrair(texto)
            if not contraditorio:
                sem_cap += 1
                print(f"[yellow]{pdf.name}[/] — capítulo Contraditório não encontrado")
                continue
            _aplicar_contraditorio(r.achados, contraditorio)
            cache.salvar(r)
            atualizados += 1
            com_defesa = sum(1 for a in r.achados if a.defesa_gestor)
            sem_defesa = sum(1 for a in r.achados if a.houve_defesa is False)
            extra = f", {sem_defesa} sem defesa" if sem_defesa else ""
            print(f"[green]{pdf.name}[/] — {com_defesa}/{len(r.achados)} com defesa{extra}")
        except Exception as e:
            print(f"[red]{pdf.name}: {e}")
    print(
        f"\n[bold]{atualizados} relatório(s) atualizado(s)[/]"
        + (f" ({sem_pdf} PDF(s) não encontrado(s))" if sem_pdf else "")
        + (f" ({sem_cap} sem capítulo Contraditório)" if sem_cap else "")
    )


@app.command()
def backfill_opiniao() -> None:
    """Preenche opiniao_auditoria nos relatórios já em cache (sem re-executar Gemini)."""
    rels = cache.listar()
    atualizados = 0
    sem_pdf = 0
    for r in rels:
        if r.opiniao_auditoria is not None:
            continue
        pdf = Path(r.arquivo)
        if not pdf.exists():
            sem_pdf += 1
            continue
        try:
            texto = extract_text.extrair(pdf)
            opiniao = enrich.detectar_opiniao_auditoria(texto)
            if opiniao:
                r.opiniao_auditoria = opiniao
                cache.salvar(r)
                atualizados += 1
                print(f"[green]{pdf.name}[/] → {opiniao}")
            else:
                print(f"[yellow]{pdf.name}[/] — opinião não encontrada")
        except Exception as e:
            print(f"[red]{pdf.name}: {e}")
    print(f"\n[bold]{atualizados} relatórios atualizados[/]" + (f" ({sem_pdf} PDF(s) não encontrado(s))" if sem_pdf else ""))


@app.command()
def backfill_resumo() -> None:
    """Gera resumo_defesa e resumo_analise para achados em cache que ainda não têm resumo."""
    rels = cache.listar()
    atualizados = processados = 0
    for r in rels:
        modificado = False
        for a in r.achados:
            if a.defesa_gestor and a.resumo_defesa is None:
                resumo = parse_contraditorio.resumir_texto(a.defesa_gestor, "defesa do gestor")
                if resumo:
                    a.resumo_defesa = resumo
                    modificado = True
                    processados += 1
            if a.analise_tecnica and a.resumo_analise is None:
                resumo = parse_contraditorio.resumir_texto(a.analise_tecnica, "análise técnica do auditor")
                if resumo:
                    a.resumo_analise = resumo
                    modificado = True
                    processados += 1
        if modificado:
            cache.salvar(r)
            atualizados += 1
            print(f"[green]{Path(r.arquivo).name}[/]")
    print(f"\n[bold]{atualizados} relatório(s) atualizado(s) ({processados} resumos gerados)[/]")


@app.command()
def listar() -> None:
    """Lista relatórios já extraídos."""
    rels = cache.listar()
    if not rels:
        print("[yellow]Nenhum relatório no cache.[/]")
        return
    for r in rels:
        print(f"[bold]{r.arquivo}[/] — {r.municipio or '?'} {r.ano_exercicio} — {len(r.achados)} achados ({r.fonte_extracao})")


@app.command()
def revisar(
    gerar: bool = typer.Option(False, "--gerar", help="Gera CSV de revisão"),
    aplicar: bool = typer.Option(False, "--aplicar", help="Aplica edições do CSV"),
) -> None:
    """Loop de revisão humana via CSV."""
    from . import review
    if gerar:
        path = review.gerar_csv()
        print(f"[green]CSV gerado em {path}")
    elif aplicar:
        n = review.aplicar_csv()
        print(f"[green]{n} achados atualizados a partir do CSV")
    else:
        print("Use --gerar ou --aplicar")


@app.command()
def build() -> None:
    """Constrói site/data.json a partir do cache (linhas revisadas)."""
    from . import build_site
    saida = build_site.build()
    print(f"[green]Portal atualizado: {saida}")


@app.command()
def publicar() -> None:
    """Commit + push para o GitHub Pages (branch gh-pages)."""
    import subprocess
    subprocess.run(["git", "add", "site/data.json", "site/"], check=True)
    subprocess.run(["git", "commit", "-m", "atualiza banco de achados"], check=False)
    subprocess.run(["git", "push"], check=False)
    # Publica site/ no branch gh-pages (servido pelo GitHub Pages)
    result = subprocess.run(
        ["git", "subtree", "split", "--prefix", "site", "HEAD"],
        capture_output=True, text=True, check=True,
    )
    sha = result.stdout.strip()
    subprocess.run(["git", "push", "origin", f"{sha}:refs/heads/gh-pages", "--force"], check=True)
    print("[green]Publicado em https://alisson16m.github.io/pc-governo-analise-historica/")


@app.command()
def diagnosticar() -> None:
    """Exibe painel de diagnóstico do estado atual do pipeline."""
    import csv as _csv
    from rich.panel import Panel

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

    from . import review as _review
    csv_path = _review.CSV_PATH
    total_csv = revisados = 0
    if csv_path.exists():
        with csv_path.open(encoding="utf-8-sig", newline="") as f:
            for row in _csv.DictReader(f):
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


if __name__ == "__main__":
    app()
