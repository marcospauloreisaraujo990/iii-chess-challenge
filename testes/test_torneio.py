"""Testes do simulador (testes/torneio.py). Dono: Léo.

Quase tudo usa jogadores de mentira (lances combinados) para checar o relógio, o resultado e a
tabela com precisão. Dois testes no fim usam o Stockfish de verdade, se ele estiver instalado.
"""
import glob
import os

import chess
import pytest

import tempo
from ferramentas import gerar_book
from testes import torneio

_RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STOCKFISH = next((c for c in glob.glob(os.path.join(_RAIZ, "stockfish", "stockfish-*"))
                  if os.path.isfile(c) and os.access(c, os.X_OK) and not c.endswith((".md", ".txt"))), None)
precisa_stockfish = pytest.mark.skipif(STOCKFISH is None, reason="Stockfish não instalado em stockfish/")


class Roteirizado(torneio.Jogador):
    """Jogador de mentira: devolve os lances combinados, em ordem. Guarda o relógio que viu a cada lance."""

    def __init__(self, *lances_uci):
        super().__init__(motor=None)
        self.lances = [chess.Move.from_uci(m) for m in lances_uci]
        self.restantes_vistos = []

    def escolher(self, board, relogio):
        self.restantes_vistos.append(relogio.restante)
        return self.lances.pop(0)

    def fechar(self):
        pass


@pytest.fixture
def restaurar_tempo(monkeypatch):
    """aplicar_escala_no_tempo mexe nas constantes do tempo.py: o monkeypatch devolve tudo no fim do teste."""
    for nome in list(torneio.CONSTANTES_DE_TEMPO) + ["LANCES_RESTANTES_MINIMO", "FATOR_MAXIMO"]:
        monkeypatch.setattr(tempo, nome, getattr(tempo, nome))


# ---------------- relógio simulado ----------------

def test_relogio_desconta_pensar_e_atraso_e_soma_incremento_depois():
    relogio = torneio.RelogioSim(inicio_s=100, incremento_s=10, atraso_s=5)
    assert relogio.gastar(20) is False
    assert relogio.restante == 100 - 20 - 5 + 10


def test_bandeira_cai_quando_chega_a_zero_antes_do_incremento():
    relogio = torneio.RelogioSim(inicio_s=25, incremento_s=10, atraso_s=5)
    assert relogio.gastar(20) is True        # 25 - 20 - 5 = 0: caiu, e o incremento não salva
    relogio = torneio.RelogioSim(inicio_s=25, incremento_s=10, atraso_s=5)
    assert relogio.gastar(19.9) is False


def test_atraso_sozinho_sem_incremento_acaba_com_o_relogio():
    relogio = torneio.RelogioSim(inicio_s=10, incremento_s=0, atraso_s=4)
    assert [relogio.gastar(0), relogio.gastar(0), relogio.gastar(0)] == [False, False, True]


# ---------------- uma partida ----------------

def test_mate_do_tolo_termina_com_vitoria_das_pretas():
    r = torneio.jogar_partida(Roteirizado("f2f3", "g2g4"), Roteirizado("e7e5", "d8h4"), [], "15+10", 0.0, 0.01)
    assert (r["resultado"], r["motivo"]) == ("0-1", "checkmate")
    assert r["plies"] == 4
    assert "Qh4#" in r["pgn"]


def test_lance_ilegal_perde_a_partida():
    r = torneio.jogar_partida(Roteirizado("e2e5"), Roteirizado("e7e5"), [], "15+10", 0.0, 0.01)
    assert (r["resultado"], r["motivo"]) == ("0-1", "lance-ilegal")


def test_estourar_o_tempo_perde_a_partida():
    # 25+0 na escala 0.004 = 6 s; atraso 4 s por lance: no 2º lance das brancas o relógio zera
    brancas = Roteirizado("a2a3", "b2b3", "c2c3")
    pretas = Roteirizado("a7a6", "b7b6", "c7c6")
    r = torneio.jogar_partida(brancas, pretas, [], "25+0", atraso_s=4.0, escala=0.004)
    assert (r["resultado"], r["motivo"]) == ("0-1", "tempo")   # brancas estouraram primeiro
    assert r["plies"] == 2     # só a3 e a6 foram jogados: o lance em que a bandeira cai não vale


