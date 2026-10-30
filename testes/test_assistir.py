"""Testes do visualizador (ferramentas/assistir.py). Dono: Junio.

Quase tudo usa jogadores de mentira (sem Stockfish) para ser rápido e previsível.
"""
import http.client
import json
import threading
import time

import chess
import pytest

from ferramentas import assistir
from testes import torneio


class Roteirizado(torneio.Jogador):
    def __init__(self, *lances, ao_pensar=None, pausa=0.0):
        super().__init__(motor=None)
        self.lances = [chess.Move.from_uci(m) for m in lances]
        self.ao_pensar = ao_pensar
        self.pausa = pausa

    def escolher(self, board, relogio):
        if self.ao_pensar:
            self.ao_pensar({"profundidade": 12, "nos": 1000, "avaliacao": 0.25, "pv": self.lances[:1], "decorrido": 0.1})
        time.sleep(self.pausa)
        return self.lances.pop(0)

    def fechar(self):
        pass


def _fabrica(lances_nosso, lances_outro, pausa=0.0):
    """abrir_jogadores de mentira. A abertura sorteada é trocada por nenhuma (lances combinados)."""
    def abrir(oponente, perfil, escala, ao_pensar):
        return (Roteirizado(*lances_nosso, ao_pensar=ao_pensar, pausa=pausa),
                Roteirizado(*lances_outro, pausa=pausa), lambda: None)
    return abrir


@pytest.fixture(autouse=True)
def restaurar_tempo(monkeypatch):
    """O visualizador escala as constantes do tempo.py (certo no processo dele); aqui devolvemos no fim."""
    import tempo
    for nome in torneio.CONSTANTES_DE_TEMPO:
        monkeypatch.setattr(tempo, nome, getattr(tempo, nome))


@pytest.fixture
def sem_abertura(monkeypatch):
    monkeypatch.setattr(torneio, "sortear_aberturas", lambda n, semente: [[]])


@pytest.fixture
def servidor():
    criados = []

    def criar(visualizador):
        srv = assistir.criar_servidor(visualizador, porta=0)
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        criados.append((srv, visualizador))
        return srv.server_address[1]
    yield criar
    for srv, vis in criados:
        vis.parar()
        srv.shutdown()
        srv.server_close()


def _pedir(porta, metodo, caminho, corpo=None, host=None):
    conexao = http.client.HTTPConnection("127.0.0.1", porta, timeout=10)
    cabecalhos = {"Content-Type": "application/json"}
    if host:
        cabecalhos["Host"] = host
    conexao.request(metodo, caminho, body=json.dumps(corpo) if corpo is not None else None, headers=cabecalhos)
    resposta = conexao.getresponse()
    dados = resposta.read()
    conexao.close()
    return resposta.status, dados


def _esperar_fim(porta, limite=10):
    fim = time.monotonic() + limite
    while time.monotonic() < fim:
        estado = json.loads(_pedir(porta, "GET", "/estado")[1])
        if not estado["rodando"] and estado["resultado"]:
            return estado
        time.sleep(0.05)
    raise AssertionError("a partida não terminou a tempo")


# ---------------- conversões ----------------

def test_avaliacao_vira_ponto_de_vista_das_brancas():
    assert assistir._aval_brancas(0.25, chess.WHITE) == {"cp": 25, "mate": None}
    assert assistir._aval_brancas(0.25, chess.BLACK) == {"cp": -25, "mate": None}
    assert assistir._aval_brancas("#3", chess.WHITE) == {"cp": None, "mate": 3}
    assert assistir._aval_brancas("#3", chess.BLACK) == {"cp": None, "mate": -3}
    assert assistir._aval_brancas("-", chess.WHITE) == {"cp": None, "mate": None}


def test_linha_principal_em_notacao_legivel():
    pv = [chess.Move.from_uci(m) for m in ("e2e4", "e7e5", "g1f3")]
    assert assistir._pv_em_san(chess.Board(), pv) == ["e4", "e5", "Nf3"]
    assert assistir._pv_em_san(chess.Board(), [chess.Move.from_uci("e2e5")]) == []   # lance impossível para


