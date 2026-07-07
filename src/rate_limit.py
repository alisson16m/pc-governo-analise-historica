"""Rate-limit local para respeitar a cota gratuita do Gemini.

A reserva de slot é atômica: verificação de cota, espaçamento RPM e
incremento do contador acontecem dentro do mesmo lock de arquivo, o que
permite extração paralela (PCG_WORKERS > 1) sem estourar RPM/RPD.
"""
from __future__ import annotations

import functools
import json
import os
import time
from datetime import date
from pathlib import Path
from typing import Callable, TypeVar

from filelock import FileLock

STATE = Path("data/.gemini_state.json")
_LOCK = FileLock(str(STATE) + ".lock")

_ESTADO_PADRAO = {"dia": "", "rpd": 0, "ultimo_request": 0.0, "esgotado": False}

# Modelo usado por todos os módulos quando GEMINI_MODEL não está no .env
MODELO_PADRAO = "gemini-3.1-flash-lite"


def modelo_gemini() -> str:
    """Nome do modelo Gemini a usar (GEMINI_MODEL do .env ou o padrão)."""
    return os.getenv("GEMINI_MODEL", MODELO_PADRAO)


def _ler_bruto() -> dict:
    """Lê o estado SEM lock — chamar apenas dentro de `with _LOCK`."""
    if not STATE.exists():
        return dict(_ESTADO_PADRAO)
    try:
        return json.loads(STATE.read_text(encoding="utf-8"))
    except Exception:
        return dict(_ESTADO_PADRAO)


def _escrever_bruto(d: dict) -> None:
    """Grava o estado SEM lock — chamar apenas dentro de `with _LOCK`."""
    STATE.parent.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps(d), encoding="utf-8")


def reservar() -> float:
    """Reserva atomicamente um slot de requisição ao Gemini.

    Retorna quantos segundos o chamador deve aguardar antes de disparar a
    requisição (0.0 se pode disparar já). Levanta RuntimeError se a cota
    diária acabou. O contador RPD conta requisições reservadas.
    """
    rpm = int(os.getenv("GEMINI_RPM", "15"))
    rpd = int(os.getenv("GEMINI_RPD", "1000"))
    intervalo = 60.0 / max(rpm, 1)
    hoje = date.today().isoformat()

    with _LOCK:
        s = _ler_bruto()
        if s.get("dia") != hoje:
            s = {"dia": hoje, "rpd": 0, "ultimo_request": 0.0, "esgotado": False}

        if s.get("esgotado"):
            raise RuntimeError("Cota diária do Gemini esgotada (erro 429 recebido). Tente amanhã.")
        if int(s.get("rpd", 0)) >= rpd:
            raise RuntimeError(f"Cota diária do Gemini atingida ({rpd} req/dia). Tente amanhã.")

        agora = time.time()
        # Slot alvo: o próximo instante livre respeitando o intervalo RPM.
        alvo = max(agora, float(s.get("ultimo_request") or 0.0) + intervalo)
        s["ultimo_request"] = alvo
        s["rpd"] = int(s.get("rpd", 0)) + 1
        _escrever_bruto(s)

    return max(0.0, alvo - agora)


def marcar_esgotado() -> None:
    """Sinaliza que a cota diária foi esgotada (erro 429) para parar o processamento."""
    with _LOCK:
        s = _ler_bruto()
        s["esgotado"] = True
        _escrever_bruto(s)


def estado_atual() -> dict:
    """Retorna o contador RPD do dia atual e o limite configurado."""
    rpd_max = int(os.getenv("GEMINI_RPD", "1000"))
    hoje = date.today().isoformat()
    with _LOCK:
        s = _ler_bruto()
    rpd_usado = int(s.get("rpd", 0)) if s.get("dia") == hoje else 0
    return {"rpd_usado": rpd_usado, "rpd_max": rpd_max}


_F = TypeVar("_F", bound=Callable)


def com_rate_limit(func: _F) -> _F:
    """Decorator: reserva um slot (atômico) e aguarda o espaçamento antes da chamada."""
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        espera = reservar()
        if espera > 0:
            time.sleep(espera)
        return func(*args, **kwargs)
    return wrapper  # type: ignore[return-value]
