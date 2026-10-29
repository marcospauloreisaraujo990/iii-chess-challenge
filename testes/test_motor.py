"""Testes de abrir_motor e escolher_lance. Dono: Junio.

Parte dos testes usa o Stockfish de verdade (pasta stockfish/, fora do Git): se ele não
estiver na máquina, esses testes são pulados em vez de falhar.
"""
import glob
import os
import time

import chess
import pytest

import book
import partida
import tempo

_RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STOCKFISH = next((c for c in glob.glob(os.path.join(_RAIZ, "stockfish", "stockfish-*"))
                  if os.path.isfile(c) and os.access(c, os.X_OK) and not c.endswith((".md", ".txt"))), None)
precisa_stockfish = pytest.mark.skipif(STOCKFISH is None, reason="Stockfish não instalado em stockfish/")

# ATENÇÃO: estes números (relógio e tempos de 0,2 a 0,5 s) são SÓ de teste. Não copiar para
# o código: os valores reais de tempo saem dos testes do Léo (regra 4 do CLAUDE.md).
RELOGIO = {"restante_s": 900, "incremento_s": 10, "atraso_humano_s": 5}


@pytest.fixture(autouse=True)
def _tempo_py_como_esqueleto(monkeypatch):
    """Estes testes são do partida.py, não da gestão de tempo: o tempo do lance vem do
    `tempo_provisorio_s` de cada teste. Sem isto, com o tempo.py pronto, cada teste faria o
    Stockfish pensar o tempo de uma partida de verdade (~25 s). Quem quiser testar a ligação
    com o tempo.py faz o próprio monkeypatch de calcular_tempo, que substitui este."""
    def esqueleto(*a):
        raise NotImplementedError
    monkeypatch.setattr(tempo, "calcular_tempo", esqueleto)


# ---------- abrir_motor (motor falso, sem processo) ----------

class MotorFalso:
    def __init__(self):
        self.opcoes = None
        self.fechado = False

    def configure(self, opcoes):
        self.opcoes = opcoes

    def quit(self):
        self.fechado = True


def test_abrir_motor_configura_threads_hash_e_limita_tablebase_a_5(monkeypatch, tmp_path):
    falso = MotorFalso()
    monkeypatch.setattr(partida.chess.engine.SimpleEngine, "popen_uci", lambda caminho: falso)
    motor = partida.abrir_motor("qualquer", 2, 64, str(tmp_path))
    assert motor is falso
    assert falso.opcoes == {"Threads": 2, "Hash": 64, "SyzygyPath": str(tmp_path), "SyzygyProbeLimit": 5}


def test_abrir_motor_sem_pasta_de_tablebase_nao_configura_syzygy_e_avisa(monkeypatch, capsys):
    falso = MotorFalso()
    monkeypatch.setattr(partida.chess.engine.SimpleEngine, "popen_uci", lambda caminho: falso)
    partida.abrir_motor("qualquer", 1, 16, "/pasta/que/nao/existe")
    # o limite de 5 peças vai sempre, mesmo sem pasta de tablebases
    assert falso.opcoes == {"Threads": 1, "Hash": 16, "SyzygyProbeLimit": 5}
    assert "não existe" in capsys.readouterr().err


def test_abrir_motor_avisa_de_tablebase_com_6_pecas(monkeypatch, tmp_path, capsys):
    (tmp_path / "KQRRvKR.rtbw").write_bytes(b"")  # 6 peças: proibido
    (tmp_path / "KQRvKR.rtbw").write_bytes(b"")   # 5 peças: ok
    falso = MotorFalso()
    monkeypatch.setattr(partida.chess.engine.SimpleEngine, "popen_uci", lambda caminho: falso)
    partida.abrir_motor("qualquer", 1, 16, str(tmp_path))
    assert "mais de 5 peças (1)" in capsys.readouterr().err
    assert falso.opcoes["SyzygyProbeLimit"] == 5


def test_contagem_de_pecas_do_arquivo_syzygy():
    assert partida._pecas_no_arquivo_syzygy("KQvK.rtbw") == 3
    assert partida._pecas_no_arquivo_syzygy("KQvKR.rtbz") == 4
    assert partida._pecas_no_arquivo_syzygy("KQRvKR.rtbw") == 5   # limite permitido
    assert partida._pecas_no_arquivo_syzygy("KQRRvKR.rtbw") == 6   # proibido


