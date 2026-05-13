"""Extração de achados em relatórios heterogêneos (pré-2024) via Gemini."""
from __future__ import annotations

import json
import os
import re
from typing import Optional

from dotenv import load_dotenv

from .extract_text import RelatorioTexto, extrair_secoes, secao_de_linha
from .rate_limit import aguardar, marcar_esgotado, marcar_sucesso
from .schema import Achado, Situacao, normalizar_situacao

load_dotenv()

_RE_CODIGO = re.compile(r"III\.\s?(\d{2,3})")

PROMPT = """Você é um analista do Tribunal de Contas. Extraia TODOS os achados de auditoria do trecho abaixo do relatório conclusivo de prestação de contas.

Cada achado é identificado pelo código no padrão III.NN (ex: III.01, III.02). Para cada achado, retorne um objeto JSON com os campos:
- codigo: string no formato "III.NN" (zero-padded, ex: "III.01")
- tipo: categoria/título do achado (ex: "Falhas no controle interno")
- secao: nome da seção do relatório onde o achado foi tratado
- base_normativa: dispositivo legal citado (lei, artigo) ou null
- descricao: texto resumido do achado (até 600 caracteres)
- houve_defesa: true se o relatório indica que o gestor apresentou defesa, false caso contrário
- situacao: um dos valores "sanado_total", "sanado_parcial", "afastado", "mantido", "nao_consta"
- recomendacao: texto da recomendação associada ou null
- determinacao: texto da determinação associada ou null
- valor_financeiro: valor em reais (somente número decimal, sem "R$") ou null

Retorne SOMENTE um JSON válido com a chave "achados" contendo a lista. Sem comentários, sem texto extra.

TRECHO DO RELATÓRIO:
---
{TRECHO}
---
"""


def _selecionar_trecho(texto: RelatorioTexto, max_chars: int = 15_000) -> str:
    """Foca no capítulo de análise da defesa, mas inclui contexto.

    Estratégia: localizar primeiro 'III.' no texto e enviar de lá em diante,
    truncando em max_chars."""
    full = texto.texto_completo
    m = _RE_CODIGO.search(full)
    inicio = max(0, (m.start() - 2000)) if m else 0
    return full[inicio : inicio + max_chars]


def _client():
    from google import genai

    key = os.getenv("GEMINI_API_KEY")
    if not key:
        raise RuntimeError("GEMINI_API_KEY não definido. Configure .env")
    return genai.Client(api_key=key)


def parse(texto: RelatorioTexto) -> list[Achado]:
    trecho = _selecionar_trecho(texto)
    if not trecho.strip() or not _RE_CODIGO.search(trecho):
        return []

    from google.genai import types

    aguardar()
    client = _client()
    model_name = os.getenv("GEMINI_MODEL", "gemini-2.5-flash-lite")
    try:
        resp = client.models.generate_content(
            model=model_name,
            contents=PROMPT.replace("{TRECHO}", trecho),
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                temperature=0.1,
            ),
        )
        marcar_sucesso()
    except Exception as exc:
        msg = str(exc).lower()
        if "429" in msg or "quota" in msg or "resource_exhausted" in msg:
            marcar_esgotado()
            raise RuntimeError(f"Cota diária do Gemini esgotada: {exc}") from exc
        raise
    bruto = resp.text or "{}"
    try:
        dados = json.loads(bruto)
    except json.JSONDecodeError:
        # Tenta recortar o primeiro objeto JSON da resposta
        m = re.search(r"\{[\s\S]*\}", bruto)
        if not m:
            return []
        dados = json.loads(m.group(0))

    raw_list = dados.get("achados") or []
    secoes = extrair_secoes(texto)
    out: list[Achado] = []
    for it in raw_list:
        codigo = _normalizar_codigo(it.get("codigo") or "")
        if not codigo:
            continue
        situacao = _coagir_situacao(it.get("situacao"))
        idx = _achar_indice(texto, codigo)
        secao_textual = secao_de_linha(secoes, idx) if idx is not None else (it.get("secao") or "Indefinida")
        out.append(
            Achado(
                codigo=codigo,
                tipo=(it.get("tipo") or "Não classificado").strip()[:200],
                secao=secao_textual or it.get("secao") or "Indefinida",
                base_normativa=_str_ou_none(it.get("base_normativa")),
                descricao=(it.get("descricao") or "").strip(),
                houve_defesa=bool(it.get("houve_defesa")),
                situacao=situacao,
                recomendacao=_str_ou_none(it.get("recomendacao")),
                determinacao=_str_ou_none(it.get("determinacao")),
                valor_financeiro=_num_ou_none(it.get("valor_financeiro")),
            )
        )
    # Deduplicar
    vistos: dict[str, Achado] = {}
    for a in out:
        vistos.setdefault(a.codigo, a)
    return sorted(vistos.values(), key=lambda a: a.codigo)


def _normalizar_codigo(raw: str) -> Optional[str]:
    m = _RE_CODIGO.search(raw or "")
    if not m:
        return None
    return f"III.{int(m.group(1)):02d}"


def _coagir_situacao(v) -> Optional[Situacao]:
    if not v:
        return None
    if isinstance(v, str):
        try:
            return Situacao(v)
        except ValueError:
            return normalizar_situacao(v)
    return None


def _str_ou_none(v) -> Optional[str]:
    if v is None:
        return None
    s = str(v).strip()
    return s or None


def _num_ou_none(v):
    if v is None or v == "":
        return None
    try:
        from decimal import Decimal
        return Decimal(str(v))
    except Exception:
        return None


def _achar_indice(texto: RelatorioTexto, codigo: str):
    for i, (_p, ln) in enumerate(texto.linhas()):
        if codigo in ln:
            return i
    return None