def test_limite_de_lances_vira_empate():
    brancas = Roteirizado("g1f3", "f3g1", "g1f3", "f3g1", "g1f3")
    pretas = Roteirizado("g8f6", "f6g8", "g8f6", "f6g8", "g8f6")
    r = torneio.jogar_partida(brancas, pretas, [], "15+10", 0.0, 0.01, max_plies=4)
    assert (r["resultado"], r["motivo"]) == ("1/2-1/2", "limite-de-lances")


def test_repeticao_e_reclamada_como_empate():
    brancas = Roteirizado(*["g1f3", "f3g1"] * 4)
    pretas = Roteirizado(*["g8f6", "f6g8"] * 4)
    r = torneio.jogar_partida(brancas, pretas, [], "15+10", 0.0, 0.01)
    assert r["resultado"] == "1/2-1/2"
    assert "repetition" in r["motivo"]


def test_abertura_e_jogada_sem_custo_de_relogio():
    abertura = [chess.Move.from_uci(m) for m in ("e2e4", "e7e5")]
    brancas = Roteirizado("g1f3")
    pretas = Roteirizado()
    torneio.jogar_partida(brancas, pretas, abertura, "15+10", 0.0, 0.01, max_plies=3)
    assert brancas.restantes_vistos == [pytest.approx(900 * 0.01)]   # relógio cheio na 1ª jogada de verdade


def test_armageddon_tem_tempos_diferentes_por_cor_e_empate_vale_pretas():
    brancas = Roteirizado("g1f3")
    pretas = Roteirizado("g8f6")
    r = torneio.jogar_partida(brancas, pretas, [], "armageddon", 0.0, 1.0, max_plies=2)
    assert brancas.restantes_vistos == [300.0] and pretas.restantes_vistos == [pytest.approx(240.0, abs=0.5)]
    assert (r["resultado"], r["motivo"]) == ("0-1", "empate-vale-pretas")


def test_perfil_desconhecido_da_erro_claro():
    with pytest.raises(ValueError, match="perfil desconhecido"):
        torneio.jogar_partida(Roteirizado("e2e4"), Roteirizado("e7e5"), [], "blitz", 0.0, 1.0)


def test_estatisticas_de_tempo_da_partida():
    r = torneio.jogar_partida(Roteirizado("f2f3", "g2g4"), Roteirizado("e7e5", "d8h4"), [], "15+10", 0.0, 1.0)
    assert r["restante"]["brancas"] > 0 and r["restante"]["pretas"] > 0
    assert r["tempo_medio_lance"]["brancas"] >= 0


# ---------------- escala e ajustes ----------------

def test_escala_multiplica_so_as_constantes_absolutas_de_tempo(restaurar_tempo):
    antes = {n: getattr(tempo, n) for n in torneio.CONSTANTES_DE_TEMPO}
    fator_antes = tempo.FATOR_MAXIMO
    torneio.aplicar_escala_no_tempo(0.2)
    for nome, valor in antes.items():
        assert getattr(tempo, nome) == pytest.approx(valor * 0.2)
    assert tempo.FATOR_MAXIMO == fator_antes     # constante sem unidade de tempo não escala


def test_escala_nao_acumula_se_aplicada_duas_vezes(restaurar_tempo):
    torneio.aplicar_escala_no_tempo(0.2)
    torneio.aplicar_escala_no_tempo(0.2)
    assert tempo.RESERVA_MINIMA_S == pytest.approx(torneio._ORIGINAIS["RESERVA_MINIMA_S"] * 0.2)


def test_ajuste_troca_o_valor_final(restaurar_tempo):
    torneio.aplicar_escala_no_tempo(0.2, {"LANCES_RESTANTES_MINIMO": 25})
    assert tempo.LANCES_RESTANTES_MINIMO == 25