def test_abrir_motor_fecha_o_processo_se_a_configuracao_falhar(monkeypatch):
    falso = MotorFalso()

    def quebra(opcoes):
        raise RuntimeError("opção inválida")
    falso.configure = quebra
    monkeypatch.setattr(partida.chess.engine.SimpleEngine, "popen_uci", lambda caminho: falso)
    with pytest.raises(RuntimeError):
        partida.abrir_motor("qualquer", 1, 16)
    assert falso.fechado is True


# ---------- escolher_lance: book ----------

def test_book_e_usado_antes_do_ply_10(monkeypatch):
    lance = chess.Move.from_uci("e2e4")
    monkeypatch.setattr(book, "lance_do_book", lambda board, caminho: lance)
    escolhido, info = partida.escolher_lance(chess.Board(), None, "15+10", RELOGIO, caminho_book="x.bin")
    assert escolhido == lance
    assert info["book"] is True and info["profundidade"] == 0


def test_book_nunca_e_consultado_depois_do_ply_10(monkeypatch):
    def proibido(board, caminho):
        raise AssertionError("o book foi consultado depois do ply 10!")
    monkeypatch.setattr(book, "lance_do_book", proibido)
    board = chess.Board()
    for lance in ("e2e4", "e7e5", "g1f3", "b8c6", "f1c4", "g8f6", "d2d3", "f8c5", "c2c3", "d7d6"):
        board.push_uci(lance)
    assert board.ply() == 10
    if STOCKFISH is None:
        pytest.skip("Stockfish não instalado")
    motor = partida.abrir_motor(STOCKFISH, 1, 16)
    try:
        partida.escolher_lance(board, motor, "15+10", RELOGIO, caminho_book="x.bin", tempo_provisorio_s=0.2)
    finally:
        motor.quit()


def test_book_quebrado_nao_derruba(monkeypatch):
    def quebra(board, caminho):
        raise OSError("arquivo corrompido")
    monkeypatch.setattr(book, "lance_do_book", quebra)
    if STOCKFISH is None:
        pytest.skip("Stockfish não instalado")
    motor = partida.abrir_motor(STOCKFISH, 1, 16)
    try:
        lance, info = partida.escolher_lance(chess.Board(), motor, "15+10", RELOGIO,
                                              caminho_book="x.bin", tempo_provisorio_s=0.2)
    finally:
        motor.quit()
    assert lance in chess.Board().legal_moves
    assert info["book"] is False


def test_lance_de_book_ilegal_e_ignorado(monkeypatch):
    monkeypatch.setattr(book, "lance_do_book", lambda board, caminho: chess.Move.from_uci("e2e5"))
    if STOCKFISH is None:
        pytest.skip("Stockfish não instalado")
    motor = partida.abrir_motor(STOCKFISH, 1, 16)
    try:
        lance, info = partida.escolher_lance(chess.Board(), motor, "15+10", RELOGIO,
                                              caminho_book="x.bin", tempo_provisorio_s=0.2)
    finally:
        motor.quit()
    assert lance in chess.Board().legal_moves and info["book"] is False


# ---------- escolher_lance: tempo ----------

def test_sem_tempo_py_e_sem_tempo_provisorio_da_erro_claro():
    with pytest.raises(RuntimeError, match="tempo_provisorio_s"):
        partida.escolher_lance(chess.Board(), None, "15+10", RELOGIO)


def test_partida_terminada_da_erro_claro():
    board = chess.Board()
    for lance in ("f2f3", "e7e5", "g2g4", "d8h4"):
        board.push_uci(lance)
    with pytest.raises(ValueError):
        partida.escolher_lance(board, None, "15+10", RELOGIO, tempo_provisorio_s=0.1)


# ---------- escolher_lance: Stockfish de verdade ----------

@pytest.fixture
def motor():
    if STOCKFISH is None:
        pytest.skip("Stockfish não instalado em stockfish/")
    m = partida.abrir_motor(STOCKFISH, 1, 16)
    yield m
    m.quit()


@precisa_stockfish
def test_devolve_lance_legal_e_info_para_o_log(motor):
    board = chess.Board()
    lance, info = partida.escolher_lance(board, motor, "15+10", RELOGIO, tempo_provisorio_s=0.3)
    assert lance in board.legal_moves
    assert set(info) == {"book", "profundidade", "nos", "avaliacao", "pv", "tempo_s", "motor_caiu"}
    assert info["motor_caiu"] is False
    assert info["profundidade"] > 0 and info["nos"] > 0
    assert info["pv"][0] == lance


