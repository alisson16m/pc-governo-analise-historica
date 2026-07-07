from __future__ import annotations

from datetime import date
from decimal import Decimal
from enum import Enum
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


class Situacao(str, Enum):
    SANADO_TOTAL = "sanado_total"
    SANADO_PARCIAL = "sanado_parcial"
    AFASTADO = "afastado"
    MANTIDO = "mantido"
    NAO_CONSTA = "nao_consta"


class Achado(BaseModel):
    model_config = ConfigDict(extra="ignore")

    codigo: str = Field(description="Código no padrão III.NN, ex: III.01")
    tipo: str = Field(description="Categoria do achado")
    secao: str = Field(description="Seção do relatório onde o achado aparece")

    @field_validator("secao", mode="before")
    @classmethod
    def _title_case_secao(cls, v: object) -> object:
        if isinstance(v, str) and v:
            return v.strip().title()
        return v
    base_normativa: Optional[str] = None
    descricao: str
    houve_defesa: bool = False
    situacao: Optional[Situacao] = None
    recomendacao: Optional[str] = None
    determinacao: Optional[str] = None
    valor_financeiro: Optional[Decimal] = None
    defesa_gestor: Optional[str] = None
    analise_tecnica: Optional[str] = None
    resumo_defesa: Optional[str] = None
    resumo_analise: Optional[str] = None


class ParecerPrevio(BaseModel):
    """Reservado para fase futura (parecer prévio do relator)."""

    model_config = ConfigDict(extra="ignore")

    relator: Optional[str] = None
    opiniao_final: Optional[str] = None
    recomendacoes: list[str] = Field(default_factory=list)
    determinacoes: list[str] = Field(default_factory=list)


class Relatorio(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: str = Field(description="SHA-256 do PDF")
    arquivo: str
    ano_exercicio: int
    municipio: Optional[str] = None
    gestor: Optional[str] = None
    auditor: Optional[str] = None
    relator: Optional[str] = None
    numero_processo: Optional[str] = None
    opiniao_auditoria: Optional[str] = None
    data_publicacao: Optional[date] = None
    fonte_extracao: str = Field(description="'parser_2024' | 'gemini_legacy'")
    achados: list[Achado] = Field(default_factory=list)
    parecer_previo: Optional[ParecerPrevio] = None


# SANADO_PARCIAL deve ser checado antes de SANADO_TOTAL (ambos contêm "sanado")
_SITUACAO_ORDEM: list[tuple[Situacao, tuple[str, ...]]] = [
    (Situacao.SANADO_PARCIAL, ("sanado parcialmente", "parcialmente sanado", "sanado parcial")),
    (Situacao.SANADO_TOTAL,   ("sanado totalmente", "sanado total", "totalmente sanado", "sanado")),
    (Situacao.AFASTADO,       ("afastado", "afastada")),
    (Situacao.MANTIDO,        ("mantido", "mantida")),
]

SITUACAO_KEYWORDS: dict[Situacao, tuple[str, ...]] = {sit: kws for sit, kws in _SITUACAO_ORDEM}


def normalizar_situacao(texto: Optional[str]) -> Optional[Situacao]:
    if not texto:
        return None
    import re as _re
    t = _re.sub(r"\s+", " ", texto).strip().lower()
    for sit, kws in _SITUACAO_ORDEM:
        if any(k in t for k in kws):
            return sit
    return Situacao.NAO_CONSTA
