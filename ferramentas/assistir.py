"""Visualizador no navegador: assista o nosso bot jogando contra outro bot, ao vivo. Dono: Junio.

    python ferramentas/assistir.py            # abre http://127.0.0.1:8765 no navegador
    python ferramentas/assistir.py --porta 9000 --sem-navegador

IMPORTANTE
  - É uma ferramenta para TESTAR e APRESENTAR (inclusive na arguição). Nas partidas oficiais o
    programa da mesa é o partida.py, só no terminal (regra do torneio).
  - Funciona SEM internet: o servidor só escuta no próprio computador (127.0.0.1), usa só a
    biblioteca padrão do Python e a página não carrega nada de fora.

COMO FUNCIONA
  A partida é jogada pelo mesmo simulador dos confrontos (testes/torneio.py), com relógio simulado
  e atraso humano. O "nosso" lado é o programa de verdade (partida.escolher_lance + tempo.py). Um
  observador registra cada lance e o que o nosso bot está pensando; a página consulta /estado
  algumas vezes por segundo e desenha tabuleiro, relógios, avaliação e a linha principal.
"""
import argparse
import json
import os
import random
import sys
import threading
import time
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if RAIZ not in sys.path:
    sys.path.insert(0, RAIZ)

import chess

import partida
from testes import torneio

PAGINA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assistir.html")
PORTA_PADRAO = 8765
HASH_POR_MOTOR_MB = 256

OPONENTES = {
    "padrao": "Stockfish (gestão de tempo dele)",
    "fraco": f"Bot fraco (Stockfish nível {torneio.NIVEL_FRACO})",
    "fixa": "Stockfish com tempo fixo por lance",
}
# controle -> (perfil, escala, rótulo). A escala encurta o relógio para dar para assistir.
CONTROLES = {
    "rapido": ("15+10", 0.2, "Rápido: 15+10 em escala 0,2 (3 min + 2 s)"),
    "torneio": ("15+10", 1.0, "Torneio: 15 min + 10 s (relógio real)"),
    "rapido25": ("25+0", 0.2, "Rápido: 25+0 em escala 0,2 (5 min)"),
}
LADOS = ("brancas", "pretas")
TEMPO_FIXO_REAL_S = 10.0   # só para o oponente "fixa": referência de teste, não vale para a mesa
TAMANHO_MAXIMO_PEDIDO = 4096   # bytes: os pedidos da página são minúsculos
# Proteções do navegador: a página não pode ser embutida em outro site nem carregar nada de fora.
CABECALHOS_SEGURANCA = {
    "X-Frame-Options": "DENY",
    "X-Content-Type-Options": "nosniff",
    "Content-Security-Policy": ("default-src 'self'; style-src 'self' 'unsafe-inline'; "
                                "script-src 'self' 'unsafe-inline'; img-src 'self' data:; frame-ancestors 'none'"),
}


def _aval_brancas(avaliacao, vez):
    """Avaliação do ponto de vista de quem joga (peões ou "#n") -> {cp, mate} do ponto de vista das brancas."""
    sinal = 1 if vez == chess.WHITE else -1
    if isinstance(avaliacao, str) and avaliacao.startswith("#"):
        try:
            return {"cp": None, "mate": sinal * int(avaliacao[1:])}
        except ValueError:
            return {"cp": None, "mate": None}
    if partida._numero_finito(avaliacao):
        return {"cp": round(sinal * avaliacao * 100), "mate": None}
    return {"cp": None, "mate": None}


def _pv_em_san(board, pv):
    """Linha principal em notação legível (Cf3 e5...), a partir de uma cópia do tabuleiro."""
    copia, saida = board.copy(stack=False), []
    for lance in pv[:12]:
        if lance not in copia.legal_moves:
            break
        saida.append(copia.san(lance))
        copia.push(lance)
    return saida


class Estado:
    """Tudo que a página mostra. Protegido por um lock: a partida escreve, o servidor lê."""

    def __init__(self):
        self.lock = threading.Lock()
        self.dados = self._vazio()

    @staticmethod
    def _vazio():
        return {"rodando": False, "fen": chess.STARTING_FEN, "ultimo": None, "lances": [], "relogios": None,
                "pensando": None, "pensando_desde": None, "nosso_lado": "brancas", "oponente": None,
                "controle": None, "info": None, "avaliacoes": [], "resultado": None, "motivo": None,
                "erro": None, "abertura": [], "nomes": None}

    def reiniciar(self, **campos):
        with self.lock:
            self.dados = self._vazio()
            self.dados.update(campos)

    def atualizar(self, **campos):
        with self.lock:
            self.dados.update(campos)

    def acrescentar(self, chave, valor):
        with self.lock:
            self.dados[chave] = self.dados[chave] + [valor]

    def copia(self):
        with self.lock:
            dados = json.loads(json.dumps(self.dados))
        dados["agora"] = time.time()
        return dados


