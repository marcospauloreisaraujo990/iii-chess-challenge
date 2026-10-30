"""Testes de main e jogar_partida (laço da partida). Dono: Junio.

O motor é falso nos testes de fluxo (os lances do nosso lado são combinados de antemão);
um teste usa o Stockfish de verdade, se ele estiver instalado.
"""
import glob
import os

import chess
import pytest

import log
import partida
import tempo

_RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STOCKFISH = next((c for c in glob.glob(os.path.join(_RAIZ, "stockfish", "stockfish-*"))
                  if os.path.isfile(c) and os.access(c, os.X_OK) and not c.endswith((".md", ".txt"))), None)

# Valores só de teste (não copiar para o código: regra 4 do CLAUDE.md).
def _relogio():
    return {"restante_s": 900.0, "incremento_s": 10.0, "atraso_humano_s": 5.0}


class Teclado:
    """Entrada falsa: devolve as linhas combinadas e, no fim, simula o teclado fechado."""

    def __init__(self, *linhas):
        self.linhas = list(linhas)

    def __call__(self, prompt=""):
        if not self.linhas:
            raise EOFError
        return self.linhas.pop(0)


def info_falsa(lance, tempo_s=2.0, book=False, caiu=False):
    return {"book": book, "profundidade": 0 if book else 20, "nos": 1000, "avaliacao": 0.3,
            "pv": [lance], "tempo_s": tempo_s, "motor_caiu": caiu}


def motor_com_lances(monkeypatch, *lances, **kw):
    """Faz escolher_lance devolver estes lances, na ordem. Guarda as chamadas."""
    fila = [chess.Move.from_uci(l) for l in lances]
    chamadas = []

    def falso(board, motor, perfil, relogio, caminho_book=None, tempo_provisorio_s=None, folga_watchdog_s=None,
              economia=False):
        chamadas.append({"fen": board.fen(), "relogio": dict(relogio), "perfil": perfil, "economia": economia})
        lance = fila.pop(0)
        return lance, info_falsa(lance, **kw)
    monkeypatch.setattr(partida, "escolher_lance", falso)
    return chamadas


class MotorQualquer:
    def __init__(self):
        self.fechado = False

    def quit(self):
        self.fechado = True


class RelogioFalso:
    """Tempo de mentira: só anda quando o teste manda (`.t += segundos`)."""

    def __init__(self):
        self.t = 0.0

    def __call__(self):
        return self.t


def jogar(tmp_path, cor, teclado, motor="padrao", relogio=None, reabrir=None, perfil="15+10", agora=None):
    tela = []
    motor = MotorQualquer() if motor == "padrao" else motor
    resultado = partida.jogar_partida(cor, perfil, relogio or _relogio(), motor, entrada=teclado,
                                      saida=tela.append, pasta_partidas=str(tmp_path), reabrir_motor=reabrir,
                                      agora=agora or RelogioFalso())
    return resultado, tela, motor


def arquivos(tmp_path, extensao):
    return sorted(tmp_path.glob("*" + extensao))


# ---------------- fluxo completo ----------------

def test_partida_curta_ate_o_mate_do_tolo(tmp_path, monkeypatch):
    """Somos as pretas: adversário f2f3 e g2g4, nós e7e5 e d8h4 (mate)."""
    motor_com_lances(monkeypatch, "e7e5", "d8h4")
    resultado, tela, motor = jogar(tmp_path, chess.BLACK, Teclado("f2f3", "g2g4"))
    assert resultado == "0-1"
    assert any("Fim da partida: 0-1" in linha for linha in tela)
    assert motor.fechado is True


def test_log_so_tem_os_nossos_lances_com_os_8_campos(tmp_path, monkeypatch):
    motor_com_lances(monkeypatch, "e7e5", "d8h4")
    jogar(tmp_path, chess.BLACK, Teclado("f2f3", "g2g4"))
    linhas = arquivos(tmp_path, ".txt")[0].read_text(encoding="utf-8").splitlines()
    assert len(linhas) == 2
    assert linhas[0].startswith("1 | pretas | e7e5 | prof 20 | nós 1000 | aval +0.30 | pv e7e5 | 2.0 s")
    assert linhas[1].startswith("2 | pretas | d8h4 |")
    assert all(len(l.split(" | ")) == 8 for l in linhas)


def test_pgn_tem_todos_os_lances_e_o_resultado(tmp_path, monkeypatch):
    import chess.pgn
    motor_com_lances(monkeypatch, "e7e5", "d8h4")
    jogar(tmp_path, chess.BLACK, Teclado("f2f3", "g2g4"))
    with open(arquivos(tmp_path, ".pgn")[0], encoding="utf-8") as f:
        jogo = chess.pgn.read_game(f)
    assert [m.uci() for m in jogo.mainline_moves()] == ["f2f3", "e7e5", "g2g4", "d8h4"]
    assert jogo.headers["Result"] == "0-1"
    assert jogo.headers["Black"] == "Capablanca"


def test_comecando_de_brancas_o_motor_joga_primeiro(tmp_path, monkeypatch):
    chamadas = motor_com_lances(monkeypatch, "e2e4")
    with pytest.raises(EOFError):
        jogar(tmp_path, chess.WHITE, Teclado())
    assert chamadas[0]["fen"] == chess.STARTING_FEN


def test_relogio_desconta_tempo_do_motor_e_atraso_e_soma_incremento(tmp_path, monkeypatch):
    chamadas = motor_com_lances(monkeypatch, "e2e4", "g1f3", tempo_s=2.0)
    with pytest.raises(EOFError):
        jogar(tmp_path, chess.WHITE, Teclado("e7e5"))
    # 900 - 2 (motor) - 5 (atraso humano) + 10 (incremento) = 903
    assert chamadas[0]["relogio"]["restante_s"] == 900.0
    assert chamadas[1]["relogio"]["restante_s"] == 903.0


def test_relogio_nunca_fica_negativo(tmp_path, monkeypatch):
    chamadas = motor_com_lances(monkeypatch, "e2e4", "g1f3", tempo_s=50.0)
    relogio = {"restante_s": 10.0, "incremento_s": 0.0, "atraso_humano_s": 5.0}
    with pytest.raises(EOFError):
        jogar(tmp_path, chess.WHITE, Teclado("e7e5"), relogio=relogio)
    assert chamadas[1]["relogio"]["restante_s"] == 0.0


