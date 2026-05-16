"""PDF -> texto + tabelas + cabeçalhos."""
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import pdfplumber
from rich.console import Console as _Console

_console = _Console(legacy_windows=False)


@dataclass
class Pagina:
    numero: int
    texto: str
    tabelas: list[list[list[str]]] = field(default_factory=list)


@dataclass
class RelatorioTexto:
    arquivo: Path
    sha256: str
    paginas: list[Pagina]
    texto_completo: str

    def linhas(self) -> list[tuple[int, str]]:
        out: list[tuple[int, str]] = []
        for p in self.paginas:
            for ln in p.texto.splitlines():
                out.append((p.numero, ln))
        return out


def sha256_arquivo(caminho: Path) -> str:
    h = hashlib.sha256()
    with caminho.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def extrair(caminho: Path) -> RelatorioTexto:
    paginas: list[Pagina] = []
    partes: list[str] = []
    with pdfplumber.open(caminho) as pdf:
        for i, page in enumerate(pdf.pages, start=1):
            texto = page.extract_text() or ""
            try:
                tabelas = page.extract_tables() or []
            except Exception as _exc:
                _console.print(
                    f"[yellow]⚠ Tabela ignorada: {caminho.name} p.{i} — {_exc}[/yellow]"
                )
                tabelas = []
            paginas.append(Pagina(numero=i, texto=texto, tabelas=tabelas))
            partes.append(texto)
    return RelatorioTexto(
        arquivo=caminho,
        sha256=sha256_arquivo(caminho),
        paginas=paginas,
        texto_completo="\n".join(partes),
    )


# Heurística simples de cabeçalho de seção: linhas curtas em maiúsculas,
# possivelmente numeradas (ex: "2.3 GESTÃO FISCAL", "III. DOS ACHADOS").
_RE_CABECALHO = re.compile(
    r"^\s*(?:[IVX]+\.|\d+(?:\.\d+)*\.?)\s+[A-ZÁÉÍÓÚÂÊÔÃÕÇ][A-ZÁÉÍÓÚÂÊÔÃÕÇ \-/–&]{3,}$"
)


def extrair_secoes(texto_relatorio: RelatorioTexto) -> list[tuple[int, str]]:
    """Retorna lista (numero_linha_global, titulo_secao). Linha global = índice em linhas()."""
    secs: list[tuple[int, str]] = []
    for idx, (_pag, ln) in enumerate(texto_relatorio.linhas()):
        if _RE_CABECALHO.match(ln):
            secs.append((idx, ln.strip()))
    return secs


def achar_indice_codigo(texto: RelatorioTexto, codigo: str) -> Optional[int]:
    """Retorna o índice global (em linhas()) da primeira linha que contém o código."""
    for i, (_p, ln) in enumerate(texto.linhas()):
        if codigo in ln:
            return i
    return None


def secao_de_linha(secoes: list[tuple[int, str]], idx_linha: int) -> str:
    atual = ""
    for idx, titulo in secoes:
        if idx <= idx_linha:
            atual = titulo
        else:
            break
    return atual