@precisa_stockfish
def test_info_entra_direto_no_log(motor, tmp_path):
    import log
    board = chess.Board()
    lance, info = partida.escolher_lance(board, motor, "15+10", RELOGIO, tempo_provisorio_s=0.3)
    arq = log.abrir_log(str(tmp_path / "p.txt"))
    ok = log.registrar_lance(arq, 1, "brancas", lance, info["profundidade"], info["nos"],
                             info["avaliacao"], info["pv"], info["tempo_s"], book=info["book"])
    arq.close()
    assert ok is True


@precisa_stockfish
def test_acha_mate_em_um(motor):
    board = chess.Board("6k1/5ppp/8/8/8/8/8/R3K3 w - - 0 1")  # Ra8#
    lance, info = partida.escolher_lance(board, motor, "15+10", RELOGIO, tempo_provisorio_s=0.5)
    assert lance == chess.Move.from_uci("a1a8")
    assert info["avaliacao"] == "#1"


@precisa_stockfish
def test_limite_duro_do_motor_vale_mesmo_se_deve_parar_nunca_manda_parar(motor, monkeypatch):
    monkeypatch.setattr(tempo, "calcular_tempo", lambda *a: (0.2, 0.4))
    monkeypatch.setattr(tempo, "deve_parar", lambda *a: False)
    antes = time.monotonic()
    lance, info = partida.escolher_lance(chess.Board(), motor, "15+10", RELOGIO)
    assert time.monotonic() - antes < 1.5   # o motor parou sozinho perto de 0,4 s
    assert lance in chess.Board().legal_moves


@precisa_stockfish
def test_deve_parar_true_encerra_antes_do_maximo(motor, monkeypatch):
    chamadas = []
    monkeypatch.setattr(tempo, "calcular_tempo", lambda *a: (1.0, 5.0))

    def parar(*args):
        chamadas.append(args)
        return True
    monkeypatch.setattr(tempo, "deve_parar", parar)
    antes = time.monotonic()
    lance, info = partida.escolher_lance(chess.Board(), motor, "15+10", RELOGIO)
    assert time.monotonic() - antes < 2.0   # bem antes do máximo de 5 s
    assert len(chamadas) == 1               # parou na primeira profundidade


@precisa_stockfish
def test_deve_parar_recebe_os_argumentos_certos(motor, monkeypatch):
    monkeypatch.setattr(tempo, "calcular_tempo", lambda *a: (0.3, 0.6))
    vistos = []

    def espiao(decorrido, alvo, maximo, estaveis, mudou, caiu):
        vistos.append((decorrido, alvo, maximo, estaveis, mudou, caiu))
        return decorrido >= alvo
    monkeypatch.setattr(tempo, "deve_parar", espiao)
    partida.escolher_lance(chess.Board(), motor, "15+10", RELOGIO)
    assert vistos
    assert all(v[1] == 0.3 and v[2] == 0.6 for v in vistos)
    assert all(isinstance(v[3], int) and isinstance(v[4], bool) and isinstance(v[5], bool) for v in vistos)
    decorridos = [v[0] for v in vistos]
    assert decorridos == sorted(decorridos)


@precisa_stockfish
def test_deve_parar_com_bug_nao_derruba_e_respeita_o_alvo(motor, monkeypatch):
    monkeypatch.setattr(tempo, "calcular_tempo", lambda *a: (0.2, 2.0))

    def quebra(*args):
        raise TypeError("bug do tempo.py")
    monkeypatch.setattr(tempo, "deve_parar", quebra)
    antes = time.monotonic()
    lance, _ = partida.escolher_lance(chess.Board(), motor, "15+10", RELOGIO)
    assert time.monotonic() - antes < 1.5   # parou perto do alvo (0,2 s), não do máximo (2 s)
    assert lance in chess.Board().legal_moves


@precisa_stockfish
def test_calcular_tempo_recebe_os_dados_do_relogio(motor, monkeypatch):
    recebido = []

    def espiao(restante, incremento, numero, atraso):
        recebido.append((restante, incremento, numero, atraso))
        return (0.2, 0.3)
    monkeypatch.setattr(tempo, "calcular_tempo", espiao)
    partida.escolher_lance(chess.Board(), motor, "15+10", RELOGIO)
    assert recebido == [(900, 10, 1, 5)]