def test_validacao_dos_pedidos():
    assert assistir.Visualizador.validar({}) == ("padrao", "rapido", "brancas")
    for ruim in ({"oponente": "x"}, {"controle": "blitz"}, {"lado": "verde"}):
        with pytest.raises(ValueError):
            assistir.Visualizador.validar(ruim)


# ---------------- servidor ----------------

def test_servidor_so_escuta_no_proprio_computador(servidor):
    vis = assistir.Visualizador(abrir_jogadores=_fabrica([], []))
    srv = assistir.criar_servidor(vis, porta=0)
    try:
        assert srv.server_address[0] == "127.0.0.1"
    finally:
        srv.server_close()


def test_pagina_estado_e_opcoes(servidor):
    porta = servidor(assistir.Visualizador(abrir_jogadores=_fabrica([], [])))
    status, html = _pedir(porta, "GET", "/")
    assert status == 200 and b"Capablanca ao vivo" in html
    assert b"http://" not in html.replace(b"http://127.0.0.1", b"")   # nada carregado de fora
    status, dados = _pedir(porta, "GET", "/estado")
    estado = json.loads(dados)
    assert status == 200 and estado["rodando"] is False and estado["fen"] == chess.STARTING_FEN
    status, dados = _pedir(porta, "GET", "/opcoes")
    opcoes = json.loads(dados)
    assert set(opcoes["oponentes"]) == {"padrao", "fraco", "fixa"} and opcoes["atraso_s"] == 12.0
    assert _pedir(porta, "GET", "/nada")[0] == 404


def test_pedido_invalido_da_400(servidor):
    porta = servidor(assistir.Visualizador(abrir_jogadores=_fabrica([], [])))
    assert _pedir(porta, "POST", "/nova", {"oponente": "x"})[0] == 400
    conexao = http.client.HTTPConnection("127.0.0.1", porta, timeout=5)
    conexao.request("POST", "/nova", body=b"isso nao e json", headers={"Content-Type": "application/json"})
    assert conexao.getresponse().status == 400


def test_pedido_de_outro_endereco_e_recusado(servidor):
    porta = servidor(assistir.Visualizador(abrir_jogadores=_fabrica([], [])))
    assert _pedir(porta, "GET", "/estado", host="site-malicioso.com")[0] == 403
    assert _pedir(porta, "POST", "/nova", {}, host="site-malicioso.com")[0] == 403


def test_partida_completa_ate_o_mate(servidor, sem_abertura):
    """Somos as pretas: o outro joga f3 e g4, nós e5 e Qh4#."""
    porta = servidor(assistir.Visualizador(abrir_jogadores=_fabrica(["e7e5", "d8h4"], ["f2f3", "g2g4"])))
    assert _pedir(porta, "POST", "/nova", {"oponente": "padrao", "controle": "rapido", "lado": "pretas"})[0] == 200
    estado = _esperar_fim(porta)
    assert (estado["resultado"], estado["motivo"]) == ("0-1", "checkmate")
    assert [l["san"] for l in estado["lances"]] == ["f3", "e5", "g4", "Qh4#"]
    assert estado["ultimo"] == "d8h4" and estado["nosso_lado"] == "pretas"
    assert estado["nomes"]["pretas"].startswith("Capablanca")
    assert len(estado["avaliacoes"]) == 2                          # só os nossos lances entram no gráfico
    assert estado["avaliacoes"][0]["cp"] == -25                     # +0.25 para as pretas = -25 das brancas
    assert estado["info"]["profundidade"] == 12 and estado["info"]["pv"]


def test_parar_no_meio_interrompe(servidor, sem_abertura):
    porta = servidor(assistir.Visualizador(abrir_jogadores=_fabrica(["e2e4"] + ["g1f3", "f3g1"] * 20,
                                                                    ["e7e5"] + ["g8f6", "f6g8"] * 20, pausa=0.2)))
    _pedir(porta, "POST", "/nova", {"lado": "brancas"})
    time.sleep(0.5)
    assert _pedir(porta, "POST", "/parar")[0] == 200
    estado = _esperar_fim(porta)
    assert estado["resultado"] == "*" and estado["motivo"] == "interrompida"


