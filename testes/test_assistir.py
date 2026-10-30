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