class Observador:
    """Recebe os avisos do simulador e do nosso bot e grava no Estado."""

    def __init__(self, estado, nossa_cor, ativo=lambda: True):
        self.estado = estado
        self.nossa_cor = nossa_cor
        self.tabuleiro_pensando = None
        self.ativo = ativo   # False quando esta partida já foi substituída ou parada: não escreve mais

    @staticmethod
    def _relogios(relogios):
        return {"brancas": relogios[chess.WHITE].restante, "pretas": relogios[chess.BLACK].restante}

    def inicio_lance(self, board, cor, relogios):
        if not self.ativo():
            return
        self.tabuleiro_pensando = board.copy(stack=False)
        self.estado.atualizar(pensando="brancas" if cor == chess.WHITE else "pretas", pensando_desde=time.time(),
                              relogios=self._relogios(relogios), info=None if cor == self.nossa_cor else
                              self.estado.copia()["info"])

    def ao_pensar(self, dados):
        board = self.tabuleiro_pensando
        if board is None or not self.ativo():
            return
        self.estado.atualizar(info={
            "profundidade": dados["profundidade"], "nos": dados["nos"], "decorrido": dados["decorrido"],
            "avaliacao": _aval_brancas(dados["avaliacao"], board.turn), "pv": _pv_em_san(board, dados["pv"])})

    def fim_lance(self, board, lance, pensou, relogios):
        if not self.ativo():
            return
        anterior = board.copy()
        anterior.pop()
        cor = "brancas" if anterior.turn == chess.WHITE else "pretas"
        self.estado.acrescentar("lances", {"san": anterior.san(lance), "uci": lance.uci(), "cor": cor,
                                           "tempo": round(pensou, 2)})
        info = self.estado.copia()["info"]
        if anterior.turn == self.nossa_cor and info:
            self.estado.acrescentar("avaliacoes", {"lance": len(self.estado.copia()["lances"]), **info["avaliacao"]})
        self.estado.atualizar(fen=board.fen(), ultimo=lance.uci(), relogios=self._relogios(relogios),
                              pensando=None, pensando_desde=None)

    def fim_partida(self, resumo):
        if not self.ativo():
            return
        self.estado.atualizar(resultado=resumo["resultado"], motivo=resumo["motivo"], pensando=None,
                              pensando_desde=None)