def test_nova_partida_substitui_a_anterior(servidor, sem_abertura):
    vis = assistir.Visualizador(abrir_jogadores=_fabrica(["e2e4"] + ["g1f3", "f3g1"] * 20,
                                                         ["e7e5"] + ["g8f6", "f6g8"] * 20, pausa=0.2))
    porta = servidor(vis)
    _pedir(porta, "POST", "/nova", {"lado": "brancas"})
    time.sleep(0.3)
    vis.abrir_jogadores = _fabrica(["e7e5", "d8h4"], ["f2f3", "g2g4"])
    _pedir(porta, "POST", "/nova", {"lado": "pretas"})
    estado = _esperar_fim(porta)
    assert estado["resultado"] == "0-1" and estado["nosso_lado"] == "pretas"


def test_erro_ao_abrir_os_motores_aparece_na_tela(servidor, sem_abertura):
    def quebra(*a):
        raise FileNotFoundError("Stockfish não encontrado")
    porta = servidor(assistir.Visualizador(abrir_jogadores=quebra))
    _pedir(porta, "POST", "/nova", {})
    estado = _esperar_fim(porta)
    assert "Stockfish não encontrado" in estado["erro"] and estado["resultado"] == "*"


def test_abertura_sorteada_aparece_na_lista_sem_custo(servidor, monkeypatch):
    monkeypatch.setattr(torneio, "sortear_aberturas", lambda n, semente: [[chess.Move.from_uci("e2e4"),
                                                                           chess.Move.from_uci("e7e5")]])
    porta = servidor(assistir.Visualizador(abrir_jogadores=_fabrica(["g1f3"], ["f7f6"] + ["e8f7"])))
    _pedir(porta, "POST", "/nova", {"lado": "brancas"})
    time.sleep(1.0)
    estado = json.loads(_pedir(porta, "GET", "/estado")[1])
    assert [l["san"] for l in estado["lances"]][:3] == ["e4", "e5", "Nf3"]
    assert estado["lances"][0].get("abertura") is True


# ---------------- segurança (achados do revisor de regras) ----------------

def _post_cru(porta, caminho, corpo, cabecalhos):
    conexao = http.client.HTTPConnection("127.0.0.1", porta, timeout=5)
    conexao.request("POST", caminho, body=corpo, headers=cabecalhos)
    resposta = conexao.getresponse()
    resposta.read()
    conexao.close()
    return resposta.status


def test_post_sem_json_e_recusado_contra_csrf(servidor):
    porta = servidor(assistir.Visualizador(abrir_jogadores=_fabrica([], [])))
    # um site malicioso só consegue mandar "text/plain" sem pedir permissão ao navegador
    assert _post_cru(porta, "/parar", b"{}", {"Content-Type": "text/plain"}) == 415


def test_post_de_outra_origem_e_recusado(servidor):
    porta = servidor(assistir.Visualizador(abrir_jogadores=_fabrica([], [])))
    status = _post_cru(porta, "/parar", b"{}", {"Content-Type": "application/json", "Origin": "http://site-malicioso.com"})
    assert status == 403
    status = _post_cru(porta, "/parar", b"{}", {"Content-Type": "application/json", "Origin": f"http://127.0.0.1:{porta}"})
    assert status == 200


def test_tamanho_do_pedido_e_validado(servidor):
    porta = servidor(assistir.Visualizador(abrir_jogadores=_fabrica([], [])))
    conexao = http.client.HTTPConnection("127.0.0.1", porta, timeout=5)
    conexao.putrequest("POST", "/parar")
    conexao.putheader("Content-Type", "application/json")
    conexao.putheader("Content-Length", "abc")
    conexao.endheaders()
    assert conexao.getresponse().status == 400
    conexao.close()
    assert _post_cru(porta, "/nova", b"x" * 5000, {"Content-Type": "application/json"}) == 413


def test_cabecalhos_de_seguranca_na_pagina(servidor):
    porta = servidor(assistir.Visualizador(abrir_jogadores=_fabrica([], [])))
    conexao = http.client.HTTPConnection("127.0.0.1", porta, timeout=5)
    conexao.request("GET", "/")
    resposta = conexao.getresponse()
    resposta.read()
    assert resposta.getheader("X-Frame-Options") == "DENY"
    assert "frame-ancestors 'none'" in resposta.getheader("Content-Security-Policy")
    conexao.close()