def test_atalho_do_marcos_e_respeitado(monkeypatch):
    lance = chess.Move.from_uci("g1f3")
    monkeypatch.setattr(tempo, "atalho_tempo_zero", lambda board, lb, tb: lance)
    escolhido, info = partida.escolher_lance(chess.Board(), None, "15+10", RELOGIO)
    assert escolhido == lance and info["tempo_s"] < 0.1


# ====================== correções da rodada de revisão ======================

# ---------- abrir_motor: vários caminhos e processo órfão ----------

def test_abrir_motor_aceita_varias_pastas_e_ignora_a_que_nao_existe(monkeypatch, tmp_path, capsys):
    a, b = tmp_path / "a", tmp_path / "b"
    a.mkdir(); b.mkdir()
    falso = MotorFalso()
    monkeypatch.setattr(partida.chess.engine.SimpleEngine, "popen_uci", lambda caminho: falso)
    caminho = os.pathsep.join([str(a), str(tmp_path / "nao-existe"), str(b)])
    partida.abrir_motor("qualquer", 1, 16, caminho)
    assert falso.opcoes["SyzygyPath"] == os.pathsep.join([str(a), str(b)])
    assert "não existe" in capsys.readouterr().err


def test_abrir_motor_fecha_o_processo_se_listar_a_pasta_falhar(monkeypatch, tmp_path):
    falso = MotorFalso()
    monkeypatch.setattr(partida.chess.engine.SimpleEngine, "popen_uci", lambda caminho: falso)

    def sem_permissao(pasta):
        raise PermissionError("sem permissão")
    monkeypatch.setattr(partida.os, "listdir", sem_permissao)
    with pytest.raises(PermissionError):
        partida.abrir_motor("qualquer", 1, 16, str(tmp_path))
    assert falso.fechado is True


# ---------- book: ply 9 entra, depois do comando fen não entra ----------

def test_book_ainda_e_usado_no_ply_9(monkeypatch):
    lance = chess.Move.from_uci("a7a6")  # ply 9: é a vez das pretas
    board = chess.Board()
    for l in ("e2e4", "e7e5", "g1f3", "b8c6", "f1c4", "g8f6", "d2d3", "f8c5", "c2c3"):
        board.push_uci(l)
    assert board.ply() == 9
    monkeypatch.setattr(book, "lance_do_book", lambda b, c: lance)
    escolhido, info = partida.escolher_lance(board, None, "15+10", RELOGIO, caminho_book="x.bin")
    assert escolhido == lance and info["book"] is True


def test_book_desligado_depois_do_comando_fen(monkeypatch):
    """`fen` zera o contador de lances: sem esta trava o book voltaria no meio da partida."""
    def proibido(board, caminho):
        raise AssertionError("book consultado depois de um fen!")
    monkeypatch.setattr(book, "lance_do_book", proibido)
    board = chess.Board()
    board.set_fen("r1bqkb1r/pppp1ppp/2n2n2/4p3/2B1P3/5N2/PPPP1PPP/RNBQK2R w KQkq - 4 4")
    assert board.ply() < 10  # o contador parece "cedo", mas a partida não é do início
    with pytest.raises(RuntimeError, match="tempo_provisorio_s"):
        # passou pelo book sem consultá-lo e parou no tempo (sem tempo.py nem provisório)
        partida.escolher_lance(board, None, "15+10", RELOGIO, caminho_book="x.bin")


def test_book_continua_valendo_se_o_fen_for_a_posicao_inicial(monkeypatch):
    lance = chess.Move.from_uci("e2e4")
    monkeypatch.setattr(book, "lance_do_book", lambda b, c: lance)
    board = chess.Board()
    board.set_fen(chess.STARTING_FEN)
    escolhido, info = partida.escolher_lance(board, None, "15+10", RELOGIO, caminho_book="x.bin")
    assert info["book"] is True


# ---------- tempo.py com bug ou lixo: modo de emergência ----------

@precisa_stockfish
@pytest.mark.parametrize("devolvido", [None, (0, 0), (-1, 5), (float("nan"), 1), ("1", "2"),
                                      (True, True), (0.1, float("inf")), 5])
