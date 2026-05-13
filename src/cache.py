"""Cache de extrações por SHA-256 para não reprocessar PDFs."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

from .schema import Relatorio

CACHE_DIR = Path("data/extracted")


def caminho(sha: str) -> Path:
    return CACHE_DIR / f"{sha}.json"


def carregar(sha: str) -> Optional[Relatorio]:
    p = caminho(sha)
    if not p.exists():
        return None
    try:
        return Relatorio.model_validate_json(p.read_text(encoding="utf-8"))
    except Exception:
        return None


def salvar(rel: Relatorio) -> Path:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    p = caminho(rel.id)
    p.write_text(rel.model_dump_json(indent=2), encoding="utf-8")
    return p


def listar() -> list[Relatorio]:
    if not CACHE_DIR.exists():
        return []
    out: list[Relatorio] = []
    for p in sorted(CACHE_DIR.glob("*.json")):
        try:
            out.append(Relatorio.model_validate_json(p.read_text(encoding="utf-8")))
        except Exception:
            continue
    return out
