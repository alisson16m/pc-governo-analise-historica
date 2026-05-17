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