def test_calcular_tempo_devolvendo_lixo_vira_emergencia(motor, monkeypatch, devolvido):
    monkeypatch.setattr(tempo, "calcular_tempo", lambda *a: devolvido)
    antes = time.monotonic()
    lance, info = partida.escolher_lance(chess.Board(), motor, "15+10", RELOGIO)
    assert lance in chess.Board().legal_moves
    assert time.monotonic() - antes < 1.0   # depth=1 é quase instantâneo
    assert info["profundidade"] == 1


@precisa_stockfish
@pytest.mark.parametrize("erro", [ZeroDivisionError, TypeError, KeyError, ValueError])
def test_calcular_tempo_com_bug_nao_derruba_o_lance(motor, monkeypatch, erro):
    def quebra(*a):
        raise erro("bug do tempo.py")
    monkeypatch.setattr(tempo, "calcular_tempo", quebra)
    lance, info = partida.escolher_lance(chess.Board(), motor, "15+10", RELOGIO)
    assert lance in chess.Board().legal_moves


@precisa_stockfish
def test_relogio_incompleto_vira_emergencia_e_nao_derruba(motor):
    lance, info = partida.escolher_lance(chess.Board(), motor, "15+10", {"restante_s": 900})
    assert lance in chess.Board().legal_moves


@precisa_stockfish
def test_maximo_maior_que_o_relogio_e_cortado_no_restante(motor, monkeypatch):
    monkeypatch.setattr(tempo, "calcular_tempo", lambda *a: (100.0, 100.0))
    visto = []
    monkeypatch.setattr(tempo, "deve_parar", lambda d, alvo, maximo, *r: visto.append((alvo, maximo)) or True)
    relogio = {"restante_s": 0.3, "incremento_s": 0, "atraso_humano_s": 0}
    partida.escolher_lance(chess.Board(), motor, "25+0", relogio)
    assert visto and all(a <= 0.3 and m <= 0.3 for a, m in visto)


@precisa_stockfish
def test_alvo_maior_que_maximo_e_cortado_no_maximo(motor, monkeypatch):
    monkeypatch.setattr(tempo, "calcular_tempo", lambda *a: (5.0, 0.3))
    visto = []
    monkeypatch.setattr(tempo, "deve_parar", lambda d, alvo, maximo, *r: visto.append((alvo, maximo)) or True)
    partida.escolher_lance(chess.Board(), motor, "15+10", RELOGIO)
    assert visto[0] == (0.3, 0.3)


@precisa_stockfish
def test_pv_do_info_sempre_comeca_pelo_lance_jogado(motor):
    for _ in range(3):
        lance, info = partida.escolher_lance(chess.Board(), motor, "15+10", RELOGIO, tempo_provisorio_s=0.2)
        assert info["pv"][0] == lance


# ---------- motor travado ou morto ----------

class AnaliseTravada:
    """Simula um Stockfish congelado: não manda nenhuma linha até alguém fechar o processo."""

    def __init__(self, motor):
        self.motor = motor

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def __iter__(self):
        return self

    def __next__(self):
        if not self.motor.fechado_evento.wait(timeout=10):
            raise AssertionError("o watchdog não fechou o motor a tempo")
        raise chess.engine.EngineTerminatedError("processo fechado")

    def stop(self):
        pass

    def wait(self):
        raise chess.engine.EngineTerminatedError("processo fechado")


class MotorTravado:
    def __init__(self):
        import threading
        self.fechado_evento = threading.Event()

    def analysis(self, board, limit):
        return AnaliseTravada(self)

    def close(self):
        self.fechado_evento.set()


def test_watchdog_fecha_o_motor_travado_e_devolve_lance_legal(monkeypatch):
    monkeypatch.setattr(tempo, "calcular_tempo", lambda *a: (0.1, 0.1))
    motor = MotorTravado()
    antes = time.monotonic()
    lance, info = partida.escolher_lance(chess.Board(), motor, "15+10", RELOGIO, folga_watchdog_s=0.1)
    assert time.monotonic() - antes < 3.0
    assert motor.fechado_evento.is_set()
    assert info["motor_caiu"] is True
    assert lance in chess.Board().legal_moves