def test_caminho_com_parametros_funciona(servidor):
    porta = servidor(assistir.Visualizador(abrir_jogadores=_fabrica([], [])))
    assert _pedir(porta, "GET", "/estado?x=1")[0] == 200


def test_duas_novas_partidas_ao_mesmo_tempo_ficam_consistentes(servidor, sem_abertura):
    vis = assistir.Visualizador(abrir_jogadores=_fabrica(["e7e5", "d8h4"], ["f2f3", "g2g4"], pausa=0.05))
    porta = servidor(vis)
    fios = [threading.Thread(target=_pedir, args=(porta, "POST", "/nova", {"lado": "pretas"})) for _ in range(4)]
    for f in fios:
        f.start()
    for f in fios:
        f.join()
    estado = _esperar_fim(porta)
    # uma partida só, inteira e coerente (nenhuma partida antiga misturou lances na tela)
    assert [l["san"] for l in estado["lances"]] == ["f3", "e5", "g4", "Qh4#"]
    assert estado["resultado"] == "0-1" and vis.geracao == 4


def test_partida_antiga_nao_escreve_na_tela_da_nova(servidor, sem_abertura):
    vis = assistir.Visualizador(abrir_jogadores=_fabrica(["e2e4"] + ["g1f3", "f3g1"] * 20,
                                                         ["e7e5"] + ["g8f6", "f6g8"] * 20, pausa=0.3))
    porta = servidor(vis)
    _pedir(porta, "POST", "/nova", {"lado": "brancas"})
    time.sleep(0.5)
    vis.abrir_jogadores = _fabrica(["e7e5", "d8h4"], ["f2f3", "g2g4"])
    _pedir(porta, "POST", "/nova", {"lado": "pretas"})
    estado = _esperar_fim(porta)
    time.sleep(0.5)    # se a partida antiga ainda escrevesse, apareceria agora
    estado = json.loads(_pedir(porta, "GET", "/estado")[1])
    assert [l["san"] for l in estado["lances"]] == ["f3", "e5", "g4", "Qh4#"]
    assert estado["rodando"] is False and estado["resultado"] == "0-1"


# ====================== modo "jogar contra o bot" ======================

class MotorFalso:
    def __init__(self):
        self.fechado = False

    def close(self):
        self.fechado = True


class PonderFalso:
    registro = []

    def __init__(self, motor, board):
        PonderFalso.registro.append("ponder-comecou")

    def parar(self):
        PonderFalso.registro.append("ponder-parou")
        return True


def _escolher_falso(respostas, demora=0.0, registro=None):
    """Imita partida.escolher_lance: devolve os lances combinados, em ordem."""
    fila = [chess.Move.from_uci(m) for m in respostas]

    def escolher(board, motor, perfil, relogio, caminho_book=None, ao_pensar=None, **k):
        if registro is not None:
            registro.append("pensar")
        if ao_pensar:
            ao_pensar({"profundidade": 15, "nos": 5000, "avaliacao": 0.3, "pv": fila[:1], "decorrido": 0.1})
        time.sleep(demora)
        lance = fila.pop(0)
        return lance, {"book": False, "profundidade": 15, "nos": 5000, "avaliacao": 0.3, "pv": [lance],
                       "tempo_s": demora, "motor_caiu": False}
    return escolher


def _vis_jogar(respostas, demora=0.0, registro=None):
    PonderFalso.registro = registro if registro is not None else []
    return assistir.Visualizador(abrir_bot=MotorFalso, escolher=_escolher_falso(respostas, demora, registro),
                                 ponder=PonderFalso)


def _esperar(porta, condicao, limite=10):
    fim = time.monotonic() + limite
    while time.monotonic() < fim:
        estado = json.loads(_pedir(porta, "GET", "/estado")[1])
        if condicao(estado):
            return estado
        time.sleep(0.03)
    raise AssertionError("condição não aconteceu a tempo")


