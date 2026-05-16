"""Cache de extrações por SHA-256 para não reprocessar PDFs."""
from __future__ import annotations

import json
import warnings
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
    except Exception as e:
        warnings.warn(f"Cache corrompido ignorado: {p.name} — {e}")
        return None


def salvar(rel: Relatorio) -> Path:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    p = caminho(rel.id)
    tmp = p.with_suffix(".tmp")
    json_str = rel.model_dump_json(indent=2)
    try:
        json.loads(json_str)
    except json.JSONDecodeError as e:
        raise ValueError(f"JSON inválido gerado para {p.name}: {e}") from e
    tmp.write_text(json_str, encoding="utf-8")
    tmp.replace(p)
    return p


def listar() -> list[Relatorio]:
    if not CACHE_DIR.exists():
        return []
    out: list[Relatorio] = []
    for p in sorted(CACHE_DIR.glob("*.json")):
        try:
            out.append(Relatorio.model_validate_json(p.read_text(encoding="utf-8")))
        except Exception as e:
            warnings.warn(f"Cache corrompido ignorado: {p.name} — {e}")
            continue
    return out