def test_motor_que_morre_no_meio_devolve_lance_legal_e_avisa(monkeypatch):
    class AnaliseMorre:
        def __enter__(self):
            raise chess.engine.EngineTerminatedError("o Stockfish morreu")

        def __exit__(self, *args):
            return False

    class MotorMorto:
        def analysis(self, board, limit):
            return AnaliseMorre()

    monkeypatch.setattr(tempo, "calcular_tempo", lambda *a: (0.1, 0.2))
    lance, info = partida.escolher_lance(chess.Board(), MotorMorto(), "15+10", RELOGIO)
    assert info["motor_caiu"] is True
    assert lance in chess.Board().legal_moves


@precisa_stockfish
def test_watchdog_nao_atrapalha_quando_tudo_funciona(motor, monkeypatch):
    monkeypatch.setattr(tempo, "calcular_tempo", lambda *a: (0.2, 0.3))
    lance, info = partida.escolher_lance(chess.Board(), motor, "15+10", RELOGIO, folga_watchdog_s=2.0)
    assert info["motor_caiu"] is False
    # o vigia foi cancelado: o motor continua vivo e dá para jogar de novo
    lance2, info2 = partida.escolher_lance(chess.Board(), motor, "15+10", RELOGIO, folga_watchdog_s=2.0)
    assert info2["motor_caiu"] is False and lance2 in chess.Board().legal_moves


# ---------- atalho recebe dados reais ----------

def test_atalho_recebe_em_tablebase_calculado(monkeypatch):
    recebido = []
    monkeypatch.setattr(tempo, "atalho_tempo_zero", lambda board, lb, tb: recebido.append(tb) or None)
    with pytest.raises(RuntimeError):
        partida.escolher_lance(chess.Board(), None, "15+10", RELOGIO)
    assert recebido == [False]                       # 32 peças
    pouco = chess.Board("8/8/8/8/8/8/k7/4K2R w K - 0 1")
    with pytest.raises(RuntimeError):
        partida.escolher_lance(pouco, None, "15+10", RELOGIO)
    assert recebido == [False, True]                 # 3 peças


def test_atalho_com_bug_nao_derruba(monkeypatch, capsys):
    def quebra(*a):
        raise KeyError("bug")
    monkeypatch.setattr(tempo, "atalho_tempo_zero", quebra)
    with pytest.raises(RuntimeError, match="tempo_provisorio_s"):
        partida.escolher_lance(chess.Board(), None, "15+10", RELOGIO)
    assert "atalho_tempo_zero falhou" in capsys.readouterr().err


# ---------- correções da 3ª rodada de revisão ----------

@precisa_stockfish
def test_atraso_humano_e_descontado_do_maximo(motor, monkeypatch):
    monkeypatch.setattr(tempo, "calcular_tempo", lambda *a: (100.0, 100.0))
    visto = []
    monkeypatch.setattr(tempo, "deve_parar", lambda d, alvo, maximo, *r: visto.append(maximo) or True)
    relogio = {"restante_s": 1.0, "incremento_s": 0.0, "atraso_humano_s": 0.7}
    partida.escolher_lance(chess.Board(), motor, "25+0", relogio)
    assert visto and all(abs(m - 0.3) < 1e-9 for m in visto)   # 1,0 - 0,7


@precisa_stockfish
def test_atraso_maior_que_o_relogio_vira_emergencia(motor, monkeypatch):
    monkeypatch.setattr(tempo, "calcular_tempo", lambda *a: (1.0, 1.0))
    relogio = {"restante_s": 3.0, "incremento_s": 0.0, "atraso_humano_s": 8.0}
    lance, info = partida.escolher_lance(chess.Board(), motor, "25+0", relogio)
    assert lance in chess.Board().legal_moves and info["profundidade"] == 1


def test_ctrl_c_durante_a_busca_usa_o_melhor_lance_visto(monkeypatch):
    class AnaliseCtrlC:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def __iter__(self):
            return self

        def __next__(self):
            raise KeyboardInterrupt

        def stop(self):
            pass

    class MotorCtrlC:
        def analysis(self, board, limit):
            return AnaliseCtrlC()
    monkeypatch.setattr(tempo, "calcular_tempo", lambda *a: (0.1, 0.2))
    lance, info = partida.escolher_lance(chess.Board(), MotorCtrlC(), "15+10", RELOGIO)
    assert lance in chess.Board().legal_moves
    assert info["motor_caiu"] is False   # Ctrl+C não é motor caído