def test_jogar_voce_de_brancas_o_bot_responde(servidor):
    porta = servidor(_vis_jogar(["e7e5", "b8c6"]))
    assert _pedir(porta, "POST", "/nova", {"modo": "jogar", "lado": "pretas", "relogio": "5+3"})[0] == 200
    estado = _esperar(porta, lambda e: e["pensando"] == "brancas")
    assert estado["modo"] == "jogar" and len(estado["legais"]) == 20       # vez do humano: 20 lances legais
    assert estado["nomes"]["pretas"].startswith("Capablanca")
    assert _pedir(porta, "POST", "/lance", {"uci": "e2e4"})[0] == 200
    estado = _esperar(porta, lambda e: len(e["lances"]) == 2 and e["pensando"] == "brancas")
    assert [l["san"] for l in estado["lances"]] == ["e4", "e5"]
    # relógio do humano: 300 - (o que demorou) + 3 de incremento
    assert 300 < estado["relogios"]["brancas"] <= 303
    assert estado["info"]["profundidade"] == 15 and estado["info"]["pv"]


def test_jogar_lance_ilegal_ou_fora_da_vez_e_recusado(servidor):
    porta = servidor(_vis_jogar(["e7e5"], demora=1.0))
    _pedir(porta, "POST", "/nova", {"modo": "jogar", "lado": "pretas", "relogio": "5+3"})
    _esperar(porta, lambda e: e["pensando"] == "brancas")
    assert _pedir(porta, "POST", "/lance", {"uci": "e2e5"})[0] == 409        # ilegal
    assert _pedir(porta, "POST", "/lance", {"uci": "banana"})[0] == 409
    assert _pedir(porta, "POST", "/lance", {"uci": "e2e4"})[0] == 200
    assert _pedir(porta, "POST", "/lance", {"uci": "d2d4"})[0] == 409        # agora é a vez do bot


def test_jogar_bot_de_brancas_comeca_pensando(servidor):
    porta = servidor(_vis_jogar(["e2e4"]))
    _pedir(porta, "POST", "/nova", {"modo": "jogar", "lado": "brancas", "relogio": "3+2"})
    estado = _esperar(porta, lambda e: len(e["lances"]) == 1)
    assert estado["lances"][0]["san"] == "e4" and estado["pensando"] == "pretas" and estado["legais"]


def test_jogar_humano_estoura_o_tempo(servidor, monkeypatch):
    monkeypatch.setitem(assistir.RELOGIOS_JOGAR, "teste", (0.4, 0))
    porta = servidor(_vis_jogar([]))
    _pedir(porta, "POST", "/nova", {"modo": "jogar", "lado": "pretas", "relogio": "teste"})
    estado = _esperar(porta, lambda e: e["resultado"] is not None)
    assert (estado["resultado"], estado["motivo"]) == ("0-1", "tempo")      # você (brancas) perdeu no tempo
    assert estado["relogios"]["brancas"] == 0.0 and estado["rodando"] is False


def test_jogar_bot_estoura_o_tempo(servidor, monkeypatch):
    monkeypatch.setitem(assistir.RELOGIOS_JOGAR, "teste", (0.3, 0))
    porta = servidor(_vis_jogar(["e2e4"], demora=0.6))
    _pedir(porta, "POST", "/nova", {"modo": "jogar", "lado": "brancas", "relogio": "teste"})
    estado = _esperar(porta, lambda e: e["resultado"] is not None)
    assert (estado["resultado"], estado["motivo"]) == ("0-1", "tempo")      # o bot (brancas) perdeu no tempo


def test_jogar_desistir(servidor):
    porta = servidor(_vis_jogar([]))
    _pedir(porta, "POST", "/nova", {"modo": "jogar", "lado": "pretas", "relogio": "5+3"})
    _esperar(porta, lambda e: e["pensando"] == "brancas")
    assert _pedir(porta, "POST", "/desistir", {})[0] == 200
    estado = _esperar(porta, lambda e: e["resultado"] is not None)
    assert (estado["resultado"], estado["motivo"]) == ("0-1", "desistencia")


def test_desistir_sem_partida_e_recusado(servidor):
    porta = servidor(_vis_jogar([]))
    assert _pedir(porta, "POST", "/desistir", {})[0] == 409


