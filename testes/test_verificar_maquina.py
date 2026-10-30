"""Testes do verificador da máquina (ferramentas/verificar_maquina.py). Dono: Léo."""
import pytest

from ferramentas import verificar_maquina as vm


def test_candidatos_cobrem_1_metade_e_o_topo():
    assert vm.candidatos_de_threads(16) == [1, 8, 14, 15, 16]     # PC do torneio
    assert vm.candidatos_de_threads(12) == [1, 6, 10, 11, 12]
    assert vm.candidatos_de_threads(1) == [1]


def test_escolhe_o_maximo_quando_mais_threads_ajudam_mas_deixa_uma_livre():
    medidas = {1: 1.0, 8: 7.0, 14: 10.0, 15: 10.5, 16: 10.6}
    assert vm.escolher_threads(medidas, 16) == 15


def test_nao_sobe_quando_mais_threads_deixam_mais_lento():
    """O que aconteceu neste notebook: 6 threads mais rápido que 10, 11 e 12."""
    medidas = {1: 0.79, 6: 2.65, 10: 1.79, 11: 1.82, 12: 1.80}
    assert vm.escolher_threads(medidas, 12) == 6


def test_ganho_pequeno_demais_nao_justifica_mais_threads():
    medidas = {1: 1.0, 8: 8.0, 14: 8.1, 15: 8.15, 16: 8.2}
    assert vm.escolher_threads(medidas, 16) == 8


def test_maquina_de_uma_thread():
    assert vm.escolher_threads({1: 1.0}, 1) == 1


def test_verificar_completo_com_medidas_de_mentira(monkeypatch):
    """Roda o verificador inteiro (Stockfish real se houver), trocando só as medidas demoradas."""
    import partida
    if partida._achar_stockfish() is None:
        pytest.skip("Stockfish não instalado")
    monkeypatch.setattr(vm, "medir_nos_por_segundo", lambda caminho, threads, **k: 1e6 * min(threads, 4))
    from testes import torneio
    monkeypatch.setattr(torneio, "medir_estouro", lambda **k: {"pior_estouro_ms": 7.0})
    tela = []
    relatorio, resultado = vm.verificar(rapido=True, saida=tela.append, pausa_s=0)
    assert relatorio.falhas == []
    assert resultado["threads"] >= 1 and resultado["hash_mb"] >= 16
    assert any("CAPABLANCA_THREADS=" in linha for linha in tela)
    assert any("TUDO CERTO" in linha for linha in tela)


def test_sem_stockfish_aponta_a_falha(monkeypatch):
    import partida
    monkeypatch.setattr(partida, "_achar_stockfish", lambda: None)
    tela = []
    relatorio, resultado = vm.verificar(rapido=True, saida=tela.append, pausa_s=0)
    assert resultado is None
    assert any("Stockfish não encontrado" in f for f in relatorio.falhas)
