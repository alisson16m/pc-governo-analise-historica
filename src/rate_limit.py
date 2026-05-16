"""Rate-limit local para respeitar a cota gratuita do Gemini."""
from __future__ import annotations

import json
import os
import time
from datetime import date
from pathlib import Path

from filelock import FileLock

STATE = Path("data/.gemini_state.json")
_LOCK = FileLock(str(STATE) + ".lock")

_ESTADO_PADRAO = {"dia": "", "rpd": 0, "ultimo_request": 0.0, "esgotado": False}


def _ler() -> dict:
    with _LOCK:
        if not STATE.exists():
            return dict(_ESTADO_PADRAO)
        try:
            return json.loads(STATE.read_text(encoding="utf-8"))
        except Exception:
            return dict(_ESTADO_PADRAO)


def _escrever(d: dict) -> None:
    with _LOCK:
        STATE.parent.mkdir(parents=True, exist_ok=True)
        STATE.write_text(json.dumps(d), encoding="utf-8")


def aguardar() -> None:
    """Aguarda o intervalo mínimo entre requisições (RPM) e verifica a cota diária."""
    rpm = int(os.getenv("GEMINI_RPM", "15"))
    rpd = int(os.getenv("GEMINI_RPD", "1000"))
    minimo_intervalo = 60.0 / max(rpm, 1)
    hoje = date.today().isoformat()

    s = _ler()
    if s.get("dia") != hoje:
        s = {"dia": hoje, "rpd": 0, "ultimo_request": 0.0, "esgotado": False}
        _escrever(s)

    if s.get("esgotado"):
        raise RuntimeError("Cota diária do Gemini esgotada (erro 429 recebido). Tente amanhã.")

    if s["rpd"] >= rpd:
        raise RuntimeError(f"Cota diária do Gemini atingida ({rpd} req/dia). Tente amanhã.")

    delta = time.time() - float(s.get("ultimo_request") or 0.0)
    if delta < minimo_intervalo:
        time.sleep(minimo_intervalo - delta)


def marcar_sucesso() -> None:
    """Incrementa o contador após uma chamada bem-sucedida."""
    s = _ler()
    hoje = date.today().isoformat()
    if s.get("dia") != hoje:
        s = {"dia": hoje, "rpd": 0, "ultimo_request": 0.0, "esgotado": False}
    s["ultimo_request"] = time.time()
    s["rpd"] = int(s.get("rpd", 0)) + 1
    _escrever(s)


def marcar_esgotado() -> None:
    """Sinaliza que a cota diária foi esgotada (erro 429) para parar o processamento."""
    s = _ler()
    s["esgotado"] = True
    _escrever(s)


def estado_atual() -> dict:
    """Retorna o contador RPD do dia atual e o limite configurado."""
    rpd_max = int(os.getenv("GEMINI_RPD", "1000"))
    s = _ler()
    hoje = date.today().isoformat()
    rpd_usado = int(s.get("rpd", 0)) if s.get("dia") == hoje else 0
    return {"rpd_usado": rpd_usado, "rpd_max": rpd_max}


# Mantém compatibilidade com chamadas existentes
def aguardar_e_marcar() -> None:
    aguardar()
    marcar_sucesso()


import functools
from typing import Callable, TypeVar

_F = TypeVar("_F", bound=Callable)


def com_rate_limit(func: _F) -> _F:
    """Decorator: aguarda rate-limit antes da chamada e marca sucesso ao terminar."""
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        aguardar()
        resultado = func(*args, **kwargs)
        marcar_sucesso()
        return resultado
    return wrapper  # type: ignore[return-value]