def test_jogar_ponder_para_antes_do_bot_pensar(servidor):
    registro = []
    porta = servidor(_vis_jogar(["e7e5", "b8c6"], registro=registro))
    _pedir(porta, "POST", "/nova", {"modo": "jogar", "lado": "pretas", "relogio": "5+3"})
    _esperar(porta, lambda e: e["pensando"] == "brancas")
    _pedir(porta, "POST", "/lance", {"uci": "e2e4"})
    _esperar(porta, lambda e: len(e["lances"]) == 2 and e["pensando"] == "brancas")
    _pedir(porta, "POST", "/lance", {"uci": "g1f3"})
    _esperar(porta, lambda e: len(e["lances"]) == 4)
    # nunca "pensar" sem o ponder anterior ter parado
    assert registro[:6] == ["ponder-comecou", "ponder-parou", "pensar", "ponder-comecou", "ponder-parou", "pensar"]


def test_jogar_parametros_invalidos(servidor):
    porta = servidor(_vis_jogar([]))
    for ruim in ({"relogio": "99+99"}, {"lado": "verde"}, {"atraso": 7}, {"atraso": "abc"}):
        assert _pedir(porta, "POST", "/nova", {"modo": "jogar", **ruim})[0] == 400


def test_promocao_precisa_da_peca_e_e_aceita_com_ela():
    vis = _vis_jogar([])
    vis.tabuleiro_humano = chess.Board("8/4P2k/8/8/8/8/8/K7 w - - 0 1")
    with pytest.raises(ValueError):
        vis.lance_humano("e7e8")                 # falta a peça
    vis.lance_humano("e7e8n")                    # cavalo
    assert vis.fila_humano.get_nowait() == ("lance", chess.Move.from_uci("e7e8n"))
    with pytest.raises(ValueError, match="sua vez"):
        vis.lance_humano("a1a2")                 # um lance por vez


def test_lance_digitado_aceita_uci_san_e_portugues():
    """A pessoa copia o lance da outra tela sem traduzir: e2e4, e4, Nf3 ou Cf3 valem o mesmo."""
    board = chess.Board()
    for texto, esperado in [("e2e4", "e2e4"), ("e4", "e2e4"), ("  E2E4 ", "e2e4"),
                            ("Nf3", "g1f3"), ("Cf3", "g1f3"), ("g1f3", "g1f3")]:
        assert assistir.interpretar_lance(board, texto).uci() == esperado, texto
    roque = chess.Board("r3k2r/8/8/8/8/8/8/R3K2R w KQkq - 0 1")
    for texto in ("O-O", "o-o", "0-0"):
        assert assistir.interpretar_lance(roque, texto).uci() == "e1g1", texto
    assert assistir.interpretar_lance(roque, "0-0-0").uci() == "e1c1"
    assert assistir.interpretar_lance(roque, "Td1").uci() == "a1d1"        # torre em português


def test_lance_digitado_recusa_o_que_nao_da_para_entender():
    board = chess.Board()
    for ruim, pedaco in [("", "digite"), ("xyz", "não entendi"), ("e9e9", "não entendi"),
                         ("e7e5", "ilegal"), ("Nf6", "não entendi")]:
        with pytest.raises(ValueError, match=pedaco):
            assistir.interpretar_lance(board, ruim)


def test_lance_digitado_recusa_o_r_ambiguo_em_vez_de_adivinhar():
    """Rf1 é torre em inglês e rei em português. Jogar o errado estragaria a partida."""
    board = chess.Board("4k3/8/8/8/8/8/8/4K2R w K - 0 1")
    with pytest.raises(ValueError, match="ambíguo"):
        assistir.interpretar_lance(board, "Rf1")                           # h1f1 (torre) ou e1f1 (rei)
    assert assistir.interpretar_lance(board, "e1f1").uci() == "e1f1"       # UCI resolve
    assert assistir.interpretar_lance(board, "Rh2").uci() == "h1h2"        # só a torre pode: sem ambiguidade


def test_parar_no_modo_jogar_acorda_e_encerra(servidor):
    porta = servidor(_vis_jogar([]))
    _pedir(porta, "POST", "/nova", {"modo": "jogar", "lado": "pretas", "relogio": "15+10"})
    _esperar(porta, lambda e: e["pensando"] == "brancas")
    inicio = time.monotonic()
    _pedir(porta, "POST", "/parar", {})
    estado = _esperar(porta, lambda e: not e["rodando"])
    assert time.monotonic() - inicio < 3
    assert estado["resultado"] == "*" and estado["motivo"] == "interrompida"