# ---------------- comandos de emergência dentro da partida ----------------

def test_comando_t_corrige_o_relogio(tmp_path, monkeypatch):
    chamadas = motor_com_lances(monkeypatch, "e2e4", "g1f3", tempo_s=0.0)
    monkeypatch.setattr(tempo, "sincronizar", lambda texto: 754)
    with pytest.raises(EOFError):
        jogar(tmp_path, chess.WHITE, Teclado("t 12:34", "e7e5"))
    # o operador informou 754 antes do 2º lance: o motor pensa com exatamente isso
    assert chamadas[1]["relogio"]["restante_s"] == 754


def test_desfazer_na_nossa_vez_nao_chama_o_motor_ate_o_operador_digitar_go(tmp_path, monkeypatch):
    """O operador digitou e7e5 mas o adversário jogou c7c5. O motor já tinha jogado.
    Corrigir: desfazer (nosso lance), desfazer (lance errado), digitar o certo."""
    chamadas = motor_com_lances(monkeypatch, "e2e4", "g1f3", "d2d4")
    tela = []
    with pytest.raises(EOFError):
        partida.jogar_partida(chess.WHITE, "15+10", _relogio(), MotorQualquer(),
                              entrada=Teclado("e7e5", "desfazer", "desfazer", "c7c5"), saida=tela.append,
                              pasta_partidas=str(tmp_path), agora=RelogioFalso())
    # 1ª chamada: abertura (e2e4). 2ª: depois do e7e5 errado (g1f3). Depois dos dois 'desfazer'
    # e do c7c5 correto, o motor pensa de novo — e só 3 chamadas no total, nunca sobre a posição errada.
    assert [c["fen"] for c in chamadas][0] == chess.STARTING_FEN
    assert len(chamadas) == 3
    # a 3ª posição é a CORRETA: e2e4 c7c5
    certo = chess.Board()
    certo.push_uci("e2e4"); certo.push_uci("c7c5")
    assert chamadas[2]["fen"] == certo.fen()


def test_apos_desfazer_na_nossa_vez_o_programa_espera_o_go(tmp_path, monkeypatch):
    chamadas = motor_com_lances(monkeypatch, "e2e4", "g1f3")
    tela = []
    # e7e5 -> motor joga g1f3; 'desfazer' tira o g1f3 e a vez volta a ser nossa: NÃO pensa sozinho
    with pytest.raises(EOFError):
        partida.jogar_partida(chess.WHITE, "15+10", _relogio(), MotorQualquer(),
                              entrada=Teclado("e7e5", "desfazer"), saida=tela.append,
                              pasta_partidas=str(tmp_path), agora=RelogioFalso())
    assert len(chamadas) == 2        # só e2e4 e g1f3; nada depois do desfazer
    assert any("'go'" in linha for linha in tela)


def test_go_libera_o_motor_depois_do_desfazer(tmp_path, monkeypatch):
    chamadas = motor_com_lances(monkeypatch, "e2e4", "g1f3", "b1c3")
    with pytest.raises(EOFError):
        jogar(tmp_path, chess.WHITE, Teclado("e7e5", "desfazer", "go"))
    assert len(chamadas) == 3
    assert chamadas[2]["fen"] == chamadas[1]["fen"].replace("w", "w")  # mesma posição de antes


def test_lance_digitado_enquanto_espera_o_go_e_recusado(tmp_path, monkeypatch):
    chamadas = motor_com_lances(monkeypatch, "e2e4", "g1f3")
    tela = []
    with pytest.raises(EOFError):
        partida.jogar_partida(chess.WHITE, "15+10", _relogio(), MotorQualquer(),
                              entrada=Teclado("e7e5", "desfazer", "d2d4"), saida=tela.append,
                              pasta_partidas=str(tmp_path), agora=RelogioFalso())
    assert len(chamadas) == 2
    assert any("É a vez do motor" in linha for linha in tela)


def test_go_fora_de_hora_e_recusado():
    tela = []
    resultado = None
    with pytest.raises(EOFError):
        partida.ler_lance(chess.Board(), entrada=Teclado("go"), saida=tela.append)
    assert any("'go' só vale" in linha for linha in tela)


def test_fen_na_nossa_vez_tambem_espera_o_go(tmp_path, monkeypatch):
    chamadas = motor_com_lances(monkeypatch, "e2e4", "h1h2")
    fen = "8/8/8/8/8/8/k7/4K2R w K - 0 1"
    with pytest.raises(EOFError):
        jogar(tmp_path, chess.WHITE, Teclado("fen " + fen))
    assert len(chamadas) == 1   # só a abertura; depois do fen espera o 'go'


def test_comando_fen_recarrega_a_posicao(tmp_path, monkeypatch):
    chamadas = motor_com_lances(monkeypatch, "e2e4", "h1h2")
    fen = "8/8/8/8/8/8/k7/4K2R w K - 0 1"
    with pytest.raises(EOFError):
        jogar(tmp_path, chess.WHITE, Teclado("fen " + fen, "go"))
    assert chess.Board(chamadas[1]["fen"]).board_fen() == chess.Board(fen).board_fen()


def test_entrada_ruim_do_adversario_nao_derruba_a_partida(tmp_path, monkeypatch):
    motor_com_lances(monkeypatch, "e2e4", "g1f3")
    with pytest.raises(EOFError):
        jogar(tmp_path, chess.WHITE, Teclado("banana", "e7e9", "", "e7e5"))
    pgn = arquivos(tmp_path, ".pgn")[0].read_text(encoding="utf-8")
    assert "e5" in pgn  # a partida seguiu depois das entradas ruins


# ---------------- motor caiu ----------------

def test_motor_que_caiu_e_reiniciado_e_o_lance_e_aproveitado(tmp_path, monkeypatch):
    motor_com_lances(monkeypatch, "e2e4", "g1f3", caiu=True)
    novos = []

    def reabrir():
        novos.append(MotorQualquer())
        return novos[-1]
    with pytest.raises(EOFError):
        jogar(tmp_path, chess.WHITE, Teclado("e7e5"), reabrir=reabrir)
    assert len(novos) == 2          # reiniciou depois de cada lance com motor_caiu
    assert arquivos(tmp_path, ".pgn")[0].read_text(encoding="utf-8").count("e4") >= 1


