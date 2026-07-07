"""Testes do fluxo de revisão humana (review.py)."""
from src.review import _mesclar
from src.schema import Achado, Situacao


def _achado_com_contraditorio() -> Achado:
    return Achado(
        codigo="III.01",
        tipo="Irregularidade",
        secao="3. Gestão Fiscal",
        descricao="Descrição original do achado",
        houve_defesa=True,
        situacao=Situacao.MANTIDO,
        defesa_gestor="Texto integral da defesa do gestor",
        analise_tecnica="Texto integral da análise técnica",
        resumo_defesa="Resumo da defesa",
        resumo_analise="Resumo da análise",
    )


def test_mesclar_preserva_campos_do_contraditorio():
    """Editar um campo no CSV não pode apagar defesa_gestor/resumos do achado."""
    edicao = {"tipo": "Impropriedade", "houve_defesa": "true", "revisado": "true"}
    novo = _mesclar(_achado_com_contraditorio(), edicao)
    assert novo.tipo == "Impropriedade"
    assert novo.defesa_gestor == "Texto integral da defesa do gestor"
    assert novo.analise_tecnica == "Texto integral da análise técnica"
    assert novo.resumo_defesa == "Resumo da defesa"
    assert novo.resumo_analise == "Resumo da análise"


def test_mesclar_houve_defesa_vazio_mantem_valor_original():
    """Coluna houve_defesa vazia no CSV não pode virar False silenciosamente."""
    edicao = {"descricao": "Descrição corrigida", "houve_defesa": "", "revisado": "true"}
    novo = _mesclar(_achado_com_contraditorio(), edicao)
    assert novo.houve_defesa is True
    assert novo.descricao == "Descrição corrigida"


def test_mesclar_houve_defesa_false_explicito_e_aplicado():
    """Valor 'false' explícito no CSV deve ser aplicado normalmente."""
    edicao = {"houve_defesa": "false", "revisado": "true"}
    novo = _mesclar(_achado_com_contraditorio(), edicao)
    assert novo.houve_defesa is False