def test_ajuste_de_constante_que_nao_existe_da_erro(restaurar_tempo):
    with pytest.raises(ValueError, match="NAO_EXISTE"):
        torneio.aplicar_escala_no_tempo(0.2, {"NAO_EXISTE": 1})


def test_interpretar_ajustes():
    assert torneio.interpretar_ajustes(["LANCES_RESTANTES_MINIMO=30", "FATOR_MAXIMO=2.5"]) == \
        {"LANCES_RESTANTES_MINIMO": 30.0, "FATOR_MAXIMO": 2.5}
    assert torneio.interpretar_ajustes(None) == {}
    with pytest.raises(ValueError, match="NOME=VALOR"):
        torneio.interpretar_ajustes(["sem-igual"])


# ---------------- aberturas e tarefas ----------------

def test_aberturas_sao_distintas_legais_e_reprodutiveis():
    a = torneio.sortear_aberturas(30, semente=1)
    assert a == torneio.sortear_aberturas(30, semente=1)
    assert a != torneio.sortear_aberturas(30, semente=2)
    assert len({tuple(x) for x in a}) == 30
    for lances in a:
        assert len(lances) == torneio.PLIES_DE_ABERTURA
        board = chess.Board()
        for lance in lances:
            assert lance in board.legal_moves
            board.push(lance)


def test_pedir_mais_aberturas_do_que_existem_da_erro():
    with pytest.raises(ValueError, match="aberturas distintas"):
        torneio.sortear_aberturas(10**6, semente=1)


def _tarefas(**mudancas):
    base = dict(versao_a="nossa", versao_b="padrao", n_partidas=6, perfil="15+10", atraso_s=6.0, escala=0.2,
                tempo_fixo_s=None, ajustes={}, semente=1, max_plies=300)
    base.update(mudancas)
    return torneio.montar_tarefas(**base)


def test_cores_alternam_e_cada_abertura_e_jogada_duas_vezes():
    t = _tarefas()
    assert [x["brancas"] for x in t] == ["nossa", "padrao"] * 3
    assert [x["pretas"] for x in t] == ["padrao", "nossa"] * 3
    for i in (0, 2, 4):
        assert t[i]["abertura"] == t[i + 1]["abertura"]          # mesma abertura, cores trocadas
    assert len({tuple(x["abertura"]) for x in t}) == 3


def test_numero_impar_de_partidas_usa_abertura_a_mais():
    assert len(_tarefas(n_partidas=5)) == 5


def test_atraso_e_tempo_fixo_sao_escalados():
    t = _tarefas(versao_b="fixa", tempo_fixo_s=12.0, escala=0.2)[0]
    assert t["atraso_s"] == pytest.approx(1.2)
    assert t["tempo_fixo_s"] == pytest.approx(2.4)


def test_versao_fixa_exige_tempo_fixo():
    with pytest.raises(ValueError, match="--tempo-fixo"):
        _tarefas(versao_b="fixa", tempo_fixo_s=None)


def test_versoes_iguais_ou_desconhecidas_dao_erro():
    with pytest.raises(ValueError, match="iguais"):
        _tarefas(versao_b="nossa")
    with pytest.raises(ValueError, match="desconhecida"):
        _tarefas(versao_b="magica")


# ---------------- tabela ----------------

def _r(i, brancas, pretas, resultado, motivo, sobra_b=50.0, sobra_p=40.0):
    return {"indice": i, "brancas": brancas, "pretas": pretas, "resultado": resultado, "motivo": motivo, "plies": 60,
            "restante": {"brancas": sobra_b, "pretas": sobra_p}, "tempo_medio_lance": {"brancas": 1.0, "pretas": 2.0},
            "pgn": f'[Result "{resultado}"]\n\n*'}