def test_motor_que_nao_volta_vira_modo_manual(tmp_path, monkeypatch):
    def falha(*a, **k):
        raise AssertionError("não devia chamar o motor")
    monkeypatch.setattr(partida, "escolher_lance", falha)

    def reabrir():
        raise OSError("Stockfish sumiu")
    resultado, tela, _ = None, None, None
    tela = []
    with pytest.raises(EOFError):
        partida.jogar_partida(chess.WHITE, "15+10", _relogio(), None, entrada=Teclado("e2e4", "e7e5"),
                              saida=tela.append, pasta_partidas=str(tmp_path), reabrir_motor=reabrir)
    assert any("MODO MANUAL" in linha for linha in tela)
    linhas = arquivos(tmp_path, ".txt")[0].read_text(encoding="utf-8").splitlines()
    assert linhas[0].startswith("1 | brancas | e2e4 | prof 0")


def test_erro_do_escolher_lance_reinicia_e_cai_no_manual(tmp_path, monkeypatch):
    def quebra(*a, **k):
        raise KeyError("bug")
    monkeypatch.setattr(partida, "escolher_lance", quebra)
    tela = []
    with pytest.raises(EOFError):
        partida.jogar_partida(chess.WHITE, "15+10", _relogio(), MotorQualquer(), entrada=Teclado("e2e4"),
                              saida=tela.append, pasta_partidas=str(tmp_path), reabrir_motor=None)
    assert any("Erro ao escolher o lance" in linha for linha in tela)
    assert any("MODO MANUAL" in linha for linha in tela)


def test_teclado_fechado_salva_log_pgn_e_fecha_o_motor(tmp_path, monkeypatch):
    motor_com_lances(monkeypatch, "e2e4")
    motor = MotorQualquer()
    with pytest.raises(EOFError):
        jogar(tmp_path, chess.WHITE, Teclado(), motor=motor)
    assert motor.fechado is True
    assert arquivos(tmp_path, ".pgn") and arquivos(tmp_path, ".txt")
    assert "e2e4" in arquivos(tmp_path, ".txt")[0].read_text(encoding="utf-8")


def test_lance_de_book_vai_para_o_log_com_prof_0_e_book(tmp_path, monkeypatch):
    motor_com_lances(monkeypatch, "e2e4", book=True)
    with pytest.raises(EOFError):
        jogar(tmp_path, chess.WHITE, Teclado())
    linha = arquivos(tmp_path, ".txt")[0].read_text(encoding="utf-8").splitlines()[0]
    assert "prof 0" in linha and linha.endswith("| book")


# ---------------- main: perguntas e recusas na largada ----------------

def _com_tempo_pronto(monkeypatch):
    monkeypatch.setattr(tempo, "calcular_tempo", lambda *a: (1.0, 2.0))
    monkeypatch.delenv("CAPABLANCA_TEMPO_PROVISORIO_S", raising=False)
    monkeypatch.delenv("CAPABLANCA_ATRASO_HUMANO_S", raising=False)
    monkeypatch.delenv("CAPABLANCA_FOLGA_WATCHDOG_S", raising=False)


def test_main_recusa_comecar_sem_stockfish(monkeypatch):
    monkeypatch.setattr(partida, "_achar_stockfish", lambda: None)
    tela = []
    assert partida.main(entrada=Teclado(), saida=tela.append) == 2
    assert any("Stockfish não encontrado" in l for l in tela)


def _tempo_esqueleto(monkeypatch):
    def nao_existe(*a):
        raise NotImplementedError
    monkeypatch.setattr(tempo, "calcular_tempo", nao_existe)
    monkeypatch.delenv("CAPABLANCA_TEMPO_PROVISORIO_S", raising=False)
    monkeypatch.delenv("CAPABLANCA_FOLGA_WATCHDOG_S", raising=False)
    monkeypatch.delenv("CAPABLANCA_ATRASO_HUMANO_S", raising=False)


def test_main_recusa_comecar_se_tempo_py_nao_existe_e_nada_foi_informado(monkeypatch):
    _tempo_esqueleto(monkeypatch)
    monkeypatch.setattr(partida, "_achar_stockfish", lambda: "stockfish/x")
    monkeypatch.delenv("CAPABLANCA_TEMPO_PROVISORIO_S", raising=False)
    tela = []
    codigo = partida.main(entrada=Teclado("brancas", "15+10", "6"), saida=tela.append)
    assert codigo == 2
    assert any("tempo.py ainda não está implementado" in l for l in tela)


def test_main_valida_cor_perfil_e_atraso_ate_ficarem_certos(monkeypatch, tmp_path):
    _com_tempo_pronto(monkeypatch)
    monkeypatch.setattr(partida, "_achar_stockfish", lambda: "stockfish/x")
    monkeypatch.setattr(partida, "PASTA_PARTIDAS", str(tmp_path))
    monkeypatch.setattr(partida, "abrir_motor", lambda *a: MotorQualquer())
    visto = {}

    def falso(cor, chave, relogio, motor, *a, **k):
        visto.update(cor=cor, chave=chave, relogio=dict(relogio))
        return "1/2-1/2"
    monkeypatch.setattr(partida, "jogar_partida", falso)
    tela = []
    codigo = partida.main(entrada=Teclado("azul", "pretas", "blitz", "15+10", "abc", "-1", "6,5"), saida=tela.append)
    assert codigo == 0
    assert visto["cor"] == chess.BLACK and visto["chave"] == "15+10"
    assert visto["relogio"] == {"restante_s": 900.0, "incremento_s": 10.0, "atraso_humano_s": 6.5}
    assert sum("Digite" in l or "Perfil desconhecido" in l for l in tela) >= 4


def test_main_armageddon_depende_da_cor(monkeypatch, tmp_path):
    _com_tempo_pronto(monkeypatch)
    monkeypatch.setattr(partida, "_achar_stockfish", lambda: "stockfish/x")
    monkeypatch.setattr(partida, "abrir_motor", lambda *a: MotorQualquer())
    vistos = []
    monkeypatch.setattr(partida, "jogar_partida",
                        lambda cor, chave, relogio, *a, **k: vistos.append((chave, relogio["restante_s"], relogio["incremento_s"])))
    partida.main(entrada=Teclado("brancas", "armageddon", "5"), saida=lambda _: None)
    partida.main(entrada=Teclado("pretas", "armageddon", "5"), saida=lambda _: None)
    assert vistos == [("armageddon_brancas", 300.0, 0.0), ("armageddon_pretas", 240.0, 0.0)]


