"""Lê as planilhas PC_Gov_AAAA.xlsx e monta lookup (municipio, ano) → {numero_processo, conselheiro}."""
from __future__ import annotations

import shutil
import tempfile
import unicodedata
from pathlib import Path
from typing import Optional

import pandas as pd

PLANILHAS: dict[int, str] = {
    2023: "PC_Gov_2023.xlsx",
    2024: "PC_Gov_2024.xlsx",
    2025: "PC_Gov_2025.xlsx",
}


def _norm(s: object) -> str:
    if not isinstance(s, str):
        return ""
    s = unicodedata.normalize("NFD", s)
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    return s.strip().lower()


def _col(df: pd.DataFrame, fragmento: str, excluir: tuple[str, ...] = ()) -> Optional[str]:
    for c in df.columns:
        nc = _norm(c)
        if fragmento in nc and not any(e in nc for e in excluir):
            return c
    return None


def carregar_lookup() -> dict[tuple[str, int], dict]:
    """Retorna {(municipio_norm, ano): {numero_processo, conselheiro}}."""
    lookup: dict[tuple[str, int], dict] = {}

    for ano, arquivo in PLANILHAS.items():
        path = Path(arquivo)
        if not path.exists():
            continue

        # OneDrive pode manter lock de escrita; copia para tmp antes de ler
        with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as tmp:
            tmp_path = Path(tmp.name)
        shutil.copy2(path, tmp_path)

        try:
            df = pd.read_excel(tmp_path, engine="openpyxl")
        except Exception:
            continue
        finally:
            tmp_path.unlink(missing_ok=True)

        df.columns = [str(c).strip() for c in df.columns]

        col_proc = _col(df, "processo", excluir=("ext", "tipo"))
        col_mun = _col(df, "administrativa")
        col_cons = _col(df, "conselheiro")
        col_ano = _col(df, "exerc")

        if not all([col_proc, col_mun, col_cons]):
            continue

        for _, row in df.iterrows():
            municipio = row.get(col_mun) if col_mun else None
            conselheiro = row.get(col_cons) if col_cons else None
            processo = row.get(col_proc) if col_proc else None
            ano_linha = int(row[col_ano]) if col_ano and pd.notna(row.get(col_ano)) else ano

            if not isinstance(municipio, str) or not municipio.strip():
                continue
            if not isinstance(processo, str) or not processo.strip():
                continue

            chave = (_norm(municipio), ano_linha)
            lookup[chave] = {
                "numero_processo": processo.strip(),
                "conselheiro": conselheiro.strip().title() if isinstance(conselheiro, str) else None,
            }

    return lookup


def enriquecer(municipio: Optional[str], ano: int, lookup: dict[tuple[str, int], dict]) -> dict:
    """Retorna {numero_processo, conselheiro} para o par (municipio, ano), ou {} se não encontrado."""
    if not municipio:
        return {}
    return lookup.get((_norm(municipio), ano), {})
