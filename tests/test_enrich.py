"""Testes das heurísticas de metadados (enrich.py)."""
from src.enrich import MUNICIPIOS_AL, detectar_municipio

# Municípios que estavam ausentes da lista original
_RECEM_INCLUIDOS = (
    "Batalha",
    "Jacuípe",
    "Jaramataia",
    "Pariconha",
    "Porto de Pedras",
    "Santana do Mundaú",
    "São Miguel dos Milagres",
)


def test_lista_cobre_os_102_municipios_de_alagoas():
    assert len(set(MUNICIPIOS_AL)) == 102


def test_detecta_municipios_recem_incluidos():
    for m in _RECEM_INCLUIDOS:
        texto = f"PREFEITURA MUNICIPAL DE {m.upper()} — Exercício de 2023"
        assert detectar_municipio(texto) == m, f"{m} não detectado"


def test_nome_mais_especifico_prevalece():
    """'São Miguel dos Milagres' não pode ser confundido com 'São Miguel dos Campos'."""
    texto = "Prefeitura Municipal de São Miguel dos Milagres"
    assert detectar_municipio(texto) == "São Miguel dos Milagres"
