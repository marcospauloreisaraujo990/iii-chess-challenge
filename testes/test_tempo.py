"""Testes de tempo.py. Marcos Paulo implementa; Léo ajuda a calibrar."""
import math

import chess
import pytest

import tempo

ATRASO = 5.0


# ---------- calcular_tempo ----------

@pytest.mark.parametrize("restante", [0.01, 0.5, 2, 5, 6, 10, 30, 60, 300, 900, 1500])
@pytest.mark.parametrize("incremento", [0, 10])
@pytest.mark.parametrize("lance", [1, 20, 60, 150])
def test_nunca_pede_mais_do_que_pode_gastar(restante, incremento, lance):
    """Com poucos segundos no relógio, o tempo máximo fica abaixo do restante."""
    alvo, maximo = tempo.calcular_tempo(restante, incremento, lance, ATRASO)
    assert 0 < alvo <= maximo
    if maximo == tempo.TEMPO_MINIMO_S:
        return   # relógio no limite: lance mais rápido possível (o partida.py ainda corta para depth=1)
    # Sobra tempo para anunciar, mover, apertar o relógio e a reserva.
    assert maximo + ATRASO + tempo.RESERVA_MINIMA_S <= restante


def _lances_ate_estourar(perfil, atraso, usar_maximo, limite=400):
    """Simula a partida inteira gastando o alvo (ou o máximo) + o atraso da mesa a cada lance.

    O incremento só entra DEPOIS de apertar o relógio, então conferimos antes de somar.
    """
    restante, incremento = tempo.PERFIS[perfil]
    for lance in range(1, limite + 1):
        alvo, maximo = tempo.calcular_tempo(restante, incremento, lance, atraso)
        restante -= (maximo if usar_maximo else alvo) + atraso
        if restante <= 0:
            return lance
        restante += incremento
    return limite


def _limite_fisico(perfil, atraso):
    """Lances que a mesa aguenta pensando ZERO: sem incremento, o atraso sozinho zera o relógio."""
    inicio, incremento = tempo.PERFIS[perfil]
    return math.inf if incremento >= atraso else inicio / (atraso - incremento)


@pytest.mark.parametrize("atraso", [2.0, 5.0])
def test_com_incremento_nunca_estoura_nem_no_pior_caso(atraso):
    """15+10 gastando sempre o MÁXIMO: 400 lances e o relógio não zera."""
    assert _lances_ate_estourar("15+10", atraso, usar_maximo=True) == 400


@pytest.mark.parametrize("perfil", ["25+0", "armageddon_brancas", "armageddon_pretas"])
@pytest.mark.parametrize("atraso", [2.0, 5.0])
def test_sem_incremento_aguenta_partida_longa(perfil, atraso):
    """Sem incremento, jogando no alvo, chegamos a 80 lances ou quase ao limite físico da mesa.

    Pior caso (sempre o máximo): ainda passa de 60 lances ou de 75% do limite físico.
    """
    fisico = _limite_fisico(perfil, atraso)
    assert _lances_ate_estourar(perfil, atraso, usar_maximo=False) >= min(80, 0.9 * fisico)
    assert _lances_ate_estourar(perfil, atraso, usar_maximo=True) >= min(60, 0.75 * fisico)


def test_gastando_o_alvo_sobra_relogio_para_o_fim():
    """No 25+0, jogando no alvo, depois de 40 lances ainda sobra tempo de verdade."""
    restante, incremento = tempo.PERFIS["25+0"]
    for lance in range(1, 41):
        alvo, _ = tempo.calcular_tempo(restante, incremento, lance, ATRASO)
        restante -= alvo + ATRASO
    assert restante > 60


def test_incremento_aumenta_o_alvo():
    sem, _ = tempo.calcular_tempo(300, 0, 20, ATRASO)
    com, _ = tempo.calcular_tempo(300, 10, 20, ATRASO)
    assert com > sem


def test_atraso_humano_diminui_o_alvo():
    rapido, _ = tempo.calcular_tempo(900, 10, 20, 1)
    lento, _ = tempo.calcular_tempo(900, 10, 20, 8)
    assert lento < rapido