@pytest.mark.skipif(__import__("partida")._achar_stockfish() is None, reason="Stockfish não instalado")
def test_jogar_contra_o_stockfish_de_verdade(servidor, monkeypatch):
    monkeypatch.setenv("CAPABLANCA_THREADS", "2")
    monkeypatch.setenv("CAPABLANCA_HASH_MB", "64")
    porta = servidor(assistir.Visualizador())
    _pedir(porta, "POST", "/nova", {"modo": "jogar", "lado": "pretas", "relogio": "3+2"})
    _esperar(porta, lambda e: e["pensando"] == "brancas", limite=20)
    _pedir(porta, "POST", "/lance", {"uci": "e2e4"})
    estado = _esperar(porta, lambda e: len(e["lances"]) == 2, limite=30)
    resposta = chess.Move.from_uci(estado["lances"][1]["uci"])
    board = chess.Board()
    board.push_uci("e2e4")
    assert resposta in board.legal_moves
    _pedir(porta, "POST", "/parar", {})


# ---- correções da revisão do modo jogar ----

def test_pedido_com_tipo_errado_da_400_e_nao_derruba(servidor):
    porta = servidor(_vis_jogar([]))
    assert _pedir(porta, "POST", "/nova", {"modo": "jogar", "relogio": ["5+3"]})[0] == 400
    assert _pedir(porta, "POST", "/nova", {"oponente": [1]})[0] == 400
    assert _pedir(porta, "GET", "/estado")[0] == 200          # o servidor continua de pé


def test_motor_que_caiu_e_fechado_antes_de_abrir_outro(servidor):
    abertos = []

    def abrir():
        abertos.append(MotorFalso())
        return abertos[-1]

    def escolher(board, motor, perfil, relogio, caminho_book=None, ao_pensar=None, **k):
        lance = chess.Move.from_uci("e2e4")
        return lance, {"book": False, "profundidade": 10, "nos": 1, "avaliacao": 0.1, "pv": [lance],
                       "tempo_s": 0.0, "motor_caiu": True}
    PonderFalso.registro = []
    porta = servidor(assistir.Visualizador(abrir_bot=abrir, escolher=escolher, ponder=PonderFalso))
    _pedir(porta, "POST", "/nova", {"modo": "jogar", "lado": "brancas", "relogio": "5+3"})
    _esperar(porta, lambda e: len(e["lances"]) == 1)
    assert len(abertos) == 2 and abertos[0].fechado is True   # o motor antigo foi fechado


def test_parar_o_ponder_nao_conta_no_relogio_do_humano(servidor):
    class PonderLento(PonderFalso):
        def parar(self):
            time.sleep(0.6)            # o bot demora para parar de pensar
            return True
    PonderFalso.registro = []
    porta = servidor(assistir.Visualizador(abrir_bot=MotorFalso, escolher=_escolher_falso(["e7e5"]), ponder=PonderLento))
    _pedir(porta, "POST", "/nova", {"modo": "jogar", "lado": "pretas", "relogio": "5+3"})
    _esperar(porta, lambda e: e["pensando"] == "brancas")
    _pedir(porta, "POST", "/lance", {"uci": "e2e4"})
    estado = _esperar(porta, lambda e: len(e["lances"]) == 2)
    # 300 - (o que o humano demorou, bem menos de 0,6 s) + 3 de incremento
    assert estado["relogios"]["brancas"] > 302.5


def test_lance_do_bot_sem_analise_nao_entra_no_grafico(servidor):
    def escolher_book(board, motor, perfil, relogio, caminho_book=None, ao_pensar=None, **k):
        lance = chess.Move.from_uci("e2e4")
        return lance, {"book": True, "profundidade": 0, "nos": 0, "avaliacao": 0.0, "pv": [lance],
                       "tempo_s": 0.0, "motor_caiu": False}
    PonderFalso.registro = []
    porta = servidor(assistir.Visualizador(abrir_bot=MotorFalso, escolher=escolher_book, ponder=PonderFalso))
    _pedir(porta, "POST", "/nova", {"modo": "jogar", "lado": "brancas", "relogio": "5+3"})
    estado = _esperar(porta, lambda e: len(e["lances"]) == 1)
    assert estado["avaliacoes"] == []
