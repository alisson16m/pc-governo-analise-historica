"""Revisão humana via CSV.

Fluxo:
- gerar_csv() lê data/extracted/*.json e escreve data/review.csv preservando
  edições anteriores (chave = relatorio_id + codigo).
- aplicar_csv() relê o CSV (após edição manual), aplica as mudanças nos JSONs
  do cache e marca o achado como revisado.
"""
from __future__ import annotations

import csv
from decimal import Decimal
from pathlib import Path
from typing import Optional

from . import cache
from .schema import Achado, Situacao

CSV_PATH = Path("data/review.csv")

CAMPOS = [
    "relatorio_id",
    "arquivo",
    "ano",
    "municipio",
    "codigo",
    "tipo",
    "secao",
    "base_normativa",
    "descricao",
    "houve_defesa",
    "situacao",
    "recomendacao",
    "determinacao",
    "valor_financeiro",
    "fonte_extracao",
    "revisado",
]


def gerar_csv() -> Path:
    rels = cache.listar()
    existentes = _ler_existente()
    CSV_PATH.parent.mkdir(parents=True, exist_ok=True)
    with CSV_PATH.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=CAMPOS)
        w.writeheader()
        for r in rels:
            for a in r.achados:
                chave = (r.id, a.codigo)
                base = {
                    "relatorio_id": r.id,
                    "arquivo": r.arquivo,
                    "ano": r.ano_exercicio,
                    "municipio": r.municipio or "",
                    "codigo": a.codigo,
                    "tipo": a.tipo,
                    "secao": a.secao,
                    "base_normativa": a.base_normativa or "",
                    "descricao": a.descricao,
                    "houve_defesa": "true" if a.houve_defesa else "false",
                    "situacao": a.situacao.value if a.situacao else "",
                    "recomendacao": a.recomendacao or "",
                    "determinacao": a.determinacao or "",
                    "valor_financeiro": str(a.valor_financeiro) if a.valor_financeiro is not None else "",
                    "fonte_extracao": r.fonte_extracao,
                    "revisado": "false",
                }
                if chave in existentes:
                    ant = existentes[chave]
                    # Só preserva edições explícitas (revisado=true); linhas não
                    # revisadas são descartadas para que o cache atualizado prevaleça.
                    if ant.get("revisado", "").strip().lower() == "true":
                        base.update({k: v for k, v in ant.items() if v not in ("", None)})
                w.writerow(base)
    return CSV_PATH


def _ler_existente() -> dict[tuple[str, str], dict]:
    if not CSV_PATH.exists():
        return {}
    out: dict[tuple[str, str], dict] = {}
    with CSV_PATH.open("r", encoding="utf-8-sig", newline="") as f:
        r = csv.DictReader(f)
        for linha in r:
            out[(linha["relatorio_id"], linha["codigo"])] = linha
    return out


def aplicar_csv() -> int:
    if not CSV_PATH.exists():
        raise FileNotFoundError(f"{CSV_PATH} não encontrado. Rode --gerar primeiro.")
    por_rel: dict[str, dict[str, dict]] = {}
    with CSV_PATH.open("r", encoding="utf-8-sig", newline="") as f:
        r = csv.DictReader(f)
        for linha in r:
            por_rel.setdefault(linha["relatorio_id"], {})[linha["codigo"]] = linha

    aplicados = 0
    for rid, mapa in por_rel.items():
        rel = cache.carregar(rid)
        if not rel:
            continue
        novos: list[Achado] = []
        for a in rel.achados:
            edicao = mapa.get(a.codigo)
            if edicao and edicao.get("revisado", "").strip().lower() == "true":
                novos.append(_mesclar(a, edicao))
                aplicados += 1
            else:
                novos.append(a)
        rel.achados = novos
        cache.salvar(rel)
    return aplicados


def _mesclar(a: Achado, e: dict) -> Achado:
    def _v(k: str) -> Optional[str]:
        v = e.get(k, "")
        return v.strip() if isinstance(v, str) and v.strip() else None

    sit_raw = _v("situacao")
    situacao: Optional[Situacao]
    if sit_raw:
        try:
            situacao = Situacao(sit_raw)
        except ValueError:
            situacao = a.situacao
    else:
        situacao = a.situacao

    valor = e.get("valor_financeiro", "").strip()
    valor_dec = a.valor_financeiro
    if valor:
        try:
            valor_dec = Decimal(valor.replace(",", "."))
        except Exception:
            pass

    # model_copy preserva os campos que não existem no CSV
    # (defesa_gestor, analise_tecnica, resumo_defesa, resumo_analise)
    update: dict = {
        "tipo": _v("tipo") or a.tipo,
        "secao": _v("secao") or a.secao,
        "base_normativa": _v("base_normativa") or a.base_normativa,
        "descricao": _v("descricao") or a.descricao,
        "situacao": situacao,
        "recomendacao": _v("recomendacao") or a.recomendacao,
        "determinacao": _v("determinacao") or a.determinacao,
        "valor_financeiro": valor_dec,
    }
    hd_raw = (e.get("houve_defesa") or "").strip().lower()
    if hd_raw in ("true", "false"):
        update["houve_defesa"] = hd_raw == "true"
    return a.model_copy(update=update)
