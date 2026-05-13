"""Rate-limit local para respeitar a cota gratuita do Gemini."""
from __future__ import annotations

import json
import os
import time
from datetime import date
from pathlib import Path

STATE = Path("data/.gemini_state.json")


def _ler() -> dict:
    if not STATE.exists():
        return {"dia": "", "rpd": 0, "ultimo_request": 0.0, "esgotado": False}
    try:
        return json.loads(STATE.read_text(encoding="utf-8"))
    except Exception:
        return {"dia": "", "rpd": 0, "ultimo_request": 0.0, "esgotado": False}


def _escrever(d: dict) -> None:
    STATE.parent.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps(d), encoding="utf-8")


def aguardar() -> None:
    """Aguarda o intervalo mínimo entre requisições (RPM) e verifica a cota diária.

    Não incrementa o contador — chame marcar_sucesso() após a chamada bem-sucedida
    ou marcar_esgotado() ao receber um erro 429 da API.
    """
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


# Mantém compatibilidade com chamadas existentes
def aguardar_e_marcar() -> None:
    aguardar()
    marcar_sucesso()