def test_main_com_teclado_fechado_sai_com_codigo_1(monkeypatch):
    _com_tempo_pronto(monkeypatch)
    monkeypatch.setattr(partida, "_achar_stockfish", lambda: "stockfish/x")
    monkeypatch.setattr(partida, "abrir_motor", lambda *a: MotorQualquer())

    def fecha(*a, **k):
        raise EOFError
    monkeypatch.setattr(partida, "jogar_partida", fecha)
    assert partida.main(entrada=Teclado("brancas", "25+0", "5"), saida=lambda _: None) == 1


def test_main_avisa_quando_o_motor_nao_abre(monkeypatch):
    _com_tempo_pronto(monkeypatch)
    monkeypatch.setattr(partida, "_achar_stockfish", lambda: "stockfish/x")

    def falha(*a):
        raise FileNotFoundError("sem motor")
    monkeypatch.setattr(partida, "abrir_motor", falha)
    tela = []
    assert partida.main(entrada=Teclado("brancas", "25+0", "5"), saida=tela.append) == 2
    assert any("Não consegui abrir o Stockfish" in l for l in tela)


def test_atraso_pode_vir_do_ambiente(monkeypatch):
    monkeypatch.setenv("CAPABLANCA_ATRASO_HUMANO_S", "7.5")
    assert partida._perguntar_atraso(Teclado(), lambda _: None) == 7.5


def test_variavel_de_ambiente_invalida_e_ignorada(monkeypatch):
    for ruim in ("abc", "-3", "nan", "inf"):
        monkeypatch.setenv("CAPABLANCA_X", ruim)
        assert partida._numero_do_ambiente("CAPABLANCA_X") is None


def test_formato_mmss():
    assert partida._mmss(754) == "12:34"
    assert partida._mmss(5) == "0:05"
    assert partida._mmss(-3) == "0:00"


# ---------------- Stockfish de verdade ----------------

@pytest.mark.skipif(STOCKFISH is None, reason="Stockfish não instalado em stockfish/")
def test_partida_real_com_stockfish_ate_o_teclado_fechar(tmp_path, monkeypatch):
    """Somos as brancas: o Stockfish de verdade joga 2 lances e tudo vai para log e PGN."""
    monkeypatch.setattr(tempo, "calcular_tempo", lambda *a: (0.15, 0.2))
    monkeypatch.setattr(tempo, "deve_parar", lambda *a: False)
    motor = partida.abrir_motor(STOCKFISH, 1, 16)
    tela = []
    with pytest.raises(EOFError):
        partida.jogar_partida(chess.WHITE, "15+10", _relogio(), motor, entrada=Teclado("e7e5"),
                              saida=tela.append, pasta_partidas=str(tmp_path))
    linhas = arquivos(tmp_path, ".txt")[0].read_text(encoding="utf-8").splitlines()
    assert len(linhas) == 2
    assert all(len(l.split(" | ")) == 8 for l in linhas)
    assert sum(">>> JOGUE:" in l for l in tela) == 2


# ====================== correções da rodada de revisão (relógio, fim, Ctrl+C...) ======================

def test_relogio_desconta_o_tempo_real_mesmo_se_o_motor_disser_menos(tmp_path, monkeypatch):
    """O operador demorou 20 s digitando o lance do adversário e o motor declarou 2 s: vale o real."""
    relogio_falso = RelogioFalso()
    chamadas = []

    def falso(board, motor, perfil, relogio, *a, **k):
        chamadas.append(dict(relogio))
        lance = list(board.legal_moves)[0]
        relogio_falso.t += 20.0           # 20 s reais passam enquanto "pensamos"
        return lance, info_falsa(lance, tempo_s=2.0)
    monkeypatch.setattr(partida, "escolher_lance", falso)
    with pytest.raises(EOFError):
        jogar(tmp_path, chess.WHITE, Teclado("e7e5"), agora=relogio_falso)
    segunda = chamadas[1]["restante_s"]
    assert segunda == 900.0 - 20.0 - 5.0 + 10.0   # 20 s reais, não 2 s


def test_tentativa_que_falha_nao_perde_o_tempo_ja_gasto(tmp_path, monkeypatch):
    """O motor gasta 30 s e quebra; o operador digita nosso lance no modo manual.
    Esses 30 s reais precisam sair do relógio, senão o erro se acumula lance a lance."""
    relogio_falso = RelogioFalso()
    chamadas = []
    estado = {"n": 0}

    def falso(board, motor, perfil, relogio, *a, **k):
        estado["n"] += 1
        chamadas.append(dict(relogio))
        if estado["n"] == 1:
            relogio_falso.t += 30.0       # 30 s gastos e depois o motor quebra
            raise KeyError("o motor quebrou")
        lance = list(board.legal_moves)[0]
        return lance, info_falsa(lance, tempo_s=0.0)
    monkeypatch.setattr(partida, "escolher_lance", falso)
    with pytest.raises(EOFError):
        jogar(tmp_path, chess.WHITE, Teclado("e2e4", "e7e5"), reabrir=lambda: MotorQualquer(),
              agora=relogio_falso)
    assert chamadas[0]["restante_s"] == 900.0
    # 900 - 30 (tentativa que falhou + digitação) - 5 (atraso humano) + 10 (incremento) = 875
    assert chamadas[1]["restante_s"] == 875.0


def test_aviso_quando_o_relogio_estimado_chega_a_zero(tmp_path, monkeypatch):
    motor_com_lances(monkeypatch, "e2e4", tempo_s=50.0)
    relogio = {"restante_s": 10.0, "incremento_s": 0.0, "atraso_humano_s": 5.0}
    tela = []
    with pytest.raises(EOFError):
        partida.jogar_partida(chess.WHITE, "25+0", relogio, MotorQualquer(), entrada=Teclado(),
                              saida=tela.append, pasta_partidas=str(tmp_path), agora=RelogioFalso())
    assert any("0:00" in linha and "t mm:ss" in linha for linha in tela)


