"""Extrai defesa do gestor e análise técnica por achado do capítulo Contraditório."""
from __future__ import annotations

import re

from .extract_text import RelatorioTexto

_MAX_CHARS = 800

# Título do capítulo: linha isolada ou com prefixo "N |" (pdfplumber mescla colunas do sumário)
_RE_TITULO = re.compile(
    r'^(?:\d+\s*[|.]\s*)?CONTRADIT[ÓO]RIO(?:\s+E\s+AMPLA\s+DEFESA)?',
    re.MULTILINE | re.IGNORECASE,
)
# Início do próximo capítulo principal (sinal de fim do contraditório)
_RE_PROXIMO_CAP = re.compile(
    r'^(?:\d+\.\s+)(?:RESUMO|CONCLUS[ÃA]O|REFER[ÊE]NCIAS|AP[ÊE]NDICE)\s*$',
    re.IGNORECASE | re.MULTILINE,
)

# Junk típico do pdfplumber: hash de assinatura, bloco invertido de assinatura digital, URLs, página
_RE_JUNK = re.compile(
    r'[0-9A-F]{20,}[ \t]*\n'
    r'|OGID[ÓO]C[\s\S]{0,800}?ACINÔRTELE\s+ARUTANISSA[ \t]*\n?'
    r'|rb\.ct\.\S+[ \t]*\n?'
    r'|(?:^|\n)\s*\d{1,3}\s*\n',
    re.IGNORECASE,
)

_RE_DEFESA = re.compile(
    r'(?:DEFESA\s+APRESENTADA|Defesa\s+apresentada)[^\n]*\n',
    re.IGNORECASE,
)
_RE_ANALISE = re.compile(
    r'(?:AN[ÁA]LISE\s+T[ÉE]CNICA|An[áa]lise\s+t[ée]cnica)[^\n]*\n',
    re.IGNORECASE,
)
_RE_CODIGO = re.compile(r'\(?III\.(\d{2,3})\)?')

# Capítulo declara explicitamente que o gestor não apresentou defesa alguma
_RE_SEM_DEFESA_GLOBAL = re.compile(
    r'n[ãa]o\s+apresentou\s+qualquer\s+justificativa'
    r'|todas\s+as\s+(?:Irregularidades[\s\S]{0,80}?Impropriedades|III[^\n]{0,80})'
    r'[\s\S]{0,400}?foram\s+integralmente\s+mantidas',
    re.IGNORECASE,
)

# Análise técnica indica que o achado específico não foi contestado
_RE_NAO_CONTESTOU = re.compile(
    r'n[ãa]o\s+contestou\s+o\s+achado'
    r'|n[ãa]o\s+apresentou\s+(?:qualquer\s+)?(?:justificativa|defesa)\b'
    r'|mantém[\s-]se\s+o\s+entendimento\s+inicial',
    re.IGNORECASE,
)


def _limpar(txt: str) -> str:
    txt = _RE_JUNK.sub(' ', txt)
    txt = re.sub(r'[ \t]{2,}', ' ', txt)
    txt = re.sub(r'\n{3,}', '\n\n', txt)
    return txt


def _truncar(txt: str) -> str:
    txt = txt.strip()
    if len(txt) <= _MAX_CHARS:
        return txt
    # Trunca na última frase completa dentro do limite
    corte = txt.rfind('.', 0, _MAX_CHARS)
    return txt[: corte + 1] if corte > 0 else txt[:_MAX_CHARS]