def test_maximo_nunca_e_fatia_grande_do_relogio():
    for restante in (60, 300, 900, 1500):
        _, maximo = tempo.calcular_tempo(restante, 10, 1, ATRASO)
        assert maximo <= restante * tempo.FRACAO_MAXIMA_DO_RELOGIO


# ---------- deve_parar ----------

@pytest.mark.parametrize("mudou,caiu,estaveis", [(False, False, 9), (True, False, 0), (False, True, 0), (True, True, 0)])
def test_para_no_maximo(mudou, caiu, estaveis):
    """Ao atingir o tempo máximo, deve_parar devolve True sempre."""
    assert tempo.deve_parar(10.0, 3.0, 10.0, estaveis, mudou, caiu) is True


def test_antes_do_alvo_continua():
    assert tempo.deve_parar(1.0, 3.0, 10.0, 9, False, False) is False


def test_depois_do_alvo_com_lance_firme_para():
    assert tempo.deve_parar(4.0, 3.0, 10.0, tempo.PROFUNDIDADES_ESTAVEIS, False, False) is True


def test_depois_do_alvo_com_lance_instavel_continua():
    assert tempo.deve_parar(4.0, 3.0, 10.0, 0, False, False) is False
    assert tempo.deve_parar(4.0, 3.0, 10.0, 9, True, False) is False
    assert tempo.deve_parar(4.0, 3.0, 10.0, 9, False, True) is False


# ---------- atalho_tempo_zero ----------

def test_atalho_lance_unico():
    board = chess.Board("R6k/8/5K2/8/8/8/8/8 b - - 0 1")   # xeque da torre: só sobra h8h7
    legais = list(board.legal_moves)
    assert len(legais) == 1
    assert tempo.atalho_tempo_zero(board, None, False) == legais[0]


def test_atalho_lance_de_book():
    board = chess.Board()
    lance = chess.Move.from_uci("e2e4")
    assert tempo.atalho_tempo_zero(board, lance, False) == lance


def test_atalho_ignora_book_ilegal():
    board = chess.Board()
    assert tempo.atalho_tempo_zero(board, chess.Move.from_uci("e2e5"), False) is None


def test_atalho_tablebase_deixa_o_stockfish_decidir():
    board = chess.Board("8/8/8/4k3/8/8/3QK3/8 w - - 0 1")
    assert tempo.atalho_tempo_zero(board, None, True) is None


# ---------- modo_economia ----------

def test_economia_em_final_calmo():
    assert tempo.modo_economia([10, -5, 0, 20] * 3, 1200) is True


def test_sem_economia_com_muito_material_ou_avaliacao_alta_ou_poucos_lances():
    assert tempo.modo_economia([0] * 12, 7800) is False
    assert tempo.modo_economia([0] * 11 + [200], 1200) is False
    assert tempo.modo_economia([0] * 3, 1200) is False


def test_economia_ignora_mate_e_valores_estranhos():
    assert tempo.modo_economia([0] * 11 + ["#3"], 1200) is False
    assert tempo.modo_economia([0] * 11 + [None], 1200) is False
    assert tempo.modo_economia([0] * 11 + [True], 1200) is False


def test_material_em_centipawns():
    assert tempo.material_em_centipawns(chess.Board()) == 2 * (8 * 100 + 4 * 300 + 2 * 500 + 900)


# ---------- sincronizar ----------

def test_sincronizar_aceita_formato_mm_ss():
    """'t 12:34' vira 754 segundos."""
    assert tempo.sincronizar("t 12:34") == 754
    assert tempo.sincronizar("T 0:09") == 9
    assert tempo.sincronizar("  t  25:00 ") == 1500
    assert tempo.sincronizar("t 1:02:03") == 3723
    assert tempo.sincronizar("t 0:00") == 0   # o partida.py é quem recusa zero


@pytest.mark.parametrize("texto", ["", "t", "t 12", "t 12:3", "t 12:60", "t aa:bb", "12:34", "t -1:00", "t 1:60:00", "t １２:３４", None])
def test_sincronizar_recusa_formato_errado(texto):
    with pytest.raises(ValueError):
        tempo.sincronizar(texto)
