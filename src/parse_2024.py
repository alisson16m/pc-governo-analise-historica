"""Parser determinístico para o formato 2024+ (tabela padronizada de achados)."""
from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation
from typing import Optional

from .extract_text import RelatorioTexto, extrair_secoes, secao_de_linha
from .schema import Achado, Situacao, normalizar_situacao

# Cabeçalhos esperados na tabela padrão pós-2024 (formato com header explícito)
COLUNAS_ESPERADAS = {
    "numero": ("nº", "numero", "número", "no", "n°"),
    "tipo": ("tipo",),
    "base_normativa": ("base normativa", "fundamentação", "base legal"),
    "descricao": ("descrição", "descricao", "achado"),
    "situacao": ("situação", "situacao", "status"),
    "recomendacao": ("recomendação", "recomendacao", "recomendações"),
    "determinacao": ("determinação", "determinacao", "determinações"),
}

# Valores que identificam a coluna "tipo" no formato posicional
_TIPOS_CLASSIFICACAO = frozenset({
    "impropriedade", "irregularidade", "inconsistência", "inconsistencia",
    "ineficiência", "ineficiencia", "ineficácia", "ineficacia",
})

_RE_CODIGO_LOOSE = re.compile(r"\bIII\.\s?(\d{2,3})\b")

# Padrões para delimitar a seção de achados no RESUMO
_RE_TITULO_RESUMO = re.compile(r"^(\d+)\.\s*RESUMO\s*$", re.IGNORECASE)

# Capítulos "contêiner" que agrupam achados mas não são a seção analítica
_RE_CAP_CONTEINER = re.compile(
    r"CONTRADIT[ÓO]RIO|RESUMO|CONCLUS[ÃA]O|REFER[EÊ]NCIAS|AP[ÊE]NDICE",
    re.IGNORECASE,
)
_RE_SUBCAP_ACHADOS = re.compile(
    r"Irregularidades[,\s]+Inconsist[eê]ncias[,\s]+e[,\s]+Impropriedades",
    re.IGNORECASE,
)


def _norm(s: str) -> str:
    return (s or "").strip().lower()


def _e_tipo(s: str) -> bool:
    return _norm(s) in _TIPOS_CLASSIFICACAO


def _mapear_colunas(header: list[str]) -> Optional[dict[str, int]]:
    mapa: dict[str, int] = {}
    for i, h in enumerate(header):
        hn = _norm(h)
        for chave, opcoes in COLUNAS_ESPERADAS.items():
            if any(op in hn for op in opcoes) and chave not in mapa:
                mapa[chave] = i
                break
    if "numero" in mapa and "descricao" in mapa:
        return mapa
    return None


def _parse_valor(texto: Optional[str]) -> Optional[Decimal]:
    if not texto:
        return None
    m = re.search(r"R\$\s*([\d\.\,]+)", texto)
    if not m:
        return None
    bruto = m.group(1).replace(".", "").replace(",", ".")
    try:
        return Decimal(bruto)
    except InvalidOperation:
        return None


def _normalizar_codigo(raw: str) -> Optional[str]:
    m = _RE_CODIGO_LOOSE.search(raw or "")
    if not m:
        return None
    return f"III.{int(m.group(1)):02d}"


def parse(texto: RelatorioTexto) -> Optional[list[Achado]]:
    """Tenta extrair achados do formato pós-2024.

    Estratégia 1: tabela com linha de cabeçalho nomeada.
    Estratégia 2: tabela posicional no capítulo RESUMO >
                  'Irregularidades, Inconsistências e Impropriedades'.

    Retorna None se nenhuma tabela compatível for encontrada — sinal para
    cair no parser legacy via Gemini."""
    resultado = _parse_formato_cabecalho(texto)
    if resultado is not None:
        return resultado
    return _parse_formato_posicional(texto)


# ---------------------------------------------------------------------------
# Estratégia 1 – cabeçalho explícito
# ---------------------------------------------------------------------------