def extrair(texto: RelatorioTexto) -> dict:
    """Retorna {codigo: {defesa_gestor, analise_tecnica, houve_defesa?}} para o capítulo Contraditório.

    Casos:
    - {"_sem_defesa_global": True} quando o capítulo declara que não houve defesa alguma.
    - {codigo: {...}} com achados que tiveram "DEFESA APRESENTADA" (houve_defesa implícito True).
    - {codigo: {"houve_defesa": False, ...}} para achados com ANÁLISE TÉCNICA mas sem DEFESA.
    """
    txt = texto.texto_completo

    # Isolar capítulo Contraditório
    caps = list(_RE_TITULO.finditer(txt))
    if not caps:
        return {}
    # Prefere o último match com prefixo numérico (cabeçalho real, não rodapé de página)
    caps_num = [m for m in caps if re.match(r'^\d+', m.group())]
    titulo_m = caps_num[-1] if caps_num else caps[-1]
    inicio = titulo_m.start()

    # Número do capítulo Contraditório (ex: "11" em "11. CONTRADITÓRIO...")
    _m_num = re.match(r'^(\d+)', titulo_m.group())
    cap_num_int = int(_m_num.group(1)) if _m_num else 0

    # Próximo capítulo: número obrigatoriamente maior que o capítulo Contraditório
    # (evita falso-positivo com "11. RESUMO" em cabeçalhos de página dentro do capítulo)
    _RE_PROX_NUM = re.compile(
        r'^(\d+)\.\s+(?:RESUMO|CONCLUS[ÃA]O|REFER[ÊE]NCIAS|AP[ÊE]NDICE)\s*$',
        re.IGNORECASE | re.MULTILINE,
    )
    fim_m = None
    for _m in _RE_PROX_NUM.finditer(txt, inicio + 500):
        if int(_m.group(1)) > cap_num_int:
            fim_m = _m
            break
    if fim_m is None:
        fim_m = _RE_PROXIMO_CAP.search(txt, inicio + 500)

    cap_txt = _limpar(txt[inicio: fim_m.start() if fim_m else inicio + 120_000])

    # Caso 1: capítulo declara globalmente que não houve defesa
    if _RE_SEM_DEFESA_GLOBAL.search(cap_txt):
        return {"_sem_defesa_global": True}

    defesas = list(_RE_DEFESA.finditer(cap_txt))
    analises = list(_RE_ANALISE.finditer(cap_txt))

    resultado: dict = {}

    # Caso 2: achados com "DEFESA APRESENTADA" explícita
    for i, d_m in enumerate(defesas):
        preambulo = cap_txt[: d_m.start()]
        codigos = _RE_CODIGO.findall(preambulo)
        if not codigos:
            continue
        codigo = f"III.{int(codigos[-1]):02d}"

        a_m = next((a for a in analises if a.start() > d_m.end()), None)
        if a_m:
            defesa_txt = cap_txt[d_m.end() : a_m.start()]
            prox_defesa = defesas[i + 1] if i + 1 < len(defesas) else None
            fim_analise = prox_defesa.start() if prox_defesa else len(cap_txt)
            analise_txt: str | None = cap_txt[a_m.end() : fim_analise]
        else:
            defesa_txt = cap_txt[d_m.end() :]
            analise_txt = None

        resultado[codigo] = {
            "defesa_gestor": _truncar(defesa_txt) or None,
            "analise_tecnica": _truncar(analise_txt) if analise_txt else None,
        }

    # Caso 3: ANÁLISE TÉCNICA sem DEFESA APRESENTADA → houve_defesa=False
    codigos_com_defesa = set(resultado.keys())
    todos_codigos = list(_RE_CODIGO.finditer(cap_txt))

    for i, a_m in enumerate(analises):
        preambulo = cap_txt[: a_m.start()]
        codigos = _RE_CODIGO.findall(preambulo)
        if not codigos:
            continue
        codigo = f"III.{int(codigos[-1]):02d}"

        if codigo in codigos_com_defesa:
            continue

        # Verifica se não há DEFESA entre o último III.NN e esta ANÁLISE
        ultimo_cod_m = next(
            (m for m in reversed(todos_codigos) if m.start() < a_m.start()),
            None,
        )
        trecho = cap_txt[ultimo_cod_m.end() : a_m.start()] if ultimo_cod_m else ""
        if _RE_DEFESA.search(trecho):
            continue

        prox_d = next((d for d in defesas if d.start() > a_m.end()), None)
        prox_a = analises[i + 1] if i + 1 < len(analises) else None
        candidates = [x.start() for x in [prox_d, prox_a] if x is not None]
        fim = min(candidates) if candidates else len(cap_txt)

        resultado[codigo] = {
            "defesa_gestor": None,
            "analise_tecnica": _truncar(cap_txt[a_m.end() : fim]),
            "houve_defesa": False,
        }

    return resultado


def resumir_texto(texto: str, rotulo: str) -> "str | None":
    """Chama Gemini para gerar um resumo de 2-3 frases de um trecho do contraditório."""
    if not texto or not texto.strip():
        return None

    prompt = (
        f"Você é um analista do Tribunal de Contas. "
        f"Leia o trecho abaixo, que corresponde a '{rotulo}' de um achado de auditoria, "
        f"e escreva um resumo objetivo de 2 a 3 frases em português, "
        f"destacando os pontos principais.\n\n"
        f"{texto.strip()}"
    )

    import os
    from google import genai
    from dotenv import load_dotenv
    from .rate_limit import com_rate_limit, marcar_esgotado

    load_dotenv()
    key = os.getenv("GEMINI_API_KEY")
    if not key:
        raise RuntimeError("GEMINI_API_KEY não definido. Configure .env")

    client = genai.Client(api_key=key)
    model_name = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")

    @com_rate_limit
    def _chamar():
        return client.models.generate_content(model=model_name, contents=prompt)

    try:
        resp = _chamar()
        return resp.text.strip() or None
    except RuntimeError:
        raise
    except Exception as exc:
        msg = str(exc).lower()
        if "daily" in msg or "per_day" in msg or "quota" in msg:
            marcar_esgotado()
        return None