def test_t_com_float_e_aceito(tmp_path, monkeypatch):
    chamadas = motor_com_lances(monkeypatch, "e2e4", "g1f3", tempo_s=0.0)
    monkeypatch.setattr(tempo, "sincronizar", lambda texto: 754.0)
    with pytest.raises(EOFError):
        jogar(tmp_path, chess.WHITE, Teclado("t 12:34", "e7e5"))
    assert chamadas[1]["relogio"]["restante_s"] == 754.0


def test_t_maior_que_o_maximo_possivel_pede_confirmacao_e_recusa_por_padrao(tmp_path, monkeypatch):
    chamadas = motor_com_lances(monkeypatch, "e2e4", "g1f3", tempo_s=0.0)
    monkeypatch.setattr(tempo, "sincronizar", lambda texto: 3120)   # 52:00 no perfil 15+10 (máx 15:10)
    tela = []
    with pytest.raises(EOFError):
        partida.jogar_partida(chess.WHITE, "15+10", _relogio(), MotorQualquer(),
                              entrada=Teclado("t 52:00", "", "e7e5"), saida=tela.append,
                              pasta_partidas=str(tmp_path), agora=RelogioFalso())
    assert any("Provável erro de digitação" in linha for linha in tela)
    assert any("NÃO alterado" in linha for linha in tela)
    assert chamadas[1]["relogio"]["restante_s"] == 905.0   # o valor errado não entrou (900-0-5+10)


def test_t_maior_que_o_maximo_confirmado_com_s_entra(tmp_path, monkeypatch):
    chamadas = motor_com_lances(monkeypatch, "e2e4", "g1f3", tempo_s=0.0)
    monkeypatch.setattr(tempo, "sincronizar", lambda texto: 3120)
    with pytest.raises(EOFError):
        jogar(tmp_path, chess.WHITE, Teclado("t 52:00", "s", "e7e5"))
    assert chamadas[1]["relogio"]["restante_s"] == 3120.0


def test_t_plausivel_nao_pede_confirmacao(tmp_path, monkeypatch):
    chamadas = motor_com_lances(monkeypatch, "e2e4", "g1f3", tempo_s=0.0)
    monkeypatch.setattr(tempo, "sincronizar", lambda texto: 600)
    with pytest.raises(EOFError):
        jogar(tmp_path, chess.WHITE, Teclado("t 10:00", "e7e5"))
    assert chamadas[1]["relogio"]["restante_s"] == 600.0


def test_eof_durante_a_confirmacao_do_t_sai_limpo(tmp_path, monkeypatch):
    motor_com_lances(monkeypatch, "e2e4")
    monkeypatch.setattr(tempo, "sincronizar", lambda texto: 3120)
    motor = MotorQualquer()
    with pytest.raises(EOFError):
        jogar(tmp_path, chess.WHITE, Teclado("t 52:00"), motor=motor)
    assert motor.fechado is True


def test_fim_de_partida_permite_desfazer_um_mate_digitado_errado(tmp_path, monkeypatch):
    """O motor "jogou" d8h4 e deu mate, mas o operador percebe que algo estava errado:
    no aviso de fim de partida digita 'desfazer', depois 'go', e a partida continua."""
    chamadas = motor_com_lances(monkeypatch, "e7e5", "d8h4", "g8f6")
    tela = []
    with pytest.raises(EOFError):   # a partida continua até o teclado do teste acabar
        partida.jogar_partida(chess.BLACK, "15+10", _relogio(), MotorQualquer(),
                              entrada=Teclado("f2f3", "g2g4", "desfazer", "go", "h2h3"), saida=tela.append,
                              pasta_partidas=str(tmp_path), agora=RelogioFalso())
    assert any("Se foi erro de digitação" in linha for linha in tela)
    assert len(chamadas) >= 3                      # pensou de novo depois do go (a 4ª só esgota a fila falsa)
    log_txt = arquivos(tmp_path, ".txt")[0].read_text(encoding="utf-8")
    assert "g8f6" in log_txt


def test_fim_de_partida_sem_resposta_encerra(tmp_path, monkeypatch):
    motor_com_lances(monkeypatch, "e7e5", "d8h4")
    resultado, tela, motor = jogar(tmp_path, chess.BLACK, Teclado("f2f3", "g2g4"))
    assert resultado == "0-1" and motor.fechado


def test_ctrl_c_na_hora_de_pensar_nao_derruba_o_programa(tmp_path, monkeypatch):
    """Simula Ctrl+C no meio do motor: o programa segue com o melhor lance (ver test_motor)."""
    motor_com_lances(monkeypatch, "e2e4")
    resultado_tela = []
    with pytest.raises(EOFError):
        partida.jogar_partida(chess.WHITE, "15+10", _relogio(), MotorQualquer(), entrada=Teclado(),
                              saida=resultado_tela.append, pasta_partidas=str(tmp_path), agora=RelogioFalso())


def test_dez_erros_seguidos_abortam_mas_salvam_tudo(tmp_path, monkeypatch):
    def quebra_sempre(*a, **k):
        raise KeyError("sempre")
    monkeypatch.setattr(partida, "ler_lance", quebra_sempre)
    motor = MotorQualquer()
    with pytest.raises(KeyError):
        jogar(tmp_path, chess.BLACK, Teclado(), motor=motor)
    assert motor.fechado is True
    assert arquivos(tmp_path, ".pgn") and arquivos(tmp_path, ".txt")


def test_contador_de_erros_zera_depois_de_um_sucesso(tmp_path, monkeypatch):
    original = partida.ler_lance
    falhas = {"n": 0}

    def intermitente(*a, **k):
        falhas["n"] += 1
        if falhas["n"] % 2 == 1 and falhas["n"] < 40:
            raise KeyError("a cada duas")
        return original(*a, **k)
    monkeypatch.setattr(partida, "ler_lance", intermitente)
    motor_com_lances(monkeypatch, "e2e4", "g1f3", "b1c3")
    with pytest.raises(EOFError):
        jogar(tmp_path, chess.WHITE, Teclado("e7e5", "b8c6"))   # nunca 10 erros SEGUIDOS


