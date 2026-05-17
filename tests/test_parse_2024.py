from src.parse_2024 import _mapear_colunas


def test_mapear_colunas_formato_2024():
    """Garante que o formato existente (2024) continua funcionando."""
    header = ["Nº", "Tipo", "Base Normativa", "Descrição", "Situação",
              "Recomendação", "Determinação"]
    mapa = _mapear_colunas(header)
    assert mapa is not None
    assert mapa["numero"] == 0
    assert mapa["tipo"] == 1
    assert mapa["descricao"] == 3
    assert mapa["situacao"] == 4


def test_mapear_colunas_formato_2023():
    """Garante que o formato 2023 é reconhecido corretamente."""
    header = [
        "Nº",
        "Seção do Relatório",
        "Situação identificada",
        "Base Normativa",
        "Classificação do Achado",
        "Recomendação/Determinação",
        "Situação após análise do Contraditório",
    ]
    mapa = _mapear_colunas(header)
    assert mapa is not None, "Parser deve reconhecer o formato 2023"
    assert mapa["numero"] == 0
    assert mapa["descricao"] == 2, "'Situação identificada' deve ser mapeada como descrição"
    assert mapa["base_normativa"] == 3
    assert mapa["tipo"] == 4, "'Classificação do Achado' deve ser mapeada como tipo"
    assert mapa["recomendacao"] == 5
    assert mapa["situacao"] == 6, "'Situação após análise do Contraditório' deve ser mapeada como situação"


def test_mapear_colunas_situacao_identificada_nao_vira_situacao():
    """Garante que 'Situação identificada' NÃO é mapeada como situação (bug antigo)."""
    header = ["Nº", "Seção do Relatório", "Situação identificada",
              "Base Normativa", "Classificação do Achado",
              "Recomendação/Determinação", "Situação após análise do Contraditório"]
    mapa = _mapear_colunas(header)
    assert mapa is not None
    # A coluna índice 2 é "Situação identificada" — deve ser descricao, nunca situacao
    assert mapa.get("descricao") == 2
    assert mapa.get("situacao") != 2


from src.parse_2024 import _RE_SUBCAP_NUMERADO


def test_subcap_numerado_sem_sufixo():
    """Título padrão sem sufixo continua funcionando."""
    titulo = "11.1 Irregularidades, Inconsistências e Impropriedades"
    assert _RE_SUBCAP_NUMERADO.match(titulo) is not None


def test_subcap_numerado_com_sufixo_iii():
    """Título com sufixo '– III' deve ser reconhecido (formato Belém 2023)."""
    titulo = "12.1. Irregularidades, Inconsistências e Impropriedades – III"
    assert _RE_SUBCAP_NUMERADO.match(titulo) is not None, \
        "Título com sufixo '– III' não foi reconhecido"


def test_subcap_numerado_com_hifen_simples():
    """Título com hífen simples antes de III também deve funcionar."""
    titulo = "10.1 Irregularidades, Inconsistências e Impropriedades - III"
    assert _RE_SUBCAP_NUMERADO.match(titulo) is not None


from pathlib import Path
from src.extract_text import RelatorioTexto, Pagina
from src.parse_2024 import _parse_formato_cabecalho


def _fazer_relatorio(paginas_tabelas: list[list[list[list[str]]]]) -> RelatorioTexto:
    """Monta um RelatorioTexto mínimo para testes."""
    paginas = []
    texto_total = []
    for i, tabelas in enumerate(paginas_tabelas, start=1):
        linhas_texto = []
        for tabela in tabelas:
            for row in tabela:
                linhas_texto.append(" | ".join(c or "" for c in row))
        texto_pag = "\n".join(linhas_texto)
        paginas.append(Pagina(numero=i, texto=texto_pag, tabelas=tabelas))
        texto_total.append(texto_pag)
    return RelatorioTexto(
        arquivo=Path("fake.pdf"),
        sha256="abc123",
        paginas=paginas,
        texto_completo="\n".join(texto_total),
    )


HEADER_2023 = [
    "Nº", "Seção do Relatório", "Situação identificada",
    "Base Normativa", "Classificação do Achado",
    "Recomendação/Determinação", "Situação após análise do Contraditório",
]

ROW_III01 = [
    "III.01", "3. Gestão Fiscal", "Inconsistência na gestão orçamentária",
    "LC 101/2000", "Inconsistência", "Recomenda-se correção", "Mantido",
]

ROW_III02 = [
    "III.02", "3. Gestão Fiscal", "Irregularidade na contratação",
    "CF art. 37", "Irregularidade", "Determina-se regularização", "Sanado",
]


def test_formato_cabecalho_2023_pagina_unica():
    """Parser extrai achados de tabela 2023 em página única com cabeçalho."""
    rt = _fazer_relatorio([[[HEADER_2023, ROW_III01, ROW_III02]]])
    resultado = _parse_formato_cabecalho(rt)
    assert resultado is not None
    assert len(resultado) == 2
    codigos = {a.codigo for a in resultado}
    assert "III.01" in codigos
    assert "III.02" in codigos


def test_formato_cabecalho_2023_pagina_sem_cabecalho():
    """Parser propaga mapeamento para página de continuação sem cabeçalho."""
    # Página 1: cabeçalho + III.01
    # Página 2: sem cabeçalho, apenas III.02 (continuação)
    rt = _fazer_relatorio([
        [[HEADER_2023, ROW_III01]],   # página 1
        [[ROW_III02]],                 # página 2 — sem cabeçalho
    ])
    resultado = _parse_formato_cabecalho(rt)
    assert resultado is not None
    assert len(resultado) == 2, (
        "Achado da página sem cabeçalho deve ser extraído via propagação de mapeamento"
    )
    codigos = {a.codigo for a in resultado}
    assert "III.01" in codigos
    assert "III.02" in codigos


def test_formato_cabecalho_sem_propagacao_se_nao_ha_codigo():
    """Página sem cabeçalho e sem código III.NN não é processada por engano."""
    row_sem_codigo = ["Texto qualquer", "sem codigo", "dados", "x", "y", "z", "w"]
    rt = _fazer_relatorio([
        [[HEADER_2023, ROW_III01]],
        [[row_sem_codigo]],
    ])
    resultado = _parse_formato_cabecalho(rt)
    assert resultado is not None
    assert len(resultado) == 1  # apenas III.01 da página 1