def _parse_formato_cabecalho(texto: RelatorioTexto) -> Optional[list[Achado]]:
    secoes = extrair_secoes(texto)
    achados: list[Achado] = []
    encontrou_tabela = False

    for pag in texto.paginas:
        for tabela in pag.tabelas:
            if not tabela or len(tabela) < 2:
                continue
            header = [c or "" for c in tabela[0]]
            mapa = _mapear_colunas(header)
            if not mapa:
                continue
            encontrou_tabela = True
            for linha in tabela[1:]:
                if not any(linha):
                    continue
                codigo_raw = linha[mapa["numero"]] if mapa.get("numero") is not None else ""
                codigo = _normalizar_codigo(codigo_raw or "")
                if not codigo:
                    continue
                descricao = (linha[mapa["descricao"]] or "").strip()
                tipo = (linha[mapa["tipo"]].strip() if "tipo" in mapa and linha[mapa["tipo"]] else "Não classificado")
                base = linha[mapa["base_normativa"]].strip() if "base_normativa" in mapa and linha[mapa["base_normativa"]] else None
                sit_raw = linha[mapa["situacao"]] if "situacao" in mapa else None
                rec = linha[mapa["recomendacao"]].strip() if "recomendacao" in mapa and linha[mapa["recomendacao"]] else None
                det = linha[mapa["determinacao"]].strip() if "determinacao" in mapa and linha[mapa["determinacao"]] else None
                situacao = normalizar_situacao(sit_raw)
                houve_defesa = bool(situacao and situacao != Situacao.NAO_CONSTA)
                idx_global = _achar_indice(texto, codigo)
                secao = secao_de_linha(secoes, idx_global) if idx_global is not None else "Tabela de Achados"
                achados.append(Achado(
                    codigo=codigo,
                    tipo=tipo or "Não classificado",
                    secao=secao or "Tabela de Achados",
                    base_normativa=base,
                    descricao=descricao,
                    houve_defesa=houve_defesa,
                    situacao=situacao,
                    recomendacao=rec,
                    determinacao=det,
                    valor_financeiro=_parse_valor(descricao) or _parse_valor(rec),
                ))

    if not encontrou_tabela or not achados:
        return None
    vistos: dict[str, Achado] = {}
    for a in achados:
        vistos.setdefault(a.codigo, a)
    return sorted(vistos.values(), key=lambda a: a.codigo)


# ---------------------------------------------------------------------------
# Estratégia 2 – formato posicional no capítulo RESUMO
# ---------------------------------------------------------------------------

def _paginas_subcap_achados(texto: RelatorioTexto) -> list:
    """Retorna as páginas do subcapítulo 'Irregularidades...' dentro do RESUMO.

    1. Localiza a página do título 'N. RESUMO' (não do sumário).
    2. Nessa página, identifica o número do subcapítulo (ex: '11.1').
    3. Constrói o padrão de fim dinamicamente: próximo subcapítulo (11.2)
       ou próximo capítulo (12) — evitando falsos positivos de referências
       de seção dentro das células de tabela.
    """
    pag_resumo: Optional[int] = None
    cap_num: Optional[int] = None

    for p in texto.paginas:
        for ln in p.texto.splitlines():
            m = _RE_TITULO_RESUMO.match(ln.strip())
            if m:
                pag_resumo = p.numero
                cap_num = int(m.group(1))
                break
        if pag_resumo:
            break

    if pag_resumo is None:
        # Fallback: qualquer página que tenha o subcapítulo sem título numerado
        for p in texto.paginas:
            if _RE_SUBCAP_ACHADOS.search(p.texto):
                pag_resumo = p.numero
                break

    if pag_resumo is None:
        return []

    # Detectar número do subcapítulo (ex: 11.1) para construir padrão de fim
    subcap_num: Optional[int] = None
    if cap_num is not None:
        for p in texto.paginas:
            if p.numero < pag_resumo:
                continue
            for ln in p.texto.splitlines():
                ln_s = ln.strip()
                m = re.match(rf"^{cap_num}\.(\d+)[\.\s]", ln_s)
                if m and _RE_SUBCAP_ACHADOS.search(ln_s):
                    subcap_num = int(m.group(1))
                    break
            if subcap_num is not None:
                break

    # Padrão de fim: próximo subcapítulo (cap.sub+1) ou próximo capítulo (cap+1)
    if cap_num is not None and subcap_num is not None:
        prox_sub = subcap_num + 1
        prox_cap = cap_num + 1
        re_fim = re.compile(
            rf"^{cap_num}\.{prox_sub}[\.\s]|^{prox_cap}[\.\s]",
            re.IGNORECASE,
        )
    else:
        # Fallback genérico caso não tenha identificado os números
        re_fim = re.compile(
            r"^(?:Recomenda[cç][oõ]es|CONCLUS[AÃ]O)\b",
            re.IGNORECASE,
        )

    paginas: list = []
    for p in texto.paginas:
        if p.numero < pag_resumo:
            continue
        if p.numero > pag_resumo:
            for ln in p.texto.splitlines():
                if re_fim.match(ln.strip()):
                    return paginas
        paginas.append(p)

    return paginas