def test_reabrir_motor_falha_repetida_continua_no_manual_a_cada_lance(tmp_path, monkeypatch):
    tentativas = []

    def reabrir():
        tentativas.append(1)
        raise OSError("sumiu")
    monkeypatch.setattr(partida, "escolher_lance", lambda *a, **k: (_ for _ in ()).throw(AssertionError))
    tela = []
    with pytest.raises(EOFError):
        partida.jogar_partida(chess.WHITE, "15+10", _relogio(), None, entrada=Teclado("e2e4", "e7e5", "g1f3"),
                              saida=tela.append, pasta_partidas=str(tmp_path), reabrir_motor=reabrir,
                              agora=RelogioFalso())
    assert sum("MODO MANUAL" in linha for linha in tela) == 2        # nossos 2 lances, os dois manuais
    assert len(tentativas) >= 2 * partida.TENTATIVAS_REINICIO_MOTOR    # tentou de novo a cada lance


def test_motor_caiu_mas_devolveu_lance_valido_o_lance_e_jogado(tmp_path, monkeypatch):
    motor_com_lances(monkeypatch, "e2e4", caiu=True)
    novos = []
    with pytest.raises(EOFError):
        jogar(tmp_path, chess.WHITE, Teclado(), reabrir=lambda: novos.append(MotorQualquer()) or novos[-1])
    assert "e2e4" in arquivos(tmp_path, ".txt")[0].read_text(encoding="utf-8")


def test_modo_manual_aceita_desfazer_e_espera_o_go(tmp_path, monkeypatch):
    monkeypatch.setattr(partida, "escolher_lance", lambda *a, **k: (_ for _ in ()).throw(AssertionError))
    tela = []
    with pytest.raises(EOFError):
        partida.jogar_partida(chess.WHITE, "15+10", _relogio(), None, entrada=Teclado("desfazer"),
                              saida=tela.append, pasta_partidas=str(tmp_path), agora=RelogioFalso())
    assert any("Nada para desfazer" in linha for linha in tela)


def test_main_com_calcular_tempo_que_quebra_ainda_abre_a_partida(monkeypatch, tmp_path):
    def quebra(*a):
        raise ZeroDivisionError("bug do Marcos")
    monkeypatch.setattr(tempo, "calcular_tempo", quebra)
    monkeypatch.delenv("CAPABLANCA_TEMPO_PROVISORIO_S", raising=False)
    monkeypatch.delenv("CAPABLANCA_ATRASO_HUMANO_S", raising=False)
    monkeypatch.delenv("CAPABLANCA_FOLGA_WATCHDOG_S", raising=False)
    monkeypatch.setattr(partida, "_achar_stockfish", lambda: "stockfish/x")
    monkeypatch.setattr(partida, "abrir_motor", lambda *a: MotorQualquer())
    chamou = []
    monkeypatch.setattr(partida, "jogar_partida", lambda *a, **k: chamou.append(1) or "*")
    assert partida.main(entrada=Teclado("brancas", "25+0", "5"), saida=lambda _: None) == 0
    assert chamou == [1]


def test_main_avisa_book_ausente_e_watchdog_desligado(monkeypatch, tmp_path):
    _com_tempo_pronto(monkeypatch)
    monkeypatch.delenv("CAPABLANCA_FOLGA_WATCHDOG_S", raising=False)
    monkeypatch.setattr(partida, "_achar_stockfish", lambda: "stockfish/x")
    monkeypatch.setattr(partida, "CAMINHO_BOOK", str(tmp_path / "nao-existe.bin"))
    monkeypatch.setattr(partida, "abrir_motor", lambda *a: MotorQualquer())
    monkeypatch.setattr(partida, "jogar_partida", lambda *a, **k: "*")
    tela = []
    partida.main(entrada=Teclado("brancas", "25+0", "5"), saida=tela.append)
    assert any("Jogando sem book" in l for l in tela)
    assert any("watchdog desligado" in l for l in tela)


def test_main_com_tempo_provisorio_avisa_que_nao_vale_no_torneio(monkeypatch):
    _tempo_esqueleto(monkeypatch)
    monkeypatch.setenv("CAPABLANCA_TEMPO_PROVISORIO_S", "0.3")
    monkeypatch.setattr(partida, "_achar_stockfish", lambda: "stockfish/x")
    monkeypatch.setattr(partida, "abrir_motor", lambda *a: MotorQualquer())
    monkeypatch.setattr(partida, "jogar_partida", lambda *a, **k: "*")
    tela = []
    assert partida.main(entrada=Teclado("brancas", "25+0", "5"), saida=tela.append) == 0
    assert any("NÃO USAR NO TORNEIO" in l for l in tela)


def test_eof_nas_perguntas_da_largada_sai_com_codigo_1(monkeypatch):
    monkeypatch.setattr(partida, "_achar_stockfish", lambda: "stockfish/x")
    tela = []
    assert partida.main(entrada=Teclado("brancas"), saida=tela.append) == 1
    assert any("encerrada antes de começar" in l for l in tela)


def test_caminhos_nao_dependem_da_pasta_de_execucao():
    for caminho in (partida.PASTA_STOCKFISH, partida.CAMINHO_BOOK, partida.PASTA_TABLEBASES, partida.PASTA_PARTIDAS):
        assert os.path.isabs(caminho)


# ====================== modo economia (ligação com o tempo.py do Marcos) ======================

def test_modo_economia_verdadeiro_chega_ao_escolher_lance_e_aparece_na_tela(tmp_path, monkeypatch):
    chamadas = motor_com_lances(monkeypatch, "e2e4")
    monkeypatch.setattr(tempo, "modo_economia", lambda historico, material: True)
    tela = []
    with pytest.raises(EOFError):
        partida.jogar_partida(chess.WHITE, "15+10", _relogio(), MotorQualquer(), entrada=Teclado(),
                              saida=tela.append, pasta_partidas=str(tmp_path), agora=RelogioFalso())
    assert chamadas[0]["economia"] is True
    assert any("[modo economia]" in linha for linha in tela)


def test_modo_economia_falso_por_padrao(tmp_path, monkeypatch):
    chamadas = motor_com_lances(monkeypatch, "e2e4")
    with pytest.raises(EOFError):
        jogar(tmp_path, chess.WHITE, Teclado())
    assert chamadas[0]["economia"] is False


def test_bug_no_modo_economia_nao_derruba_a_partida(tmp_path, monkeypatch):
    chamadas = motor_com_lances(monkeypatch, "e2e4")

    def quebra(*a):
        raise ZeroDivisionError("bug")
    monkeypatch.setattr(tempo, "modo_economia", quebra)
    with pytest.raises(EOFError):
        jogar(tmp_path, chess.WHITE, Teclado())
    assert chamadas[0]["economia"] is False