def abrir_jogadores_reais(oponente, perfil, escala, ao_pensar):
    """Abre os dois Stockfish (cada um com metade das threads da máquina) e devolve (nosso, outro, fechar)."""
    caminho = partida._achar_stockfish()
    if caminho is None:
        raise FileNotFoundError("Stockfish não encontrado em stockfish/ (veja o README)")
    threads = max(1, partida.threads_automaticas() // 2)
    pasta_tb = partida.PASTA_TABLEBASES if os.path.isdir(partida.PASTA_TABLEBASES) else None
    motores = []
    try:
        motores.append(partida.abrir_motor(caminho, threads, HASH_POR_MOTOR_MB, pasta_tb))
        motores.append(partida.abrir_motor(caminho, threads, HASH_POR_MOTOR_MB, pasta_tb))
    except Exception:
        for motor in motores:
            motor.quit()
        raise
    nosso = torneio.JogadorNossa(motores[0], perfil)
    nosso.ao_pensar = ao_pensar
    outro = torneio._criar_jogador(oponente, motores[1], perfil, TEMPO_FIXO_REAL_S * escala)

    def fechar():
        for motor in motores:
            try:
                motor.close()   # close (e não quit): também serve para interromper uma busca em andamento
            except Exception:
                pass
    return nosso, outro, fechar


class Visualizador:
    """Uma partida por vez, numa linha de execução de fundo."""

    def __init__(self, abrir_jogadores=abrir_jogadores_reais, atraso_real_s=12.0):
        self.estado = Estado()
        self.abrir_jogadores = abrir_jogadores
        self.atraso_real_s = atraso_real_s
        self.cancelar = threading.Event()
        self.fechar_motores = None
        self.fio = None
        self.geracao = 0                # cada partida nova ganha um número; só a atual escreve no Estado
        self.trava = threading.RLock()  # "Nova partida" e "Parar" nunca rodam ao mesmo tempo

    @staticmethod
    def validar(pedido):
        oponente = pedido.get("oponente", "padrao")
        controle = pedido.get("controle", "rapido")
        lado = pedido.get("lado", "brancas")
        if oponente not in OPONENTES:
            raise ValueError(f"oponente inválido: {oponente!r}")
        if controle not in CONTROLES:
            raise ValueError(f"controle inválido: {controle!r}")
        if lado not in LADOS:
            raise ValueError(f"lado inválido: {lado!r}")
        return oponente, controle, lado

    def nova(self, pedido):
        oponente, controle, lado = self.validar(pedido)
        with self.trava:
            self._parar_partida_atual()
            self.geracao += 1
            self.cancelar = threading.Event()
            perfil, escala, rotulo = CONTROLES[controle]
            abertura = torneio.sortear_aberturas(1, random.randrange(10 ** 6))[0]
            nomes = {lado: "Capablanca (nosso)", ("pretas" if lado == "brancas" else "brancas"): OPONENTES[oponente]}
            self.estado.reiniciar(rodando=True, nosso_lado=lado, oponente=OPONENTES[oponente], controle=rotulo,
                                  abertura=[m.uci() for m in abertura], nomes=nomes)
            self.fio = threading.Thread(target=self._jogar, daemon=True,
                                        args=(oponente, perfil, escala, lado, abertura, self.cancelar, self.geracao))
            self.fio.start()

    def _jogar(self, oponente, perfil, escala, lado, abertura, cancelar, geracao):
        nossa_cor = chess.WHITE if lado == "brancas" else chess.BLACK
        ativa = lambda: self.geracao == geracao   # partida substituída não escreve mais na tela
        observador = Observador(self.estado, nossa_cor, ativo=ativa)
        board = chess.Board()
        for lance in abertura:   # a abertura sorteada aparece na lista, sem custo de relógio
            self.estado.acrescentar("lances", {"san": board.san(lance), "uci": lance.uci(),
                                               "cor": "brancas" if board.turn else "pretas", "tempo": 0, "abertura": True})
            board.push(lance)
        self.estado.atualizar(fen=board.fen(), ultimo=abertura[-1].uci() if abertura else None)
        fechar = None
        try:
            torneio.aplicar_escala_no_tempo(escala)
            nosso, outro, fechar = self.abrir_jogadores(oponente, perfil, escala, observador.ao_pensar)
            if ativa():
                self.fechar_motores = fechar
            branco, preto = (nosso, outro) if nossa_cor == chess.WHITE else (outro, nosso)
            torneio.jogar_partida(branco, preto, abertura, perfil, self.atraso_real_s * escala, escala,
                                  observador=observador, cancelar=cancelar)
        except Exception as erro:
            if ativa():
                if cancelar.is_set():
                    self.estado.atualizar(resultado="*", motivo="interrompida")
                else:
                    self.estado.atualizar(erro=f"{type(erro).__name__}: {erro}", resultado="*", motivo="erro")
        finally:
            if fechar is not None:
                fechar()
            if ativa():
                self.estado.atualizar(rodando=False, pensando=None, pensando_desde=None)

    def parar(self):
        with self.trava:
            self._parar_partida_atual()

    def _parar_partida_atual(self):
        """Só com a trava na mão. Para a partida em andamento (se houver) e espera ela terminar."""
        fio, fechar = self.fio, self.fechar_motores
        self.cancelar.set()
        if fechar is not None:
            fechar()   # interrompe na hora uma busca longa
        if fio is not None:
            fio.join(timeout=10)
        self.fio = None
        self.fechar_motores = None


def _criar_manipulador(visualizador):
    class Manipulador(BaseHTTPRequestHandler):
        def log_message(self, *args):   # silencioso: não polui o terminal
            pass

        def _local(self):
            """Só aceita pedidos endereçados ao próprio computador."""
            host = (self.headers.get("Host") or "").split(":")[0]
            return host in ("127.0.0.1", "localhost")

        def _origem_ok(self):
            """Navegador manda Origin nos POST: só aceita a própria página do visualizador."""
            origem = self.headers.get("Origin")
            if origem is None:
                return True   # pedido que não veio de navegador (ex.: curl, testes)
            porta = self.server.server_address[1]
            return origem in (f"http://127.0.0.1:{porta}", f"http://localhost:{porta}")

        def _caminho(self):
            return urlsplit(self.path).path

        def _responder(self, codigo, corpo, tipo="application/json; charset=utf-8"):
            dados = corpo if isinstance(corpo, bytes) else json.dumps(corpo, ensure_ascii=False).encode("utf-8")
            self.send_response(codigo)
            self.send_header("Content-Type", tipo)
            self.send_header("Content-Length", str(len(dados)))
            self.send_header("Cache-Control", "no-store")
            for nome, valor in CABECALHOS_SEGURANCA.items():
                self.send_header(nome, valor)
            self.end_headers()
            self.wfile.write(dados)

        def do_GET(self):
            if not self._local():
                return self._responder(403, {"erro": "só acesso local"})
            caminho = self._caminho()
            if caminho in ("/", "/index.html"):
                with open(PAGINA, "rb") as arquivo:
                    return self._responder(200, arquivo.read(), "text/html; charset=utf-8")
            if caminho == "/estado":
                return self._responder(200, visualizador.estado.copia())
            if caminho == "/opcoes":
                return self._responder(200, {"oponentes": OPONENTES, "lados": list(LADOS),
                                             "atraso_s": visualizador.atraso_real_s,
                                             "controles": {k: v[2] for k, v in CONTROLES.items()}})
            return self._responder(404, {"erro": "não encontrado"})

        def do_POST(self):
            if not self._local() or not self._origem_ok():
                return self._responder(403, {"erro": "só a página do visualizador pode mandar comandos"})
            # Exigir JSON obriga o navegador a pedir permissão antes (preflight), o que um site estranho não consegue.
            if not (self.headers.get("Content-Type") or "").startswith("application/json"):
                return self._responder(415, {"erro": "envie application/json"})
            try:
                tamanho = int(self.headers.get("Content-Length") or 0)
            except ValueError:
                return self._responder(400, {"erro": "Content-Length inválido"})
            if tamanho < 0 or tamanho > TAMANHO_MAXIMO_PEDIDO:
                return self._responder(413, {"erro": "pedido grande demais"})
            try:
                pedido = json.loads(self.rfile.read(tamanho) or b"{}") if tamanho else {}
                if not isinstance(pedido, dict):
                    raise ValueError("corpo precisa ser um objeto JSON")
            except ValueError as erro:
                return self._responder(400, {"erro": f"JSON inválido: {erro}"})
            caminho = self._caminho()
            if caminho == "/nova":
                try:
                    visualizador.nova(pedido)
                except ValueError as erro:
                    return self._responder(400, {"erro": str(erro)})
                return self._responder(200, {"ok": True})
            if caminho == "/parar":
                visualizador.parar()
                return self._responder(200, {"ok": True})
            return self._responder(404, {"erro": "não encontrado"})
    return Manipulador


def criar_servidor(visualizador, porta=PORTA_PADRAO):
    """Servidor só em 127.0.0.1. Se a porta estiver ocupada, usa qualquer porta livre."""
    manipulador = _criar_manipulador(visualizador)
    try:
        return ThreadingHTTPServer(("127.0.0.1", porta), manipulador)
    except OSError:
        return ThreadingHTTPServer(("127.0.0.1", 0), manipulador)


def main(argv=None):
    parser = argparse.ArgumentParser(description="Assista o nosso bot jogando contra outro bot, no navegador.")
    parser.add_argument("--porta", type=int, default=PORTA_PADRAO)
    parser.add_argument("--sem-navegador", action="store_true", help="não abre o navegador sozinho")
    parser.add_argument("--atraso-s", type=float, default=12.0,
                        help="atraso humano simulado por lance, em segundos reais (padrão: 12, medido no ensaio)")
    args = parser.parse_args(argv)
    visualizador = Visualizador(atraso_real_s=args.atraso_s)
    servidor = criar_servidor(visualizador, args.porta)
    endereco = f"http://127.0.0.1:{servidor.server_address[1]}/"
    print(f"Visualizador em {endereco}  (Ctrl+C para fechar)")
    if not args.sem_navegador:
        threading.Timer(0.5, lambda: webbrowser.open(endereco)).start()
    try:
        servidor.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        visualizador.parar()
        servidor.server_close()
        print("Visualizador fechado.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
