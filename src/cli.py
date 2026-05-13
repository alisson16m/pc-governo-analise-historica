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

_console = Console(legacy_windows=False)
print = _console.print

from . import cache, enrich, extract_text, parse_2024
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
                _processar(caminho, ano_pasta, forcar=forcar)
                prog.update(t, description=f"[green]OK {caminho.name}")
            except Exception as e:
                prog.update(t, description=f"[red]ERRO {caminho.name}: {e}")


def _processar(caminho: Path, ano_pasta: Optional[int], *, forcar: bool) -> None:
    sha = extract_text.sha256_arquivo(caminho)
    if not forcar:
        if cache.carregar(sha) is not None:
            return
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

    rel = Relatorio(
        id=sha,
        arquivo=str(caminho),
        ano_exercicio=int(meta.get("ano_exercicio") or 0),
        municipio=meta.get("municipio"),
        orgao=meta.get("orgao") or "Não identificado",
        gestor=meta.get("gestor"),
        auditor=meta.get("auditor"),
        relator=meta.get("relator"),
        fonte_extracao=fonte,
        achados=achados or [],
    )
    cache.salvar(rel)


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
    """Commit + push para o GitHub Pages."""
    import subprocess
    subprocess.run(["git", "add", "data/final.json", "site/data.json", "site/"], check=True)
    subprocess.run(["git", "commit", "-m", "atualiza banco de achados"], check=False)
    subprocess.run(["git", "push"], check=False)


if __name__ == "__main__":
    app()