def test_historico_de_avaliacoes_guarda_centipawns_e_none_para_book_e_mate(tmp_path, monkeypatch):
    vistos = []
    monkeypatch.setattr(tempo, "modo_economia", lambda historico, material: vistos.append(list(historico)) or False)
    avaliacoes = iter([0.30, "#3", 0.0, -1.25])
    livros = iter([False, False, True, False])

    def falso(board, motor, perfil, relogio, *a, **k):
        lance = list(board.legal_moves)[0]
        info = info_falsa(lance)
        info["avaliacao"] = next(avaliacoes)
        info["book"] = next(livros)
        return lance, info
    monkeypatch.setattr(partida, "escolher_lance", falso)
    with pytest.raises(EOFError):
        jogar(tmp_path, chess.WHITE, Teclado("a7a6", "b7b6", "c7c6"))
    # antes do 1º lance: []. Depois: 30, None (mate), None (book, mesmo com 0.0), e por fim -125
    assert vistos[0] == []
    assert vistos[1] == [30]
    assert vistos[2] == [30, None]
    assert vistos[3] == [30, None, None]


precisa_stockfish_main = pytest.mark.skipif(STOCKFISH is None, reason="Stockfish não instalado em stockfish/")


@precisa_stockfish_main
def test_economia_corta_o_alvo_pela_metade_no_escolher_lance_real(monkeypatch):
    monkeypatch.setattr(tempo, "calcular_tempo", lambda *a: (0.4, 0.8))
    alvos = []
    monkeypatch.setattr(tempo, "deve_parar", lambda d, alvo, maximo, *r: alvos.append((alvo, maximo)) or True)
    motor = partida.abrir_motor(STOCKFISH, 1, 16)
    try:
        partida.escolher_lance(chess.Board(), motor, "15+10", _relogio(), economia=True)
        partida.escolher_lance(chess.Board(), motor, "15+10", _relogio(), economia=False)
    finally:
        motor.quit()
    assert alvos[0] == (0.4 * tempo.FATOR_ECONOMIA, 0.8)   # alvo cortado, máximo (limite duro) intacto
    assert alvos[1] == (0.4, 0.8)


@precisa_stockfish_main
def test_economia_nunca_corta_abaixo_do_tempo_minimo_nem_acima_do_maximo(monkeypatch):
    monkeypatch.setattr(tempo, "calcular_tempo", lambda *a: (0.06, 0.3))
    alvos = []
    monkeypatch.setattr(tempo, "deve_parar", lambda d, alvo, maximo, *r: alvos.append(alvo) or True)
    motor = partida.abrir_motor(STOCKFISH, 1, 16)
    try:
        partida.escolher_lance(chess.Board(), motor, "15+10", _relogio(), economia=True)
    finally:
        motor.quit()
    assert alvos[0] == tempo.TEMPO_MINIMO_S   # 0.06 * 0.5 = 0.03 < 0.05: sobe para o piso


# ---- casos de borda apontados pelo testador (economia) ----

def test_historico_esquece_a_avaliacao_do_lance_desfeito(tmp_path, monkeypatch):
    vistos = []
    monkeypatch.setattr(tempo, "modo_economia", lambda historico, material: vistos.append(list(historico)) or False)
    avaliacoes = iter([0.30, 0.10, 0.20])

    def falso(board, motor, perfil, relogio, *a, **k):
        lance = list(board.legal_moves)[0]
        info = info_falsa(lance)
        info["avaliacao"] = next(avaliacoes)
        return lance, info
    monkeypatch.setattr(partida, "escolher_lance", falso)
    with pytest.raises(EOFError):
        # nosso 1º lance (30), adversário a7a6, nosso 2º lance (10), desfazer (tira o 2º), go, nosso 2º de novo (20)
        jogar(tmp_path, chess.WHITE, Teclado("a7a6", "desfazer", "go"))
    assert vistos[0] == []
    assert vistos[1] == [30]
    assert vistos[2] == [30]        # depois do desfazer: só o primeiro; o 10 do lance desfeito saiu


def test_historico_zera_depois_do_comando_fen(tmp_path, monkeypatch):
    vistos = []
    monkeypatch.setattr(tempo, "modo_economia", lambda historico, material: vistos.append(list(historico)) or False)

    def falso(board, motor, perfil, relogio, *a, **k):
        lance = list(board.legal_moves)[0]
        return lance, info_falsa(lance)
    monkeypatch.setattr(partida, "escolher_lance", falso)
    fen = "8/8/8/8/8/8/k7/4K2R w K - 0 1"
    with pytest.raises(EOFError):
        jogar(tmp_path, chess.WHITE, Teclado("a7a6", "fen " + fen, "go"))
    assert vistos[0] == [] and len(vistos[1]) == 1     # depois do 1º lance: uma avaliação
    assert vistos[2] == []                              # depois do fen: posição nova, histórico zerado


@pytest.mark.parametrize("devolvido,esperado", [(None, False), (0, False), (1, True), ("sim", True), ([], False)])
def test_economia_nao_booleana_e_convertida_em_bool(tmp_path, monkeypatch, devolvido, esperado):
    chamadas = motor_com_lances(monkeypatch, "e2e4")
    monkeypatch.setattr(tempo, "modo_economia", lambda historico, material: devolvido)
    with pytest.raises(EOFError):
        jogar(tmp_path, chess.WHITE, Teclado())
    assert chamadas[0]["economia"] is esperado


@precisa_stockfish_main
def test_economia_nunca_deixa_o_alvo_passar_do_maximo_mesmo_abaixo_do_tempo_minimo(monkeypatch):
    monkeypatch.setattr(tempo, "calcular_tempo", lambda *a: (0.03, 0.03))   # máximo menor que TEMPO_MINIMO_S
    alvos = []
    monkeypatch.setattr(tempo, "deve_parar", lambda d, alvo, maximo, *r: alvos.append((alvo, maximo)) or True)
    motor = partida.abrir_motor(STOCKFISH, 1, 16)
    try:
        partida.escolher_lance(chess.Board(), motor, "15+10", {"restante_s": 900, "incremento_s": 10, "atraso_humano_s": 1},
                               economia=True)
    finally:
        motor.quit()
    alvo, maximo = alvos[0]
    assert alvo <= maximo == 0.03


