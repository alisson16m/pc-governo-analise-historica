"""Parser determinístico para o formato 2024+ (tabela padronizada de achados)."""
from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation
from typing import Optional

from .extract_text import RelatorioTexto, achar_indice_codigo, extrair_secoes, secao_de_linha
from .schema import Achado, Situacao, normalizar_situacao

# Cabeçalhos esperados na tabela padrão pós-2024 (formato com header explícito)
# ATENÇÃO: a ordem das chaves importa.
# "descricao" deve vir antes de "situacao" para que "Situação identificada"
# seja capturada pelo match exato de descricao antes do substring "situação"
# da chave situacao. A função _mapear_colunas() usa a primeira correspondência;
# se reordenar as chaves ou adicionar novas, verificar os testes para evitar
# mapear "Situação identificada" erroneamente para "situacao" em 2023.
COLUNAS_ESPERADAS = {
    "numero": ("nº", "numero", "número", "no", "n°"),
    "tipo": ("tipo", "classificação do achado", "classificacao do achado"),
    "base_normativa": ("base normativa", "fundamentação", "base legal"),
    "descricao": (
        "descrição", "descricao", "achado",
        "situação identificada", "situacao identificada",
    ),
    "situacao": (
        "situação", "situacao", "status",
        "situação após análise", "situacao apos analise",
    ),
    "recomendacao": (
        "recomendação", "recomendacao", "recomendações",
        "recomendação/determinação", "recomendacao/determinacao",
    ),
    "determinacao": ("determinação", "determinacao", "determinações"),
}

# Valores que identificam a coluna "tipo" no formato posicional
_TIPOS_CLASSIFICACAO = frozenset({
    "impropriedade", "irregularidade", "inconsistência", "inconsistencia",
    "ineficiência", "ineficiencia", "ineficácia", "ineficacia",
})

_RE_CODIGO_LOOSE = re.compile(r"\bIII\.\s?(\d{2,3})\b")

# Padrões para delimitar a seção de achados no RESUMO
_RE_TITULO_RESUMO = re.compile(r"^(\d+)\.?\s*RESUMO\s*$", re.IGNORECASE)

# Capítulos "contêiner" que agrupam achados mas não são a seção analítica
_RE_CAP_CONTEINER = re.compile(
    r"CONTRADIT[ÓO]RIO|RESUMO|CONCLUS[ÃA]O|REFER[EÊ]NCIAS|AP[ÊE]NDICE",
    re.IGNORECASE,
)
_RE_SUBCAP_ACHADOS = re.compile(
    r"Irregularidades[,\s]+Inconsist[eê]ncias[,\s]+e[,\s]+Impropriedades",
    re.IGNORECASE,
)
# Título de subcapítulo numerado: "11.1 Irregularidades, Inconsistências e Impropriedades"
# Aceita opcionalmente sufixo "– III" (formato Belém 2023)
_RE_SUBCAP_NUMERADO = re.compile(
    r"^(\d+)\.(\d+)\.?[\s\-–]+Irregularidades[,\s]+Inconsist[eê]ncias[,\s]+e[,\s]+Impropriedades"
    r"(?:\s*[–\-]\s*III)?",
    re.IGNORECASE,
)

# Regex para extrair tipo e situação diretamente do texto plano do RESUMO
_RE_TIPO_TEXTO = re.compile(
    r"\b(Impropriedade|Irregularidade|Inconsist[eê]ncia|Inefici[eê]ncia|Inefic[aá]cia)\b",
    re.IGNORECASE,
)
_RE_SITUACAO_TEXTO = re.compile(
    r"\b(Sanado\s+Parcial|Sanado\s+Total|Sanado|Mantido|Afastado|N[aã]o\s+Consta)\b",
    re.IGNORECASE,
)

# Clusters consonantais que NUNCA iniciam palavras portuguesas.
# Quando aparecem após um espaço numa célula PDF, indicam sílaba quebrada pelo
# pdfplumber (ex: "Compleme ntar" → "Complementar", "impor tante" → "importante").
# Clusters válidos de início (pr, br, tr, cl, fl…) são excluídos propositalmente.
_RE_SILABA = re.compile(
    r"([A-Za-záéíóúâêôãõçÀ-ÿ]) "
    r"(nt|nd|nç|ng|nf|nv|nm|mp|mb|mn|lt|ld|lm|lv|rt|rd|rm|rn|rv|rç|ct|pt|bt|ss|rr|ll|nn)"
    r"(?=[a-záéíóúâêôãõçà-ÿ])",
)