def test_resumo_conta_vitorias_empates_derrotas_e_derrotas_por_tempo():
    resultados = [
        _r(0, "nossa", "padrao", "1-0", "checkmate"),       # nossa vence de brancas
        _r(1, "padrao", "nossa", "1-0", "tempo"),           # nossa perde por tempo de pretas
        _r(2, "nossa", "padrao", "1/2-1/2", "stalemate"),
        _r(3, "padrao", "nossa", "0-1", "checkmate"),       # nossa vence de pretas
    ]
    linhas = torneio.resumir(resultados, "nossa", "padrao")
    nossa, padrao = linhas["nossa"], linhas["padrao"]
    assert (nossa["vitorias"], nossa["empates"], nossa["derrotas"], nossa["derrotas_por_tempo"]) == (2, 1, 1, 1)
    assert (padrao["vitorias"], padrao["empates"], padrao["derrotas"], padrao["derrotas_por_tempo"]) == (1, 1, 2, 0)
    assert nossa["pontos"] == 2.5 and padrao["pontos"] == 1.5
    assert nossa["partidas"] == padrao["partidas"] == 4


def test_resumo_tempo_que_sobrou_ignora_negativos_e_usa_a_cor_certa():
    resultados = [_r(0, "nossa", "padrao", "0-1", "tempo", sobra_b=-3.0, sobra_p=40.0),
                  _r(1, "padrao", "nossa", "1-0", "checkmate", sobra_b=10.0, sobra_p=30.0)]
    linhas = torneio.resumir(resultados, "nossa", "padrao")
    assert linhas["nossa"]["sobra_media_s"] == pytest.approx((0.0 + 30.0) / 2)    # -3 vira 0; segunda: pretas = 30
    assert linhas["padrao"]["sobra_media_s"] == pytest.approx((40.0 + 10.0) / 2)


def test_tabela_markdown_tem_as_colunas_da_arguicao():
    linhas = torneio.resumir([_r(0, "nossa", "padrao", "1-0", "checkmate")], "nossa", "padrao")
    md = torneio.tabela_markdown(linhas, "titulo de teste")
    assert md.startswith("**titulo de teste**")
    for coluna in ("Vitórias", "Empates", "Derrotas", "Derrotas por tempo", "Tempo médio que sobrou"):
        assert coluna in md
    assert "| nossa | 1 | 1 | 0 | 0 | 0 | 1 |" in md


def test_salvar_resultados_cria_md_csv_e_pgn(tmp_path):
    resultados = [_r(0, "nossa", "padrao", "1-0", "checkmate"), _r(1, "padrao", "nossa", "1/2-1/2", "stalemate")]
    linhas = torneio.resumir(resultados, "nossa", "padrao")
    base = torneio.salvar_resultados(resultados, linhas, str(tmp_path / "res"), "teste", "t")
    assert open(base + ".md", encoding="utf-8").read().startswith("**t**")
    linhas_csv = open(base + ".csv", encoding="utf-8").read().splitlines()
    assert linhas_csv[0].startswith("partida,brancas,pretas,resultado,motivo")
    assert len(linhas_csv) == 3
    assert open(base + ".pgn", encoding="utf-8").read().count("[Result") == 2


# ---------------- linha de comando ----------------

def test_confronto_exige_o_atraso(capsys):
    with pytest.raises(SystemExit) as saida:
        torneio.main(["confronto", "--a", "nossa", "--b", "padrao", "--perfil", "15+10"])
    assert saida.value.code == 2
    assert "--atraso-s" in capsys.readouterr().err


def test_escala_invalida_e_recusada(capsys):
    with pytest.raises(SystemExit):
        torneio.main(["confronto", "--a", "nossa", "--b", "padrao", "--perfil", "15+10", "--atraso-s", "5", "--escala", "3"])


# ---------------- Stockfish de verdade ----------------

@precisa_stockfish
@pytest.mark.parametrize("a,b", [("nossa", "padrao"), ("nossa", "fixa")])
def test_confronto_real_termina_e_conta_certo(a, b, tmp_path, restaurar_tempo):
    resultados = torneio.rodar_torneio(a, b, 2, "15+10", atraso_s=1.0, escala=0.02, tempo_fixo_s=5.0,
                                       paralelo=2, max_plies=24, saida=lambda _: None)
    assert [r["indice"] for r in resultados] == [0, 1]
    assert {r["brancas"] for r in resultados} == {a, b}                  # cores trocadas
    for r in resultados:
        assert r["resultado"] in ("1-0", "0-1", "1/2-1/2")
        assert r["plies"] >= torneio.PLIES_DE_ABERTURA
    linhas = torneio.resumir(resultados, a, b)
    assert linhas[a]["partidas"] == linhas[b]["partidas"] == 2
    assert linhas[a]["vitorias"] + linhas[a]["empates"] + linhas[a]["derrotas"] == 2


