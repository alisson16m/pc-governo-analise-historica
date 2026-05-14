"""Heurísticas para identificar metadados (município, órgão, ano, auditor, relator)."""
from __future__ import annotations

import re
from typing import Optional

from .extract_text import RelatorioTexto

# Lista parcial dos 102 municípios de AL — completar conforme necessário.
# Para o piloto, casamento por substring case-insensitive já cobre a maioria.
MUNICIPIOS_AL: tuple[str, ...] = (
    "Maceió", "Arapiraca", "Palmeira dos Índios", "Rio Largo", "Penedo",
    "União dos Palmares", "São Miguel dos Campos", "Santana do Ipanema",
    "Delmiro Gouveia", "Coruripe", "Marechal Deodoro", "Campo Alegre",
    "Pilar", "Atalaia", "Murici", "Viçosa", "Cajueiro", "Capela", "Quebrangulo",
    "São Luís do Quitunde", "Porto Calvo", "Maragogi", "Japaratinga",
    "Joaquim Gomes", "Matriz de Camaragibe", "Passo de Camaragibe",
    "São José da Laje", "Branquinha", "Ibateguara", "Pindoba",
    "Estrela de Alagoas", "Mar Vermelho", "Igaci", "Coité do Nóia",
    "Craíbas", "Lagoa da Canoa", "Junqueiro", "Limoeiro de Anadia",
    "Taquarana", "Tanque d'Arca", "Belém", "Anadia", "Boca da Mata",
    "Roteiro", "Jequiá da Praia", "Barra de Santo Antônio",
    "Barra de São Miguel", "Paripueira", "Messias", "Coqueiro Seco",
    "Santa Luzia do Norte", "Satuba", "Flexeiras", "Colônia Leopoldina",
    "Novo Lino", "Jundiá", "São José da Tapera", "Olho d'Água das Flores",
    "Pão de Açúcar", "Piranhas", "Olho d'Água do Casado", "Água Branca",
    "Mata Grande", "Inhapi", "Canapi", "Carneiros", "Senador Rui Palmeira",
    "Maravilha", "Ouro Branco", "Poço das Trincheiras", "Dois Riachos",
    "Cacimbinhas", "Minador do Negrão", "Olivença", "Belo Monte",
    "Monteirópolis", "Palestina", "Jacaré dos Homens", "Major Isidoro",
    "Olho d'Água Grande", "Feira Grande", "Girau do Ponciano",
    "Traipu", "Campo Grande", "Igreja Nova", "Piaçabuçu", "São Brás",
    "Feliz Deserto", "Porto Real do Colégio", "São Sebastião",
    "Teotônio Vilela", "Arapiraca", "Maribondo", "Tanque d'Arca",
    "Chã Preta", "Paulo Jacinto", "Pindoba", "Mar Vermelho",
)


_RE_ANO = re.compile(r"\bExerc[ií]cio(?:\s+financeiro)?(?:\s+de)?[:\s]+(20\d{2})\b", re.IGNORECASE)
_RE_ANO_ALT = re.compile(r"\b(20\d{2})\b")
_RE_AUDITOR = re.compile(
    r"(?:Auditor(?:a)?|Analista de Controle Externo)[:\s]+([A-ZÁÉÍÓÚÂÊÔÃÕÇ][\wÀ-ÿ\s\.]{5,80})",
    re.IGNORECASE,
)
_RE_RELATOR = re.compile(
    r"Relator[:\s]+(?:Conselheiro[a]?\s+)?([A-ZÁÉÍÓÚÂÊÔÃÕÇ][\wÀ-ÿ\s\.]{5,80})",
    re.IGNORECASE,
)
_RE_GESTOR = re.compile(
    r"(?:Gestor(?:a)?|Respons[áa]vel)[:\s]+([A-ZÁÉÍÓÚÂÊÔÃÕÇ][\wÀ-ÿ\s\.]{5,80})",
    re.IGNORECASE,
)


def detectar_municipio(texto: str) -> Optional[str]:
    matches: list[tuple[int, str]] = []
    for m in MUNICIPIOS_AL:
        idx = texto.lower().find(m.lower())
        if idx >= 0:
            matches.append((idx, m))
    if not matches:
        return None
    matches.sort()
    return matches[0][1]


def detectar_ano(texto: str) -> Optional[int]:
    m = _RE_ANO.search(texto)
    if m:
        return int(m.group(1))
    m = _RE_ANO_ALT.search(texto[:2000])
    if m:
        return int(m.group(1))
    return None


def _primeiro(rx: re.Pattern[str], texto: str) -> Optional[str]:
    m = rx.search(texto)
    if not m:
        return None
    return _limpar(m.group(1))


def _limpar(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip(" .;:,")


def metadados(texto: RelatorioTexto, ano_pasta: Optional[int]) -> dict:
    cab = texto.texto_completo[:15000]
    fim = texto.texto_completo[-5000:]
    return {
        "municipio": detectar_municipio(cab),
        "ano_exercicio": detectar_ano(cab) or ano_pasta or 0,
        "orgao": _detectar_orgao(cab),
        "gestor": _primeiro(_RE_GESTOR, cab),
        "auditor": _primeiro(_RE_AUDITOR, fim) or _primeiro(_RE_AUDITOR, cab),
        "relator": _primeiro(_RE_RELATOR, cab),
    }


def _detectar_orgao(texto: str) -> str:
    # Heurística: procurar "Prefeitura Municipal de X", "Câmara Municipal de X",
    # "Secretaria de Estado de X", "Governo do Estado de Alagoas".
    rx = re.compile(
        r"(Prefeitura Municipal de [A-ZÁÉÍÓÚÂÊÔÃÕÇ][\wÀ-ÿ\s]+|"
        r"C[âa]mara Municipal de [A-ZÁÉÍÓÚÂÊÔÃÕÇ][\wÀ-ÿ\s]+|"
        r"Secretaria de Estado [A-ZÁÉÍÓÚÂÊÔÃÕÇ][\wÀ-ÿ\s]+|"
        r"Governo do Estado de Alagoas)",
        re.IGNORECASE,
    )
    m = rx.search(texto)
    if m:
        return _limpar(m.group(1))
    return "Não identificado"
