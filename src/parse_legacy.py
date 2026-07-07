"""Extração de achados em relatórios heterogêneos (pré-2024) via Gemini."""
from __future__ import annotations

import json
import os
import re
from typing import Optional

from dotenv import load_dotenv

from decimal import Decimal

from .extract_text import RelatorioTexto, achar_indice_codigo, extrair_secoes, secao_de_linha
from .rate_limit import com_rate_limit, marcar_esgotado, modelo_gemini
from .schema import Achado, normalizar_situacao

load_dotenv()

_RE_CODIGO = re.compile(r"III\.\s?(\d{2,3})")
_MAX_CHARS_GEMINI = 80_000

_RE_SUBCAP_ACHADOS = re.compile(
    r"Irregularidades[,\s]+Inconsist[eê]ncias[,\s]+e[,\s]+Impropriedades",
    re.IGNORECASE,
)

PROMPT = """Você é um analista do Tribunal de Contas. Extraia TODOS os achados de auditoria do trecho abaixo do relatório conclusivo de prestação de contas.

Cada achado é identificado pelo código no padrão III.NN (ex: III.01, III.02). Para cada achado, retorne um objeto JSON com os campos:
- codigo: string no formato "III.NN" (zero-padded, ex: "III.01")
- tipo: classificação técnica do achado conforme coluna "Classificação do Achado" da tabela. \
DEVE ser EXATAMENTE um destes três valores: "Impropriedade", "Irregularidade" ou "Inconsistência". \
NÃO use o título do subcapítulo ("Irregularidades, Inconsistências e Impropriedades") \
nem qualquer outro texto como tipo.
- secao: nome da seção do relatório onde o achado foi tratado (ex: "3. Aspectos Orçamentários e Financeiros")
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

_TIPO_MAP: dict[str, str] = {
    "impropriedade": "Impropriedade",
    "irregularidade": "Irregularidade",
    "inconsistência": "Inconsistência",
    "inconsistencia": "Inconsistência",
    # Os dois abaixo são mantidos apenas como fallback de normalização
    # caso relatórios antigos os contenham; o prompt não os solicita mais.
    "ineficiência": "Ineficiência",
    "ineficiencia": "Ineficiência",
    "ineficácia": "Ineficácia",
    "ineficacia": "Ineficácia",
}


def _normalizar_tipo(raw: str) -> str:
    """Mapeia o tipo retornado pelo Gemini para a classificação canônica.

    Evita que o Gemini use o título do subcapítulo ("Irregularidades,
    Inconsistências e Impropriedades") como tipo."""
    norm = (raw or "").strip().lower()
    # Correspondência exata primeiro
    if norm in _TIPO_MAP:
        return _TIPO_MAP[norm]
    # Substring: captura "Impropriedade" dentro de um texto mais longo
    for chave, valor in _TIPO_MAP.items():
        if chave in norm:
            return valor
    return "Não classificado"


def _selecionar_trecho(texto: RelatorioTexto, max_chars: int = _MAX_CHARS_GEMINI) -> str:
    """Seleciona o trecho mais relevante para enviar ao Gemini.

    Prioridade:
    1. Última ocorrência de 'Irregularidades, Inconsistências e Impropriedades'
       que seja seguida por códigos III.NN dentro dos próximos 8 000 chars —
       esse é o subcapítulo do RESUMO com a tabela completa de achados.
    2. Fallback: janela de max_chars a partir do primeiro III.NN encontrado.
    """
    full = texto.texto_completo

    # Procura a última menção ao subcapítulo que tenha achados logo adiante.
    melhor_inicio: Optional[int] = None
    for m in _RE_SUBCAP_ACHADOS.finditer(full):
        janela = full[m.start() : m.start() + 8_000]
        if _RE_CODIGO.search(janela):
            melhor_inicio = max(0, m.start() - 500)

    if melhor_inicio is not None:
        return full[melhor_inicio : melhor_inicio + max_chars]

    # Fallback: janela a partir do primeiro código III.NN
    m_codigo = _RE_CODIGO.search(full)
    inicio = max(0, (m_codigo.start() - 2000)) if m_codigo else 0
    return full[inicio : inicio + max_chars]


def _client():
    from google import genai

    key = os.getenv("GEMINI_API_KEY")
    if not key:
        raise RuntimeError("GEMINI_API_KEY não definido. Configure .env")
    return genai.Client(api_key=key)


@com_rate_limit
def _chamar_gemini(trecho: str):
    from google.genai import types

    client = _client()
    model_name = modelo_gemini()
    return client.models.generate_content(
        model=model_name,
        contents=PROMPT.replace("{TRECHO}", trecho),
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            temperature=0,
        ),
    )


def parse(texto: RelatorioTexto) -> list[Achado]:
    trecho = _selecionar_trecho(texto)
    if not trecho.strip() or not _RE_CODIGO.search(trecho):
        return []

    try:
        resp = _chamar_gemini(trecho)
    except Exception as exc:
        msg = str(exc).lower()
        if "429" in msg or "quota" in msg or "resource_exhausted" in msg:
            # Marca esgotado apenas para erros de cota diária; RPM é transitório
            if "daily" in msg or "per_day" in msg or "quota" in msg:
                marcar_esgotado()
            raise RuntimeError(f"Cota do Gemini atingida: {exc}") from exc
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
        situacao = normalizar_situacao(it.get("situacao"))
        idx = achar_indice_codigo(texto, codigo)
        secao_textual = secao_de_linha(secoes, idx) if idx is not None else (it.get("secao") or "Indefinida")
        out.append(
            Achado(
                codigo=codigo,
                tipo=_normalizar_tipo(it.get("tipo") or ""),
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



def _str_ou_none(v) -> Optional[str]:
    if v is None:
        return None
    s = str(v).strip()
    return s or None


def _num_ou_none(v):
    if v is None or v == "":
        return None
    try:
        return Decimal(str(v))
    except Exception:
        return None