@precisa_stockfish
def test_medir_estouro_funciona_e_devolve_numeros_plausiveis():
    saida = []
    r = torneio.medir_estouro(tempos_s=(0.05,), posicoes=3, saida=saida.append)
    assert len(r["abrir_s"]) == 5 and all(x > 0 for x in r["abrir_s"])
    assert r["pior_estouro_ms"] < 2000
    assert any("folga do watchdog" in linha for linha in saida)


def test_simulador_usa_1_thread_por_padrao_e_aceita_mais():
    t = _tarefas()[0]
    assert (t["threads"], t["hash_mb"]) == (1, 16)
    t = torneio.montar_tarefas("nossa", "padrao", 2, "15+10", 6.0, 0.2, None, {}, 1, 300, threads=8, hash_mb=256)[0]
    assert (t["threads"], t["hash_mb"]) == (8, 256)


# ---------------- ganchos do visualizador ----------------

class _Espiao:
    def __init__(self):
        self.eventos = []

    def inicio_lance(self, board, cor, relogios):
        self.eventos.append(("inicio", cor))

    def fim_lance(self, board, lance, pensou, relogios):
        self.eventos.append(("fim", lance.uci()))

    def fim_partida(self, resumo):
        self.eventos.append(("acabou", resumo["resultado"]))


def test_observador_recebe_cada_lance_e_o_fim():
    espiao = _Espiao()
    torneio.jogar_partida(Roteirizado("f2f3", "g2g4"), Roteirizado("e7e5", "d8h4"), [], "15+10", 0.0, 0.01,
                          observador=espiao)
    assert espiao.eventos == [("inicio", chess.WHITE), ("fim", "f2f3"), ("inicio", chess.BLACK), ("fim", "e7e5"),
                              ("inicio", chess.WHITE), ("fim", "g2g4"), ("inicio", chess.BLACK), ("fim", "d8h4"),
                              ("acabou", "0-1")]


def test_observador_com_erro_nao_derruba_a_partida():
    class Quebrado:
        def fim_lance(self, *a):
            raise RuntimeError("bug no visualizador")
    r = torneio.jogar_partida(Roteirizado("f2f3", "g2g4"), Roteirizado("e7e5", "d8h4"), [], "15+10", 0.0, 0.01,
                              observador=Quebrado())
    assert r["resultado"] == "0-1"


def test_cancelar_interrompe_entre_lances():
    import threading
    cancelar = threading.Event()
    cancelar.set()
    r = torneio.jogar_partida(Roteirizado("e2e4"), Roteirizado("e7e5"), [], "15+10", 0.0, 0.01, cancelar=cancelar)
    assert (r["resultado"], r["motivo"], r["plies"]) == ("*", "interrompida", 0)


def test_fraco_e_uma_versao_valida():
    assert "fraco" in torneio.VERSOES
    t = torneio.montar_tarefas("nossa", "fraco", 2, "15+10", 6.0, 0.2, None, {}, 1, 300)
    assert {x["pretas"] for x in t} | {x["brancas"] for x in t} == {"nossa", "fraco"}


@precisa_stockfish
def test_bot_fraco_real_joga_lance_legal():
    import partida
    motor = partida.abrir_motor(STOCKFISH, 1, 16)
    try:
        jogador = torneio.JogadorFraco(motor)
        relogio = torneio.RelogioSim(10, 0, 0)
        relogio.adversario = torneio.RelogioSim(10, 0, 0)
        assert jogador.escolher(chess.Board(), relogio) in chess.Board().legal_moves
    finally:
        motor.quit()
