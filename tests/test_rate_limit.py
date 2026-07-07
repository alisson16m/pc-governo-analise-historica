"""Testes do controle de cota do Gemini (rate_limit.py)."""
import threading

import pytest
from filelock import FileLock

from src import rate_limit


@pytest.fixture()
def estado_isolado(tmp_path, monkeypatch):
    """Redireciona o arquivo de estado para um diretório temporário."""
    state = tmp_path / "gemini_state.json"
    monkeypatch.setattr(rate_limit, "STATE", state)
    monkeypatch.setattr(rate_limit, "_LOCK", FileLock(str(state) + ".lock"))
    return state


def test_modelo_gemini_padrao_unificado(monkeypatch):
    """Sem GEMINI_MODEL no .env, todos os módulos devem usar o mesmo modelo."""
    monkeypatch.delenv("GEMINI_MODEL", raising=False)
    assert rate_limit.modelo_gemini() == rate_limit.MODELO_PADRAO


def test_modelo_gemini_respeita_env(monkeypatch):
    monkeypatch.setenv("GEMINI_MODEL", "gemini-teste")
    assert rate_limit.modelo_gemini() == "gemini-teste"


def test_reservar_nao_excede_cota_diaria_com_threads(estado_isolado, monkeypatch):
    """40 threads disputando 20 slots: exatamente 20 passam, 20 recebem erro."""
    monkeypatch.setenv("GEMINI_RPM", "600000")  # intervalo desprezível
    monkeypatch.setenv("GEMINI_RPD", "20")

    ok: list[int] = []
    negados: list[int] = []
    barreira = threading.Barrier(8)

    def worker(n: int) -> None:
        for _ in range(n):
            try:
                rate_limit.reservar()
                ok.append(1)
            except RuntimeError:
                negados.append(1)

    threads = [threading.Thread(target=lambda: (barreira.wait(), worker(5))) for _ in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert len(ok) == 20
    assert len(negados) == 20


def test_reservar_espaca_requisicoes(estado_isolado, monkeypatch):
    """Com RPM=60, a segunda reserva deve esperar ~1 segundo."""
    monkeypatch.setenv("GEMINI_RPM", "60")
    monkeypatch.setenv("GEMINI_RPD", "100")

    espera1 = rate_limit.reservar()
    espera2 = rate_limit.reservar()

    assert espera1 == 0.0
    assert 0.5 <= espera2 <= 1.5


def test_reservar_respeita_esgotado(estado_isolado, monkeypatch):
    monkeypatch.setenv("GEMINI_RPM", "600000")
    monkeypatch.setenv("GEMINI_RPD", "100")
    rate_limit.reservar()
    rate_limit.marcar_esgotado()
    with pytest.raises(RuntimeError):
        rate_limit.reservar()