def _parse_formato_posicional(texto: RelatorioTexto) -> Optional[list[Achado]]:
    """Extrai achados do subcapítulo 'Irregularidades, Inconsistências e
    Impropriedades' dentro do capítulo RESUMO.

    Colunas posicionais: (III.NN) | seção | descrição | base_normativa|tipo
                         | tipo|base_normativa | [recomendação] | [situação]
    """
    paginas = _paginas_subcap_achados(texto)
    if not paginas:
        return None

    secoes = extrair_secoes(texto)
    achados_mapa: dict[str, Achado] = {}

    for pag in paginas:
        for tabela in pag.tabelas:
            if not tabela:
                continue
            for linha in tabela:
                if not linha or not linha[0]:
                    continue
                codigo = _normalizar_codigo(str(linha[0]))
                if not codigo:
                    continue

                cols = [((c or "").strip()) for c in linha]
                # Normaliza espaços internos (pdfplumber fragmenta células multi-linha)
                secao_raw = re.sub(r"\s+", " ", cols[1]).strip() if len(cols) > 1 else ""
                descricao = cols[2] if len(cols) > 2 else ""

                # cols[3] e cols[4]: um é tipo, outro é base_normativa
                c3 = cols[3] if len(cols) > 3 else ""
                c4 = cols[4] if len(cols) > 4 else ""
                if _e_tipo(c3):
                    tipo, base = c3, c4 or None
                elif _e_tipo(c4):
                    tipo, base = c4, c3 or None
                else:
                    tipo = c4 or c3 or "Não classificado"
                    base = c3 if c3 and not _e_tipo(c3) else None

                rec = cols[5] if len(cols) > 5 else None
                sit_raw = cols[6] if len(cols) > 6 else None

                situacao = normalizar_situacao(sit_raw) if sit_raw else None
                houve_defesa = bool(situacao and situacao != Situacao.NAO_CONSTA)

                idx = _achar_indice(texto, codigo)
                secao_textual = secao_de_linha(secoes, idx) if idx is not None else None
                # Usa secao_raw quando o texto só posiciona o código em capítulos
                # "contêiner" (Contraditório, Resumo…) que não são a seção analítica.
                if secao_textual and not _RE_CAP_CONTEINER.search(secao_textual):
                    secao = secao_textual
                else:
                    secao = secao_raw or secao_textual or "Tabela de Achados"

                achado = Achado(
                    codigo=codigo,
                    tipo=tipo or "Não classificado",
                    secao=secao,
                    base_normativa=base or None,
                    descricao=descricao,
                    houve_defesa=houve_defesa,
                    situacao=situacao,
                    recomendacao=rec or None,
                    determinacao=None,
                    valor_financeiro=_parse_valor(descricao),
                )
                # Última ocorrência do mesmo código prevalece (tabela pode ser
                # dividida em múltiplas linhas/páginas pelo pdfplumber)
                achados_mapa[codigo] = achado

    if not achados_mapa:
        return None
    return sorted(achados_mapa.values(), key=lambda a: a.codigo)


def _achar_indice(texto: RelatorioTexto, codigo: str) -> Optional[int]:
    for i, (_p, ln) in enumerate(texto.linhas()):
        if codigo in ln:
            return i
    return None
