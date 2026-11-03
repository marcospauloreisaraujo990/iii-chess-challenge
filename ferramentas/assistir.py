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
import queue
import random
import re
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
import tempo
from testes import torneio

PAGINA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assistir.html")
PORTA_PADRAO = 8765
HASH_POR_MOTOR_MB = 256

OPONENTES = {
    "padrao": "Stockfish (gestão de tempo dele)",
    "lichess8": f"Lichess nível 8 (prof. {torneio.LICHESS8_PROFUNDIDADE}, {torneio.LICHESS8_TEMPO_S:g} s)",
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
# Modo "jogar contra o bot": relógios de verdade, como nos sites. (inicial em s, incremento em s)
#
# "ilimitado" é o modo SEM TEMPO: ninguém perde por bandeira, dos dois lados. O relógio do bot NÃO
# anda: o tempo.py recebe sempre o mesmo restante, então o bot pensa o mesmo em todo lance e a
# partida nunca acaba por tempo. É o modo para usar a tela como PONTE, quando o relógio de verdade
# está em outro lugar (Lichess, cronômetro da mesa) e o nosso relógio só atrapalharia.
#
# A base é o 5+3 porque é a que dá o ritmo do torneio. Medido com tempo.calcular_tempo(atraso 0),
# alvo e máximo por lance: 5+3 -> 6 a 8 s (máx. 15 a 21 s); 15+10 -> 19 a 26 s (máx. 48 a 66 s,
# lento demais para ponte: estouraria o relógio do outro lado); 3+2 -> 4 a 5 s (máx. 9 a 13 s).
RELOGIO_ILIMITADO = "ilimitado"
RELOGIOS_JOGAR = {"3+2": (180, 2), "5+3": (300, 3), "10+5": (600, 5), "15+10": (900, 10), "25+0": (1500, 0),
                  RELOGIO_ILIMITADO: (300, 3)}
ATRASOS_JOGAR = (0, 6, 12)   # atraso humano simulado do nosso bot; na tela não há mesa, então o padrão é 0
NOME_HUMANO = "Você (ou o bot da outra máquina)"

# Letras das peças em português -> inglês, para aceitar o lance como ele aparece numa tela em
# português (Lichess, Chess.com). "B" é bispo nas duas línguas. O "R" é ambíguo (Rei em português,
# Rook/torre em inglês), então o texto é tentado primeiro SEM tradução: "Rd1" vale torre, como no
# padrão internacional.
LETRAS_PT = {"D": "Q", "C": "N", "T": "R", "R": "K"}
_ROQUE = re.compile(r"^[0oO]-[0oO](-[0oO])?$")
TEMPO_FIXO_REAL_S = 10.0   # só para o oponente "fixa": referência de teste, não vale para a mesa
TAMANHO_MAXIMO_PEDIDO = 4096   # bytes: os pedidos da página são minúsculos
# Proteções do navegador: a página não pode ser embutida em outro site nem carregar nada de fora.
CABECALHOS_SEGURANCA = {
    "X-Frame-Options": "DENY",
    "X-Content-Type-Options": "nosniff",
    "Content-Security-Policy": ("default-src 'self'; style-src 'self' 'unsafe-inline'; "
                                "script-src 'self' 'unsafe-inline'; img-src 'self' data:; frame-ancestors 'none'"),
}


def interpretar_lance(board, texto):
    """Texto digitado -> chess.Move legal nesta posição. ValueError com explicação se não der.

    Aceita as três formas que aparecem nas telas de xadrez, para a pessoa poder copiar o lance
    do outro programa sem traduzir nada:
        UCI  : e2e4, e1g1 (roque), e7e8q (promoção)   <- o formato da mesa do torneio
        SAN  : e4, Nf3, exd5, O-O, e8=Q
        SAN em português: Cf3, Txd5, Dh5, O-O
    """
    texto = str(texto).strip()
    if not texto:
        raise ValueError("digite um lance (exemplo: e2e4)")
    if _ROQUE.match(texto):
        texto = texto.upper().replace("0", "O")
    try:
        lance = chess.Move.from_uci(texto.lower())
    except ValueError:
        pass                      # não é UCI; tentamos SAN abaixo
    else:
        if lance in board.legal_moves:
            return lance
        raise ValueError(f"lance ilegal nesta posição: {texto}")
    traduzido = LETRAS_PT.get(texto[0], texto[0]) + texto[1:]
    lances = []
    for versao in (texto, traduzido):
        try:
            lances.append(board.parse_san(versao))   # parse_san só devolve lance legal
        except ValueError:
            pass
    if not lances:
        raise ValueError(f"não entendi o lance: {texto} (use e2e4, Cf3 ou Nf3)")
    if len(lances) == 2 and lances[0] != lances[1]:
        # Só acontece com "R": Rd1 é torre em inglês e rei em português, e as duas são legais.
        # Em vez de adivinhar e jogar o lance errado, pedimos o formato sem ambiguidade.
        raise ValueError(f"{texto} é ambíguo (torre em inglês, rei em português): "
                         f"escreva em UCI, {lances[0].uci()} ou {lances[1].uci()}")
    return lances[0]


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
                "erro": None, "abertura": [], "nomes": None, "modo": "assistir", "legais": [], "xeque": None}

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
    """Abre os dois Stockfish e devolve (nosso, outro, fechar).

    Cada motor fica com metade das threads da máquina MENOS 2 no total, que ficam livres para o
    navegador desenhar a tela sem travar.
    """
    caminho = partida._achar_stockfish()
    if caminho is None:
        raise FileNotFoundError("Stockfish não encontrado em stockfish/ (veja o README)")
    threads = max(1, (partida._threads_da_maquina() - 2) // 2)
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


def abrir_bot_real():
    """Abre o nosso bot para o modo jogar: as threads configuradas MENOS 2 (folga para o navegador)."""
    caminho = partida._achar_stockfish()
    if caminho is None:
        raise FileNotFoundError("Stockfish não encontrado em stockfish/ (veja o README)")
    threads, hash_mb, _ = partida.configuracao_do_motor()
    pasta_tb = partida.PASTA_TABLEBASES if os.path.isdir(partida.PASTA_TABLEBASES) else None
    return partida.abrir_motor(caminho, max(1, threads - 2), hash_mb, pasta_tb)


class Visualizador:
    """Uma partida por vez, numa linha de execução de fundo."""

    def __init__(self, abrir_jogadores=abrir_jogadores_reais, atraso_real_s=12.0, abrir_bot=abrir_bot_real,
                 escolher=None, ponder=None):
        self.estado = Estado()
        self.abrir_jogadores = abrir_jogadores
        # Modo jogar: o bot de verdade é partida.escolher_lance + partida.Ponder (injetáveis nos testes).
        self.abrir_bot = abrir_bot
        self.escolher = escolher or partida.escolher_lance
        self.ponder = ponder or partida.Ponder
        self.fila_humano = queue.Queue()
        self.tabuleiro_humano = None    # cópia da posição quando é a vez do humano (para validar o lance)
        self.trava_lance = threading.Lock()
        self.atraso_real_s = atraso_real_s
        self.cancelar = threading.Event()
        self.fechar_motores = None
        self.fio = None
        self.geracao = 0                # cada partida nova ganha um número; só a atual escreve no Estado
        self.trava = threading.RLock()  # "Nova partida" e "Parar" nunca rodam ao mesmo tempo

    @staticmethod
    def validar(pedido):
        if any(not isinstance(pedido.get(k, ""), str) for k in ("oponente", "controle", "lado")):
            raise ValueError("oponente, controle e lado precisam ser texto")
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

    @staticmethod
    def validar_jogar(pedido):
        if any(not isinstance(pedido.get(k, ""), str) for k in ("lado", "relogio")):
            raise ValueError("lado e relógio precisam ser texto")
        lado = pedido.get("lado", "pretas")
        relogio = pedido.get("relogio", "5+3")
        try:
            atraso = float(pedido.get("atraso", 0))
        except (TypeError, ValueError):
            raise ValueError("atraso inválido")
        if lado not in LADOS:
            raise ValueError(f"lado inválido: {lado!r}")
        if relogio not in RELOGIOS_JOGAR:
            raise ValueError(f"relógio inválido: {relogio!r}")
        if atraso not in ATRASOS_JOGAR:
            raise ValueError(f"atraso inválido: {atraso!r}")
        return lado, relogio, atraso

    def nova(self, pedido):
        if pedido.get("modo") == "jogar":
            return self.nova_jogar(pedido)
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

    # ------------------------------------------------------------------ modo jogar
    def nova_jogar(self, pedido):
        lado, relogio, atraso = self.validar_jogar(pedido)
        with self.trava:
            self._parar_partida_atual()
            self.geracao += 1
            self.cancelar = threading.Event()
            self.fila_humano = queue.Queue()
            humano = "pretas" if lado == "brancas" else "brancas"
            inicio, incremento = RELOGIOS_JOGAR[relogio]
            ilimitado = relogio == RELOGIO_ILIMITADO
            self.estado.reiniciar(rodando=True, modo="jogar", nosso_lado=lado, oponente=NOME_HUMANO,
                                  controle=("sem limite de tempo" if ilimitado else f"{relogio} (relógio real)"),
                                  nomes={lado: "Capablanca (nosso bot)", humano: NOME_HUMANO},
                                  relogios=(None if ilimitado
                                            else {"brancas": float(inicio), "pretas": float(inicio)}))
            self.fio = threading.Thread(target=self._jogar_humano, daemon=True,
                                        args=(lado, inicio, incremento, atraso, self.cancelar, self.geracao,
                                              self.fila_humano, ilimitado))
            self.fio.start()

    def lance_humano(self, uci):
        """Recebe o lance do lado humano (UCI ou SAN). Erro (ValueError) se não for a vez dele ou se for ilegal."""
        with self.trava_lance:
            board = self.tabuleiro_humano
            if board is None:
                raise ValueError("não é a sua vez")
            lance = interpretar_lance(board, uci)
            self.tabuleiro_humano = None   # um lance por vez
            self.fila_humano.put(("lance", lance))

    def desistir(self):
        with self.trava_lance:
            if self.estado.copia()["modo"] != "jogar" or not self.estado.copia()["rodando"]:
                raise ValueError("não há partida para desistir")
            self.tabuleiro_humano = None
            self.fila_humano.put(("desistir", None))

    def _jogar_humano(self, lado, inicio, incremento, atraso, cancelar, geracao, fila, ilimitado=False):
        bot = chess.WHITE if lado == "brancas" else chess.BLACK
        nome = {chess.WHITE: "brancas", chess.BLACK: "pretas"}
        ativa = lambda: self.geracao == geracao
        observador = Observador(self.estado, bot, ativo=ativa)
        board = chess.Board()
        restante = {chess.WHITE: float(inicio), chess.BLACK: float(inicio)}
        caminho_book = partida.CAMINHO_BOOK if os.path.isfile(partida.CAMINHO_BOOK) else None
        motor = None
        resultado = motivo = None
        historico_aval = []   # avaliações dos lances do bot, para o modo economia do tempo.py

        def mostrar(**extra):
            if ativa():
                self.estado.atualizar(fen=board.fen(),
                                      relogios=(None if ilimitado else {"brancas": restante[chess.WHITE],
                                                                        "pretas": restante[chess.BLACK]}),
                                      xeque=(chess.square_name(board.king(board.turn))
                                             if board.is_check() and board.king(board.turn) is not None else None),
                                      **extra)
        try:
            motor = self.abrir_bot()
            if ativa():
                self.fechar_motores = motor.close
            while resultado is None:
                if cancelar.is_set():
                    resultado, motivo = "*", "interrompida"
                    break
                fim = board.outcome(claim_draw=True)
                if fim is not None:
                    resultado, motivo = fim.result(), fim.termination.name.lower()
                    break
                cor = board.turn
                inicio_vez = time.monotonic()
                if cor == bot:
                    mostrar(pensando=nome[cor], pensando_desde=time.time(), legais=[])
                    observador.tabuleiro_pensando = board.copy(stack=False)
                    # o mesmo cálculo do partida.py e do simulador: a tela tem que ser réplica da mesa
                    try:
                        economia = bool(tempo.modo_economia(historico_aval,
                                                            tempo.material_em_centipawns(board)))
                    except Exception:   # bug no código de tempo não pode derrubar a partida
                        economia = False
                    lance, info = self.escolher(
                        board, motor, "visualizador",
                        {"restante_s": restante[cor], "incremento_s": incremento, "atraso_humano_s": atraso},
                        caminho_book=caminho_book, economia=economia, ao_pensar=observador.ao_pensar)
                    aval_bot = info.get("avaliacao")
                    historico_aval.append(round(aval_bot * 100)
                                          if partida._numero_finito(aval_bot) and info.get("profundidade", 0) > 0
                                          else None)
                    if cancelar.is_set():
                        resultado, motivo = "*", "interrompida"
                        break
                    gasto = time.monotonic() - inicio_vez + atraso   # o atraso simula o tempo da mesa
                    analisou = info.get("profundidade", 0) > 0
                    if info.get("motor_caiu"):
                        try:
                            motor.close()          # nunca deixar o processo antigo aberto
                        except Exception:
                            pass
                        motor = self.abrir_bot()   # o lance devolvido vale; o motor é trocado
                        if ativa():
                            self.fechar_motores = motor.close
                    if ativa() and info.get("avaliacao") is not None and info.get("profundidade", 0) > 0:
                        self.estado.atualizar(info={"profundidade": info["profundidade"], "nos": info["nos"],
                                                    "decorrido": info["tempo_s"],
                                                    "avaliacao": _aval_brancas(info["avaliacao"], cor),
                                                    "pv": _pv_em_san(board, info["pv"])})
                else:
                    with self.trava_lance:
                        if ativa():
                            self.tabuleiro_humano = board.copy()
                    mostrar(pensando=nome[cor], pensando_desde=time.time(),
                            legais=[l.uci() for l in board.legal_moves])
                    pensador = self.ponder(motor, board)   # o bot pensa no seu tempo, como na mesa
                    try:
                        # sem limite: espera o lance para sempre, nunca cai a bandeira
                        item = fila.get(timeout=None if ilimitado else max(0.0, restante[cor]))
                        chegou = time.monotonic()   # o relógio do humano para aqui
                    except queue.Empty:
                        item = ("tempo", None)
                        chegou = time.monotonic()
                    finally:
                        if not pensador.parar():
                            motor.close()
                            motor = self.abrir_bot()
                            if ativa():
                                self.fechar_motores = motor.close
                        with self.trava_lance:
                            if ativa():
                                self.tabuleiro_humano = None
                    gasto = chegou - inicio_vez
                    tipo, lance = item
                    if tipo == "parar" or cancelar.is_set():
                        resultado, motivo = "*", "interrompida"
                        break
                    if tipo == "desistir":
                        resultado, motivo = ("1-0" if cor == chess.BLACK else "0-1"), "desistencia"
                        break
                    if tipo == "tempo":
                        gasto = restante[cor] + 0.001
                if not ilimitado:
                    restante[cor] -= gasto
                    if restante[cor] <= 0:
                        restante[cor] = 0.0
                        if board.has_insufficient_material(not cor):
                            resultado, motivo = "1/2-1/2", "tempo-sem-material"
                        else:
                            resultado, motivo = ("0-1" if cor == chess.WHITE else "1-0"), "tempo"
                        break
                    restante[cor] += incremento
                san = board.san(lance)
                board.push(lance)
                if ativa():
                    self.estado.acrescentar("lances", {"san": san, "uci": lance.uci(), "cor": nome[cor],
                                                       "tempo": round(gasto, 2)})
                    if cor == bot and analisou:
                        info_atual = self.estado.copia()["info"]
                        if info_atual:
                            self.estado.acrescentar("avaliacoes", {"lance": len(board.move_stack),
                                                                   **info_atual["avaliacao"]})
                mostrar(ultimo=lance.uci(), pensando=None, pensando_desde=None, legais=[])
        except Exception as erro:
            if ativa():
                if cancelar.is_set():
                    resultado, motivo = "*", "interrompida"
                else:
                    self.estado.atualizar(erro=f"{type(erro).__name__}: {erro}")
                    resultado, motivo = "*", "erro"
        finally:
            with self.trava_lance:
                if ativa():
                    self.tabuleiro_humano = None
            if motor is not None:
                try:
                    motor.close()
                except Exception:
                    pass
            if ativa():
                mostrar(resultado=resultado, motivo=motivo, rodando=False, pensando=None,
                        pensando_desde=None, legais=[])

    def parar(self):
        with self.trava:
            self._parar_partida_atual()

    def _parar_partida_atual(self):
        """Só com a trava na mão. Para a partida em andamento (se houver) e espera ela terminar."""
        fio, fechar = self.fio, self.fechar_motores
        self.cancelar.set()
        self.fila_humano.put(("parar", None))   # acorda o modo jogar, que pode estar esperando o humano
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
                                             "relogios_jogar": list(RELOGIOS_JOGAR), "atrasos_jogar": list(ATRASOS_JOGAR),
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
                except (ValueError, TypeError) as erro:
                    return self._responder(400, {"erro": str(erro)})
                return self._responder(200, {"ok": True})
            if caminho == "/parar":
                visualizador.parar()
                return self._responder(200, {"ok": True})
            if caminho in ("/lance", "/desistir"):
                try:
                    if caminho == "/lance":
                        visualizador.lance_humano(pedido.get("uci", ""))
                    else:
                        visualizador.desistir()
                except ValueError as erro:
                    return self._responder(409, {"erro": str(erro)})
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