def _norm(s: str) -> str:
    return (s or "").strip().lower()


def _sit(sit_raw: Optional[str]) -> Optional["Situacao"]:
    """Normaliza situação com fallback para remover espaços espúrios ('Man tido' → 'Mantido')."""
    if not sit_raw:
        return None
    result = normalizar_situacao(sit_raw)
    if result not in (None, Situacao.NAO_CONSTA):
        return result
    result2 = normalizar_situacao(sit_raw.replace(" ", ""))
    return result2 if result2 not in (None, Situacao.NAO_CONSTA) else result


def _cel(s: Optional[str]) -> str:
    """Normaliza texto de célula PDF: colapsa newlines e une sílabas quebradas."""
    if not s:
        return ""
    t = re.sub(r"-\n", "", s)           # hífens explícitos de quebra de linha
    t = re.sub(r"\s+", " ", t).strip()  # espaço único
    t = _RE_SILABA.sub(r"\1\2", t)      # clusters inválidos → sílaba quebrada
    return t


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


def _parse_tabela_compacta(
    tabela: list,
    secoes: list,
    texto: "RelatorioTexto",
) -> "Optional[Achado]":
    """Extrai achado de tabela compacta sem cabeçalho (formato 8-cols do RESUMO).

    O pdfplumber divide o RESUMO em uma tabela-mestra de 14 colunas (que contém
    o III.01) e em tabelas menores de 8 colunas para os demais achados.  Nessas
    tabelas menores, situação/tipo/base frequentemente aparecem em linhas de
    continuação — por isso é preciso agregar TODAS as linhas antes de extrair.

    Estratégia: agrupa valores por coluna (ignorando Nones), depois varre da
    direita para esquerda para identificar situação → tipo → base; o restante
    vira descrição.
    """
    # Agrega valores por coluna, ignorando células vazias
    ncols = max((len(r) for r in tabela if r), default=0)
    if not ncols:
        return None

    por_coluna: dict[int, list[str]] = {}
    for row in tabela:
        for i, val in enumerate(row or []):
            c = _cel(val)
            if c:
                por_coluna.setdefault(i, []).append(c)

    # Código na primeira linha, primeira coluna
    codigo = _normalizar_codigo(por_coluna.get(0, [""])[0])
    if not codigo:
        return None

    # Seção na primeira linha, segunda coluna
    secao_col = (por_coluna.get(1) or [""])[0]

    usadas: set[int] = {0, 1}
    sit_raw: Optional[str] = None
    tipo = "Não classificado"
    base: Optional[str] = None

    # Varredura da direita: localiza situação, tipo e base por conteúdo
    for i in range(ncols - 1, 1, -1):
        vals = por_coluna.get(i, [])
        if not vals:
            continue
        # Situação: procura valor explicitamente reconhecível (não apenas NAO_CONSTA)
        sit_found = next(
            (v for v in vals
             if normalizar_situacao(v) not in (None, Situacao.NAO_CONSTA)
             or normalizar_situacao(v.replace(" ", "")) not in (None, Situacao.NAO_CONSTA)),
            None,
        )
        tipo_found = next((v for v in vals if _e_tipo(v)), None)
        if sit_raw is None and sit_found:
            sit_raw = sit_found
            usadas.add(i)
        elif tipo == "Não classificado" and tipo_found:
            tipo = tipo_found
            usadas.add(i)
        elif base is None:
            base = " ".join(vals)
            usadas.add(i)
            break

    # Descrição: une todos os valores das colunas não usadas (cols 2..N)
    descricao = " ".join(
        v
        for i in range(2, ncols)
        if i not in usadas
        for v in por_coluna.get(i, [])
    )

    situacao = _sit(sit_raw)
    houve_defesa = bool(situacao and situacao != Situacao.NAO_CONSTA)

    idx = achar_indice_codigo(texto, codigo)
    secao_textual = secao_de_linha(secoes, idx) if idx is not None else None
    if secao_textual and not _RE_CAP_CONTEINER.search(secao_textual):
        secao = secao_textual
    else:
        secao = secao_col or secao_textual or "Tabela de Achados"

    return Achado(
        codigo=codigo,
        tipo=tipo,
        secao=secao,
        base_normativa=base or None,
        descricao=descricao,
        houve_defesa=houve_defesa,
        situacao=situacao,
        recomendacao=None,
        determinacao=None,
        valor_financeiro=_parse_valor(descricao),
    )


