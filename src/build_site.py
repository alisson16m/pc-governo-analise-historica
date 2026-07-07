"""Consolida data/extracted/*.json em site/data.json com agregações pré-computadas."""
from __future__ import annotations

import json
import re
from collections import Counter, defaultdict
from decimal import Decimal
from pathlib import Path
from typing import Any


def _ler_versao() -> str:
    try:
        txt = Path("pyproject.toml").read_text(encoding="utf-8")
        m = re.search(r'^version\s*=\s*["\']([^"\']+)["\']', txt, re.MULTILINE)
        return m.group(1) if m else "0.0.0"
    except Exception:
        return "0.0.0"

from . import cache
from .planilha_pc import carregar_lookup, enriquecer
from .schema import Situacao

SITE_DATA = Path("site-v3/data.json")
FINAL_JSON = Path("data/final.json")


def _serializar(o: Any):
    if isinstance(o, Decimal):
        return float(o)
    raise TypeError(f"não serializável: {type(o)}")


def build() -> Path:
    rels = cache.listar()
    if not rels:
        raise RuntimeError("Nenhum relatório no cache. Rode 'extrair' primeiro.")
    achados_flat: list[dict] = []
    relatorios_out: list[dict] = []
    lookup = carregar_lookup()

    for r in rels:
        extra = enriquecer(r.municipio, r.ano_exercicio, lookup)
        numero_processo = extra.get("numero_processo") or r.numero_processo
        relator = extra.get("conselheiro") or r.relator

        relatorios_out.append({
            "id": r.id,
            "arquivo": Path(r.arquivo).name,
            "ano": r.ano_exercicio,
            "municipio": r.municipio,
            "gestor": r.gestor,
            "auditor": r.auditor,
            "relator": relator,
            "numero_processo": numero_processo,
            "opiniao_auditoria": r.opiniao_auditoria,
            "fonte_extracao": r.fonte_extracao,
            "n_achados": len(r.achados),
        })
        for a in r.achados:
            achados_flat.append({
                "relatorio_id": r.id,
                "ano": r.ano_exercicio,
                "municipio": r.municipio,
                "auditor": r.auditor,
                "relator": relator,
                "numero_processo": numero_processo,
                "codigo": a.codigo,
                "tipo": a.tipo,
                "secao": a.secao,
                "base_normativa": a.base_normativa,
                "descricao": a.descricao,
                "houve_defesa": a.houve_defesa,
                "situacao": a.situacao.value if a.situacao else None,
                "recomendacao": a.recomendacao,
                "determinacao": a.determinacao,
                "valor_financeiro": float(a.valor_financeiro) if a.valor_financeiro is not None else None,
                "defesa_gestor": a.resumo_defesa,
                "analise_tecnica": a.resumo_analise,
            })

    agregacoes = _agregar(achados_flat, relatorios_out)
    payload = {
        "gerado_em": _agora_iso(),
        "versao": _ler_versao(),
        "relatorios": relatorios_out,
        "achados": achados_flat,
        "agregacoes": agregacoes,
    }

    SITE_DATA.parent.mkdir(parents=True, exist_ok=True)
    SITE_DATA.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, default=_serializar),
        encoding="utf-8",
    )
    FINAL_JSON.parent.mkdir(parents=True, exist_ok=True)
    FINAL_JSON.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, default=_serializar),
        encoding="utf-8",
    )
    return SITE_DATA