def test_lance_forcado_ou_de_emergencia_sem_avaliacao_real_nao_entra_como_calmo(tmp_path, monkeypatch):
    """Achado do revisor-tempo: avaliação 0.0 de enfeite (profundidade 0) não pode virar 0 cp 'calmo'."""
    vistos = []
    monkeypatch.setattr(tempo, "modo_economia", lambda historico, material: vistos.append(list(historico)) or False)
    perfis = iter([(0.0, 0), (0.0, 1), (0.4, 18)])   # (avaliação, profundidade): forçado, emergência depth 1, normal

    def falso(board, motor, perfil, relogio, *a, **k):
        lance = list(board.legal_moves)[0]
        info = info_falsa(lance)
        info["avaliacao"], info["profundidade"] = next(perfis)
        return lance, info
    monkeypatch.setattr(partida, "escolher_lance", falso)
    with pytest.raises(EOFError):
        jogar(tmp_path, chess.WHITE, Teclado("a7a6", "b7b6", "c7c6"))
    assert vistos[1] == [None]            # profundidade 0: sem avaliação real
    assert vistos[2] == [None, 0]         # depth 1 tem avaliação real (0,0): conta
    assert vistos[3] == [None, 0, 40]


# ====================== ponder dentro da partida ======================

class _AnaliseRegistrada:
    def __init__(self, registro):
        import threading
        self.registro = registro
        self.parou = threading.Event()

    def __iter__(self):
        return self

    def __next__(self):
        self.parou.wait(timeout=5)
        raise StopIteration

    def stop(self):
        self.registro.append("ponder-parou")
        self.parou.set()


class _MotorComPonder(MotorQualquer):
    def __init__(self, registro):
        super().__init__()
        self.registro = registro

    def analysis(self, board, info=None):
        self.registro.append("ponder-comecou")
        return _AnaliseRegistrada(self.registro)


def _escolher_registrando(monkeypatch, registro, *lances):
    fila = [chess.Move.from_uci(l) for l in lances]

    def falso(*a, **k):
        registro.append("pensar")
        lance = fila.pop(0)
        return lance, info_falsa(lance)
    monkeypatch.setattr(partida, "escolher_lance", falso)


def test_ponder_para_sempre_antes_do_motor_pensar(tmp_path, monkeypatch):
    registro = []
    _escolher_registrando(monkeypatch, registro, "e2e4", "g1f3")
    with pytest.raises(EOFError):
        partida.jogar_partida(chess.WHITE, "15+10", _relogio(), _MotorComPonder(registro), entrada=Teclado("e7e5"),
                              saida=lambda _: None, pasta_partidas=str(tmp_path), agora=RelogioFalso(), ponder=True)
    # pensar (e2e4) -> ponder no tempo do adversário -> para -> pensar (g1f3) -> ponder -> para (EOF)
    assert registro == ["pensar", "ponder-comecou", "ponder-parou", "pensar", "ponder-comecou", "ponder-parou"]


def test_ponder_para_mesmo_com_teclado_fechado(tmp_path, monkeypatch):
    registro = []
    _escolher_registrando(monkeypatch, registro, "e2e4")
    with pytest.raises(EOFError):
        partida.jogar_partida(chess.WHITE, "15+10", _relogio(), _MotorComPonder(registro), entrada=Teclado(),
                              saida=lambda _: None, pasta_partidas=str(tmp_path), agora=RelogioFalso(), ponder=True)
    assert registro[-1] == "ponder-parou"


def test_ponder_desligado_nao_toca_no_motor(tmp_path, monkeypatch):
    registro = []
    _escolher_registrando(monkeypatch, registro, "e2e4", "g1f3")
    with pytest.raises(EOFError):
        partida.jogar_partida(chess.WHITE, "15+10", _relogio(), _MotorComPonder(registro), entrada=Teclado("e7e5"),
                              saida=lambda _: None, pasta_partidas=str(tmp_path), agora=RelogioFalso(), ponder=False)
    assert "ponder-comecou" not in registro


def test_ponder_nao_roda_sem_motor_modo_manual(tmp_path, monkeypatch):
    monkeypatch.setattr(partida, "escolher_lance", lambda *a, **k: (_ for _ in ()).throw(AssertionError))
    with pytest.raises(EOFError):
        partida.jogar_partida(chess.WHITE, "15+10", _relogio(), None, entrada=Teclado("e2e4", "e7e5"),
                              saida=lambda _: None, pasta_partidas=str(tmp_path), agora=RelogioFalso(), ponder=True)


def test_ponder_atravessa_desfazer_e_para_antes_de_pensar(tmp_path, monkeypatch):
    registro = []
    _escolher_registrando(monkeypatch, registro, "e2e4", "g1f3", "d2d4")
    with pytest.raises(EOFError):
        partida.jogar_partida(chess.WHITE, "15+10", _relogio(), _MotorComPonder(registro),
                              entrada=Teclado("e7e5", "desfazer", "desfazer", "c7c5"), saida=lambda _: None,
                              pasta_partidas=str(tmp_path), agora=RelogioFalso(), ponder=True)
    # nunca dois "pensar" seguidos sem o ponder ter parado entre eles
    for i, evento in enumerate(registro):
        if evento == "ponder-comecou":
            assert "ponder-parou" in registro[i + 1:]
            assert registro.index("ponder-parou", i) < (registro.index("pensar", i) if "pensar" in registro[i:] else 10**9)


def test_main_mostra_threads_hash_e_ponder(monkeypatch):
    _com_tempo_pronto(monkeypatch)
    monkeypatch.setenv("CAPABLANCA_THREADS", "15")
    monkeypatch.setenv("CAPABLANCA_HASH_MB", "2048")
    monkeypatch.delenv("CAPABLANCA_PONDER", raising=False)
    monkeypatch.setattr(partida, "_achar_stockfish", lambda: "stockfish/x")
    abertos = []
    monkeypatch.setattr(partida, "abrir_motor", lambda *a: abertos.append(a) or MotorQualquer())
    chamada = {}
    monkeypatch.setattr(partida, "jogar_partida", lambda *a, **k: chamada.update(k) or "*")
    tela = []
    partida.main(entrada=Teclado("brancas", "15+10", "12"), saida=tela.append)
    assert any("15 threads, 2048 MB" in l and "ponder ligado" in l for l in tela)
    assert abertos[0][1:3] == (15, 2048)
    assert chamada.get("ponder") is True