def _parse_formato_texto_resumo(
    texto: "RelatorioTexto",
    achados_existentes: set,
    secoes: list,
) -> "list[Achado]":
    """Extrai achados do texto plano do RESUMO para os que o pdfplumber não captura.

    O pdfplumber às vezes deixa de incluir certas linhas do RESUMO nas tabelas
    extraídas (linhas formatadas de modo diferente no PDF).  Esta função varre o
    texto linearizado das mesmas páginas e acrescenta qualquer III.XX que ainda
    não foi encontrado pelas estratégias de tabela.

    Só é chamada quando já existe resultado de tabela (resultado não-None).
    """
    paginas = _paginas_subcap_achados(texto)
    if not paginas:
        return []

    texto_resumo = "\n".join(p.texto for p in paginas)
    matches = list(_RE_CODIGO_LOOSE.finditer(texto_resumo))

    novos: list[Achado] = []
    for k, m in enumerate(matches):
        codigo = f"III.{int(m.group(1)):02d}"
        if codigo in achados_existentes:
            continue

        # Janela de texto: deste código até o início do próximo (ou +800 chars)
        inicio = m.start()
        fim = matches[k + 1].start() if k + 1 < len(matches) else min(inicio + 800, len(texto_resumo))
        bloco = texto_resumo[inicio:fim]

        m_tipo = _RE_TIPO_TEXTO.search(bloco)
        tipo = m_tipo.group(0).capitalize() if m_tipo else "Não classificado"

        m_sit = _RE_SITUACAO_TEXTO.search(bloco)
        sit_raw = m_sit.group(0) if m_sit else None
        situacao = _sit(sit_raw)
        houve_defesa = bool(situacao and situacao != Situacao.NAO_CONSTA)

        idx = achar_indice_codigo(texto, codigo)
        secao_textual = secao_de_linha(secoes, idx) if idx is not None else None
        if secao_textual and not _RE_CAP_CONTEINER.search(secao_textual):
            secao = secao_textual
        else:
            secao = "Tabela de Achados"

        novos.append(Achado(
            codigo=codigo,
            tipo=tipo,
            secao=secao,
            base_normativa=None,
            descricao="",
            houve_defesa=houve_defesa,
            situacao=situacao,
            recomendacao=None,
            determinacao=None,
            valor_financeiro=None,
        ))

    return novos


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
    Estratégia 3 (suplementar): texto plano do RESUMO para achados que o
                  pdfplumber não captura em tabela.

    Retorna None se nenhuma tabela compatível for encontrada — sinal para
    cair no parser legacy via Gemini."""
    resultado = _parse_formato_cabecalho(texto)
    if resultado is None:
        resultado = _parse_formato_posicional(texto)
    if resultado is None:
        return None  # nenhuma tabela encontrada → cai no Gemini

    # Suplementa com achados que as tabelas deixaram passar (pdfplumber por
    # vezes não extrai todas as linhas de uma tabela mista no RESUMO)
    existentes = {a.codigo for a in resultado}
    secoes = extrair_secoes(texto)
    extras = _parse_formato_texto_resumo(texto, existentes, secoes)
    if not extras:
        return resultado

    todos: dict[str, Achado] = {a.codigo: a for a in resultado}
    for a in extras:
        todos.setdefault(a.codigo, a)
    return sorted(todos.values(), key=lambda a: a.codigo)


# ---------------------------------------------------------------------------
# Estratégia 1 – cabeçalho explícito
# ---------------------------------------------------------------------------

def _parse_formato_cabecalho(texto: RelatorioTexto) -> Optional[list[Achado]]:
    secoes = extrair_secoes(texto)
    achados: list[Achado] = []
    encontrou_tabela = False
    mapa_ativo: Optional[dict[str, int]] = None

    for pag in texto.paginas:
        for tabela in pag.tabelas:
            if not tabela:
                continue
            header = [c or "" for c in tabela[0]]
            mapa = _mapear_colunas(header)

            if mapa:
                mapa_ativo = mapa
                linhas_dados = tabela[1:]
            elif (
                mapa_ativo
                and header
                and _RE_CODIGO_LOOSE.search(header[0])
            ):
                # Continuação sem cabeçalho.  Se a tabela tem menos colunas do
                # que o mapa espera, é o formato compacto do RESUMO (8-cols):
                # situação/tipo frequentemente aparecem em linhas de continuação,
                # por isso processamos a tabela inteira de uma vez.
                if len(tabela[0]) <= max(mapa_ativo.values()):
                    achado_comp = _parse_tabela_compacta(tabela, secoes, texto)
                    if achado_comp:
                        encontrou_tabela = True
                        achados.append(achado_comp)
                    continue
                mapa = mapa_ativo
                linhas_dados = tabela
            else:
                continue

            if not linhas_dados:
                continue

            encontrou_tabela = True
            for linha in linhas_dados:
                if not any(linha):
                    continue
                # Pula linhas com menos colunas do que o mapeamento requer
                # (tabelas compactas são tratadas no nível de tabela acima)
                if mapa and len(linha) <= max(mapa.values()):
                    continue
                codigo_raw = linha[mapa["numero"]] if mapa.get("numero") is not None else ""
                codigo = _normalizar_codigo(codigo_raw or "")
                if not codigo:
                    continue
                descricao = _cel(linha[mapa["descricao"]])
                tipo = _cel(linha[mapa["tipo"]]) if "tipo" in mapa and linha[mapa["tipo"]] else "Não classificado"
                base = _cel(linha[mapa["base_normativa"]]) if "base_normativa" in mapa and linha[mapa["base_normativa"]] else None
                sit_raw = linha[mapa["situacao"]] if "situacao" in mapa else None
                rec = _cel(linha[mapa["recomendacao"]]) if "recomendacao" in mapa and linha[mapa["recomendacao"]] else None
                det = _cel(linha[mapa["determinacao"]]) if "determinacao" in mapa and linha[mapa["determinacao"]] else None
                situacao = _sit(sit_raw)
                houve_defesa = bool(situacao and situacao != Situacao.NAO_CONSTA)
                idx_global = achar_indice_codigo(texto, codigo)
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

    subcap_num_fallback: Optional[int] = None
    if pag_resumo is None:
        # Fallback 1: busca título numerado "N.N Irregularidades..." tomando a ÚLTIMA
        # ocorrência — a primeira pode ser o sumário/índice; a última é a seção real.
        last_match_pag: Optional[int] = None
        last_cap_num: Optional[int] = None
        last_subcap_num: Optional[int] = None
        for p in texto.paginas:
            for ln in p.texto.splitlines():
                m = _RE_SUBCAP_NUMERADO.match(ln.strip())
                if m:
                    last_match_pag = p.numero
                    last_cap_num = int(m.group(1))
                    last_subcap_num = int(m.group(2))
        if last_match_pag is not None:
            pag_resumo = last_match_pag
            cap_num = last_cap_num
            subcap_num_fallback = last_subcap_num

        if pag_resumo is None:
            # Fallback 2 (último recurso): qualquer página com o termo
            for p in texto.paginas:
                if _RE_SUBCAP_ACHADOS.search(p.texto):
                    pag_resumo = p.numero
                    break

    if pag_resumo is None:
        return []

    # Detectar número do subcapítulo (ex: 11.1) para construir padrão de fim
    subcap_num: Optional[int] = subcap_num_fallback
    if cap_num is not None and subcap_num is None:
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

                cols = [_cel(c) for c in linha]
                secao_raw = cols[1] if len(cols) > 1 else ""
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

                situacao = _sit(sit_raw)
                houve_defesa = bool(situacao and situacao != Situacao.NAO_CONSTA)

                idx = achar_indice_codigo(texto, codigo)
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