def _agora_iso() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _agregar(achados: list[dict], relatorios: list[dict]) -> dict:
    total = len(achados)
    sit_count: Counter[str] = Counter()
    tipo_count: Counter[str] = Counter()
    secao_count: Counter[str] = Counter()
    municipio_count: Counter[str] = Counter()
    ano_count: Counter[int] = Counter()
    base_count: Counter[str] = Counter()
    auditor_count: Counter[str] = Counter()
    defesa_situ: dict[bool, Counter[str]] = {True: Counter(), False: Counter()}
    valores_top: list[dict] = []

    saneados = 0
    mantidos = 0
    com_defesa = 0
    sit_por_municipio: dict[str, Counter[str]] = defaultdict(Counter)
    tipo_por_secao: dict[str, Counter[str]] = defaultdict(Counter)
    mun_ano_count: dict[int, Counter[str]] = defaultdict(Counter)
    sit_por_mun_ano: dict[int, dict[str, Counter[str]]] = defaultdict(lambda: defaultdict(Counter))

    for a in achados:
        sit = a.get("situacao") or "nao_consta"
        sit_count[sit] += 1
        tipo_count[a["tipo"]] += 1
        secao_count[a["secao"]] += 1
        if a.get("municipio"):
            municipio_count[a["municipio"]] += 1
            sit_por_municipio[a["municipio"]][sit] += 1
        if a.get("ano"):
            ano_count[a["ano"]] += 1
            if a.get("municipio"):
                mun_ano_count[a["ano"]][a["municipio"]] += 1
                sit_por_mun_ano[a["ano"]][a["municipio"]][sit] += 1
        if a.get("base_normativa"):
            base_count[a["base_normativa"][:120]] += 1
        if a.get("auditor"):
            auditor_count[a["auditor"]] += 1
        defesa_situ[bool(a.get("houve_defesa"))][sit] += 1
        tipo_por_secao[a["secao"]][a["tipo"]] += 1

        if a.get("houve_defesa"):
            com_defesa += 1
        if sit in (Situacao.SANADO_TOTAL.value, Situacao.SANADO_PARCIAL.value, Situacao.AFASTADO.value):
            saneados += 1
        if sit == Situacao.MANTIDO.value:
            mantidos += 1

        if a.get("valor_financeiro"):
            valores_top.append({
                "codigo": a["codigo"],
                "municipio": a.get("municipio"),
                "valor": a["valor_financeiro"],
                "descricao": (a.get("descricao") or "")[:200],
            })

    valores_top.sort(key=lambda x: x["valor"] or 0, reverse=True)

    # Agregações por opinião do auditor e por relator (baseado nos relatórios)
    opiniao_count: Counter[str] = Counter()
    relator_count: Counter[str] = Counter()
    opiniao_por_relator: dict[str, Counter[str]] = defaultdict(Counter)
    for r in relatorios:
        op = r.get("opiniao_auditoria") or "Não identificada"
        rel = r.get("relator") or "Não identificado"
        opiniao_count[op] += 1
        relator_count[rel] += 1
        opiniao_por_relator[rel][op] += 1

    return {
        "totais": {
            "relatorios": len(relatorios),
            "achados": total,
            "saneados": saneados,
            "mantidos": mantidos,
            "com_defesa": com_defesa,
            "municipios": len({r["municipio"] for r in relatorios if r.get("municipio")}),
            "anos": sorted({r["ano"] for r in relatorios if r.get("ano")}),
        },
        "por_situacao": dict(sit_count),
        "por_tipo": _topn(tipo_count, 30),
        "por_secao": _topn(secao_count, 30),
        "por_municipio": _topn(municipio_count, 50),
        "por_ano": dict(sorted(ano_count.items())),
        "por_base_normativa": _topn(base_count, 30),
        "por_auditor": _topn(auditor_count, 30),
        "defesa_x_situacao": {
            "com_defesa": dict(defesa_situ[True]),
            "sem_defesa": dict(defesa_situ[False]),
        },
        "valores_top": valores_top[:20],
        "tipo_por_secao": {s: dict(tipo_por_secao[s].most_common(10)) for s in tipo_por_secao},
        "situacao_por_municipio": {m: dict(sit_por_municipio[m]) for m in sit_por_municipio},
        "por_municipio_por_ano": {
            str(ano): {
                "por_municipio": _topn(mun_ano_count[ano], 50),
                "situacao_por_municipio": {
                    m: dict(sit_por_mun_ano[ano][m]) for m in sit_por_mun_ano[ano]
                },
            }
            for ano in sorted(mun_ano_count)
        },
        "por_opiniao": dict(opiniao_count),
        "por_relator": _topn(relator_count, 50),
        "opiniao_por_relator": {rel: dict(opiniao_por_relator[rel]) for rel in opiniao_por_relator},
    }


def _topn(c: Counter, n: int) -> dict:
    return dict(c.most_common(n))
