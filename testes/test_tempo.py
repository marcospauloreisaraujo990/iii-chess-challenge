"""Testes de tempo.py. Marcos Paulo implementa; Léo ajuda a calibrar."""
import pytest


@pytest.mark.skip(reason="implementar quando calcular_tempo existir")
def test_nunca_pede_mais_do_que_pode_gastar():
    """Com poucos segundos no relógio, o tempo máximo fica abaixo do restante."""


@pytest.mark.skip(reason="implementar quando deve_parar existir")
def test_para_no_maximo():
    """Ao atingir o tempo máximo, deve_parar devolve True sempre."""


@pytest.mark.skip(reason="implementar quando sincronizar existir")
def test_sincronizar_aceita_formato_mm_ss():
    """'t 12:34' vira 754 segundos."""
