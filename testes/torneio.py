"""Partidas automáticas entre versões do programa, com relógio simulado. Dono: Léo.

PARA QUE SERVE
  Responde, com números, as perguntas da arguição técnica:
    - A nossa gestão de tempo (tempo.py) joga melhor do que um tempo fixo por lance?
    - E do que a gestão que o próprio Stockfish já traz?
    - Alguma versão perde por tempo? (é a métrica mais importante: estourar = derrota)
  E dá a evidência para calibrar os números de tempo.py e a folga do watchdog.

AS TRÊS VERSÕES (todas usam o MESMO Stockfish, com as mesmas threads e o mesmo hash)
    nossa   o nosso código de verdade: partida.escolher_lance, que usa tempo.calcular_tempo,
            tempo.deve_parar e o modo economia do tempo.py.
    fixa    pensa sempre o mesmo tempo por lance (parâmetro --tempo-fixo). Referência simples.
    padrao  deixa o Stockfish gerenciar o próprio relógio (comando "go wtime btime winc binc").

COMO O RELÓGIO SIMULADO FUNCIONA
    A cada lance: tempo real que o motor levou + atraso artificial (o tempo que a equipe
    gasta na mesa: anunciar, mover, apertar o relógio) é descontado. Se o relógio chega a
    zero ou menos, é derrota por tempo. Se sobrou tempo, soma o incremento.
    O atraso vale para as TRÊS versões, para a comparação ser justa.

ESCALA (--escala, padrão 0.2)
    Uma partida real de 15+10 leva mais de uma hora. Para simular em minutos, o controle, o
    atraso e as constantes de tempo ABSOLUTAS do tempo.py (RESERVA_MINIMA_S, RESERVA_MAXIMA_S,
    TEMPO_MINIMO_S) são multiplicados pela mesma escala, só dentro do simulador. O arquivo
    tempo.py não é alterado. Com escala 0.2, 15+10 vira 180 s + 2 s por lance.
    Honestidade: o motor pensa menos nessa escala, então o resultado serve para COMPARAR
    versões e CALIBRAR números, não prova o comportamento exato no relógio real.

COMO RODAR
    python testes/torneio.py confronto --a nossa --b padrao --perfil 15+10 --partidas 20 \\
           --atraso-s 6 --tempo-fixo 12
    python testes/torneio.py estouro            # mede o estouro do Limit(time=...) do motor
    (--atraso-s é OBRIGATÓRIO e não tem valor padrão: vem da medição na mesa.)

Aberturas variadas (linhas da mesma base CC0 do book), cores alternadas, e cada abertura é
jogada duas vezes com as cores trocadas.
"""
import argparse
import concurrent.futures
import csv
import io
import math
import multiprocessing
import os
import random
import statistics
import sys
import time

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if RAIZ not in sys.path:   # permite `python testes/torneio.py` de qualquer pasta
    sys.path.insert(0, RAIZ)

import chess
import chess.engine
import chess.pgn

import partida
import tempo
from ferramentas import gerar_book

VERSOES = ("nossa", "fixa", "padrao")
PASTA_RESULTADOS = os.path.join(RAIZ, "testes", "resultados")
# Cada motor do simulador usa poucos recursos por padrão, porque várias partidas rodam ao mesmo
# tempo. Para experimentos de força (ex.: 15 threads contra 1) use --threads e --hash.
HASH_MB = 16
THREADS = 1
MAX_PLIES_PADRAO = 300          # passou disso, a partida é dada como empate (evita partida eterna)
PLIES_DE_ABERTURA = 8           # quantos meios-lances da abertura sorteada são jogados sem custo de relógio
PARALELO_MAXIMO = 4             # a máquina tem pouca RAM livre: no máximo 4 partidas ao mesmo tempo

# Constantes de tempo ABSOLUTAS do tempo.py (em segundos): são as que a escala precisa multiplicar.
CONSTANTES_DE_TEMPO = ("RESERVA_MINIMA_S", "RESERVA_MAXIMA_S", "TEMPO_MINIMO_S")
_ORIGINAIS = {nome: getattr(tempo, nome) for nome in CONSTANTES_DE_TEMPO}


# ======================================================================================
# Relógio simulado
# ======================================================================================

class RelogioSim:
    """O relógio de UM jogador."""

    def __init__(self, inicio_s, incremento_s, atraso_s):
        self.restante = float(inicio_s)
        self.incremento = float(incremento_s)
        self.atraso = float(atraso_s)

    def gastar(self, pensou_s):
        """Desconta o tempo de pensar + o atraso da mesa. Devolve True se a bandeira caiu.

        A bandeira cai se o relógio chegar a zero ANTES de somar o incremento (o incremento
        só vem depois de apertar o relógio).
        """
        self.restante -= pensou_s + self.atraso
        if self.restante <= 0:
            return True
        self.restante += self.incremento
        return False


# ======================================================================================
# Jogadores (as três versões)
# ======================================================================================

class Jogador:
    nome = "?"

    def __init__(self, motor):
        self.motor = motor

    def escolher(self, board, relogio):
        """Devolve o lance. `relogio` é o RelogioSim de quem joga. `relogio_adversario` via .adversario."""
        raise NotImplementedError

    def fechar(self):
        try:
            self.motor.quit()
        except Exception:
            pass


class JogadorNossa(Jogador):
    """O nosso programa de verdade, sem book (todas as versões começam da mesma abertura)."""
    nome = "nossa"

    def __init__(self, motor, perfil):
        super().__init__(motor)
        self.perfil = perfil
        self.historico = []   # avaliações (centipawns) dos nossos lances, para o modo economia

    def escolher(self, board, relogio):
        try:
            economia = bool(tempo.modo_economia(self.historico, tempo.material_em_centipawns(board)))
        except Exception:
            economia = False
        lance, info = partida.escolher_lance(
            board, self.motor, self.perfil,
            {"restante_s": relogio.restante, "incremento_s": relogio.incremento, "atraso_humano_s": relogio.atraso},
            economia=economia)
        if info["motor_caiu"]:
            raise RuntimeError("o Stockfish caiu durante a simulação")
        aval = info["avaliacao"]
        # só conta avaliação REAL do motor (profundidade > 0): lance forçado ou de emergência não é "posição calma"
        self.historico.append(round(aval * 100) if partida._numero_finito(aval) and info["profundidade"] > 0 else None)
        return lance


class JogadorFixa(Jogador):
    """Pensa sempre o mesmo tempo por lance (já na escala da simulação)."""
    nome = "fixa"

    def __init__(self, motor, tempo_fixo_s):
        super().__init__(motor)
        self.tempo_fixo_s = tempo_fixo_s

    def escolher(self, board, relogio):
        return self.motor.play(board, chess.engine.Limit(time=self.tempo_fixo_s)).move


class JogadorPadrao(Jogador):
    """Gestão de tempo do próprio Stockfish: recebe os dois relógios e o incremento e decide sozinho."""
    nome = "padrao"

    def escolher(self, board, relogio):
        adversario = relogio.adversario
        brancas, pretas = (relogio, adversario) if board.turn == chess.WHITE else (adversario, relogio)
        limite = chess.engine.Limit(white_clock=max(0.001, brancas.restante), black_clock=max(0.001, pretas.restante),
                                    white_inc=brancas.incremento, black_inc=pretas.incremento)
        return self.motor.play(board, limite).move


# ======================================================================================
# Uma partida
# ======================================================================================

def _controle_por_cor(perfil, escala):
    """Devolve {cor: (inicio_s, incremento_s)} já na escala. 'armageddon' tem tempos diferentes por cor."""
    if perfil == "armageddon":
        chaves = {chess.WHITE: "armageddon_brancas", chess.BLACK: "armageddon_pretas"}
    elif perfil in tempo.PERFIS:
        chaves = {chess.WHITE: perfil, chess.BLACK: perfil}
    else:
        raise ValueError(f"perfil desconhecido: {perfil!r}. Opções: 15+10, 25+0, armageddon")
    return {cor: (tempo.PERFIS[chave][0] * escala, tempo.PERFIS[chave][1] * escala) for cor, chave in chaves.items()}


def jogar_partida(branco, preto, abertura, perfil, atraso_s, escala=1.0, max_plies=MAX_PLIES_PADRAO):
    """Joga uma partida entre dois Jogadores. `atraso_s` e `escala` já devem estar na escala da simulação.

    `abertura` é uma lista de chess.Move jogados sem custo de relógio.
    Devolve um dicionário com o resultado ("1-0", "0-1", "1/2-1/2"), o motivo, e as estatísticas
    de tempo de cada cor.
    """
    board = chess.Board()
    for lance in abertura:
        board.push(lance)
    controle = _controle_por_cor(perfil, escala)
    relogios = {cor: RelogioSim(inicio, incremento, atraso_s) for cor, (inicio, incremento) in controle.items()}
    relogios[chess.WHITE].adversario = relogios[chess.BLACK]
    relogios[chess.BLACK].adversario = relogios[chess.WHITE]
    jogadores = {chess.WHITE: branco, chess.BLACK: preto}
    gastos = {chess.WHITE: [], chess.BLACK: []}
    resultado = motivo = None

    while resultado is None:
        fim = board.outcome(claim_draw=True)
        if fim is not None:
            resultado, motivo = (fim.result(), fim.termination.name.lower())
            break
        if board.ply() >= max_plies:
            resultado, motivo = "1/2-1/2", "limite-de-lances"
            break
        cor = board.turn
        inicio = time.monotonic()
        lance = jogadores[cor].escolher(board, relogios[cor])
        pensou = time.monotonic() - inicio
        gastos[cor].append(pensou)
        if lance is None or lance not in board.legal_moves:
            resultado, motivo = ("0-1" if cor == chess.WHITE else "1-0"), "lance-ilegal"
            break
        if relogios[cor].gastar(pensou):
            # Bandeira caiu. Regra do xadrez: se o adversário não tem material para dar mate, é empate.
            if board.has_insufficient_material(not cor):
                resultado, motivo = "1/2-1/2", "tempo-sem-material"
            else:
                resultado, motivo = ("0-1" if cor == chess.WHITE else "1-0"), "tempo"
            break
        board.push(lance)

    if perfil == "armageddon" and resultado == "1/2-1/2":
        resultado, motivo = "0-1", "empate-vale-pretas"   # no armageddon o empate classifica as pretas

    jogo = chess.pgn.Game.from_board(board)
    jogo.headers["Result"] = resultado
    jogo.headers["Termination"] = motivo
    return {
        "resultado": resultado, "motivo": motivo, "plies": board.ply(),
        "restante": {"brancas": relogios[chess.WHITE].restante, "pretas": relogios[chess.BLACK].restante},
        "tempo_medio_lance": {"brancas": _media(gastos[chess.WHITE]), "pretas": _media(gastos[chess.BLACK])},
        "pgn": str(jogo),
    }


def _media(valores):
    return statistics.fmean(valores) if valores else 0.0


# ======================================================================================
# Preparação: escala, aberturas, e a tarefa de uma partida (roda em outro processo)
# ======================================================================================

def aplicar_escala_no_tempo(escala, ajustes=None):
    """Escala as constantes de tempo ABSOLUTAS do tempo.py, só neste processo, e aplica ajustes.

    `ajustes` = {"NOME": valor}: valor FINAL (não escalado) de qualquer constante do tempo.py.
    Serve para a calibração: "e se LANCES_RESTANTES_MINIMO fosse 30?"
    """
    for nome, original in _ORIGINAIS.items():
        setattr(tempo, nome, original * escala)
    for nome, valor in (ajustes or {}).items():
        if not hasattr(tempo, nome):
            raise ValueError(f"tempo.py não tem a constante {nome!r}")
        setattr(tempo, nome, valor)


def interpretar_ajustes(textos):
    """['LANCES_RESTANTES_MINIMO=30', 'FATOR_MAXIMO=2'] -> {'LANCES_RESTANTES_MINIMO': 30.0, ...}"""
    ajustes = {}
    for texto in textos or []:
        nome, separador, valor = texto.partition("=")
        if not separador:
            raise ValueError(f"--ajuste precisa ser NOME=VALOR, recebido {texto!r}")
        ajustes[nome.strip()] = float(valor)
    return ajustes


def sortear_aberturas(quantidade, semente):
    """Aberturas distintas (primeiros PLIES_DE_ABERTURA meios-lances das linhas da base CC0), sorteadas."""
    candidatas, vistas = [], set()
    for _eco, _nome, lances in gerar_book.ler_aberturas():
        if len(lances) < PLIES_DE_ABERTURA:
            continue
        trecho = tuple(lances[:PLIES_DE_ABERTURA])
        if trecho not in vistas:
            vistas.add(trecho)
            candidatas.append(list(trecho))
    random.Random(semente).shuffle(candidatas)
    if quantidade > len(candidatas):
        raise ValueError(f"só há {len(candidatas)} aberturas distintas, pediu {quantidade}")
    return candidatas[:quantidade]


def _criar_jogador(versao, motor, perfil, tempo_fixo_s):
    if versao == "nossa":
        return JogadorNossa(motor, perfil)
    if versao == "fixa":
        return JogadorFixa(motor, tempo_fixo_s)
    if versao == "padrao":
        return JogadorPadrao(motor)
    raise ValueError(f"versão desconhecida: {versao!r}. Opções: {', '.join(VERSOES)}")


def _executar_partida(tarefa):
    """Uma partida completa. Roda num processo separado: abre os 2 motores, joga e fecha tudo."""
    aplicar_escala_no_tempo(tarefa["escala"], tarefa["ajustes"])
    caminho = partida._achar_stockfish()
    pasta_tb = partida.PASTA_TABLEBASES if os.path.isdir(partida.PASTA_TABLEBASES) else None
    jogadores = []
    try:
        for versao in (tarefa["brancas"], tarefa["pretas"]):
            motor = partida.abrir_motor(caminho, tarefa.get("threads", THREADS), tarefa.get("hash_mb", HASH_MB), pasta_tb)
            jogadores.append(_criar_jogador(versao, motor, tarefa["perfil"], tarefa["tempo_fixo_s"]))
        abertura = [chess.Move.from_uci(m) for m in tarefa["abertura"]]
        resumo = jogar_partida(jogadores[0], jogadores[1], abertura, tarefa["perfil"], tarefa["atraso_s"],
                               tarefa["escala"], tarefa["max_plies"])
    finally:
        for jogador in jogadores:
            jogador.fechar()
    resumo.update(indice=tarefa["indice"], brancas=tarefa["brancas"], pretas=tarefa["pretas"])
    return resumo


def montar_tarefas(versao_a, versao_b, n_partidas, perfil, atraso_s, escala, tempo_fixo_s, ajustes, semente, max_plies,
                   threads=THREADS, hash_mb=HASH_MB):
    """Cada abertura é jogada duas vezes, com as cores trocadas (partidas pares: A de brancas)."""
    if versao_a == versao_b:
        raise ValueError("as duas versões são iguais")
    for versao in (versao_a, versao_b):
        if versao not in VERSOES:
            raise ValueError(f"versão desconhecida: {versao!r}. Opções: {', '.join(VERSOES)}")
    if "fixa" in (versao_a, versao_b) and tempo_fixo_s is None:
        raise ValueError("a versão 'fixa' precisa de --tempo-fixo (segundos por lance, na escala real)")
    aberturas = sortear_aberturas(math.ceil(n_partidas / 2), semente)
    tarefas = []
    for i in range(n_partidas):
        a_de_brancas = i % 2 == 0
        tarefas.append({
            "indice": i, "abertura": [m.uci() for m in aberturas[i // 2]],
            "brancas": versao_a if a_de_brancas else versao_b, "pretas": versao_b if a_de_brancas else versao_a,
            "perfil": perfil, "atraso_s": atraso_s * escala, "escala": escala,
            "tempo_fixo_s": None if tempo_fixo_s is None else tempo_fixo_s * escala,
            "ajustes": ajustes, "max_plies": max_plies, "threads": threads, "hash_mb": hash_mb,
        })
    return tarefas


def rodar_torneio(versao_a, versao_b, n_partidas, perfil, atraso_s, escala=0.2, tempo_fixo_s=None,
                  ajustes=None, paralelo=PARALELO_MAXIMO, semente=1, max_plies=MAX_PLIES_PADRAO, saida=print,
                  threads=THREADS, hash_mb=HASH_MB):
    """Roda `n_partidas` entre as duas versões. `atraso_s` e `tempo_fixo_s` são na escala REAL (a escala é aplicada aqui)."""
    tarefas = montar_tarefas(versao_a, versao_b, n_partidas, perfil, atraso_s, escala, tempo_fixo_s,
                             ajustes or {}, semente, max_plies, threads, hash_mb)
    paralelo = max(1, min(paralelo, PARALELO_MAXIMO, n_partidas))
    resultados = []
    contexto = multiprocessing.get_context("spawn")
    with concurrent.futures.ProcessPoolExecutor(max_workers=paralelo, mp_context=contexto) as pool:
        for futuro in concurrent.futures.as_completed([pool.submit(_executar_partida, t) for t in tarefas]):
            resumo = futuro.result()
            resultados.append(resumo)
            saida(f"[{len(resultados)}/{n_partidas}] {resumo['brancas']} (brancas) x {resumo['pretas']}: "
                  f"{resumo['resultado']} ({resumo['motivo']}, {resumo['plies']} meios-lances)")
    resultados.sort(key=lambda r: r["indice"])
    return resultados


# ======================================================================================
# Resultados: tabela para a arguição
# ======================================================================================

def resumir(resultados, versao_a, versao_b):
    """Agrega por versão: vitórias, empates, derrotas, derrotas por tempo, tempo que sobrou e tempo por lance."""
    linhas = {}
    for versao in (versao_a, versao_b):
        linhas[versao] = {"vitorias": 0, "empates": 0, "derrotas": 0, "derrotas_por_tempo": 0,
                          "sobra": [], "por_lance": []}
    for r in resultados:
        for cor, versao in (("brancas", r["brancas"]), ("pretas", r["pretas"])):
            linha = linhas[versao]
            if r["resultado"] == "1/2-1/2":
                linha["empates"] += 1
            elif (r["resultado"] == "1-0") == (cor == "brancas"):
                linha["vitorias"] += 1
            else:
                linha["derrotas"] += 1
                if r["motivo"] == "tempo":
                    linha["derrotas_por_tempo"] += 1
            linha["sobra"].append(max(0.0, r["restante"][cor]))
            linha["por_lance"].append(r["tempo_medio_lance"][cor])
    for linha in linhas.values():
        linha["sobra_media_s"] = _media(linha.pop("sobra"))
        linha["tempo_medio_por_lance_s"] = _media(linha.pop("por_lance"))
        linha["partidas"] = linha["vitorias"] + linha["empates"] + linha["derrotas"]
        linha["pontos"] = linha["vitorias"] + 0.5 * linha["empates"]
    return linhas


def tabela_markdown(linhas, titulo=""):
    cabecalho = ("| Versão | Partidas | Vitórias | Empates | Derrotas | Derrotas por tempo | Pontos | "
                 "Tempo médio que sobrou (s) | Tempo médio por lance (s) |\n"
                 "|---|---|---|---|---|---|---|---|---|\n")
    corpo = "".join(
        f"| {versao} | {l['partidas']} | {l['vitorias']} | {l['empates']} | {l['derrotas']} | "
        f"{l['derrotas_por_tempo']} | {l['pontos']:g} | {l['sobra_media_s']:.1f} | {l['tempo_medio_por_lance_s']:.2f} |\n"
        for versao, l in linhas.items())
    return (f"**{titulo}**\n\n" if titulo else "") + cabecalho + corpo


def salvar_resultados(resultados, linhas, pasta, nome, titulo=""):
    """Grava <nome>.md (tabela), <nome>.csv (uma linha por partida) e <nome>.pgn (as partidas)."""
    os.makedirs(pasta, exist_ok=True)
    base = os.path.join(pasta, nome)
    with open(base + ".md", "w", encoding="utf-8") as f:
        f.write(tabela_markdown(linhas, titulo))
    with open(base + ".csv", "w", encoding="utf-8", newline="") as f:
        escritor = csv.writer(f)
        escritor.writerow(["partida", "brancas", "pretas", "resultado", "motivo", "meios_lances",
                           "sobrou_brancas_s", "sobrou_pretas_s"])
        for r in resultados:
            escritor.writerow([r["indice"], r["brancas"], r["pretas"], r["resultado"], r["motivo"], r["plies"],
                               f"{r['restante']['brancas']:.2f}", f"{r['restante']['pretas']:.2f}"])
    with open(base + ".pgn", "w", encoding="utf-8") as f:
        for r in resultados:
            f.write(r["pgn"] + "\n\n")
    return base


# ======================================================================================
# Medir o estouro do motor (dado para decidir a folga do watchdog)
# ======================================================================================

def medir_estouro(tempos_s=(0.05, 0.1, 0.2, 0.5, 1.0), posicoes=20, semente=1, saida=print):
    """Mede quanto o Stockfish passa do tempo pedido e quanto leva para abrir e reiniciar.

    É EVIDÊNCIA para o grupo decidir a folga do watchdog (CAPABLANCA_FOLGA_WATCHDOG_S):
    a folga precisa ser maior que o pior estouro normal, senão o vigia mataria um motor
    saudável. A decisão do número continua sendo do grupo.
    """
    caminho = partida._achar_stockfish()
    if caminho is None:
        raise FileNotFoundError("Stockfish não encontrado em stockfish/")
    aberturas = sortear_aberturas(posicoes, semente)
    abrir, reiniciar = [], []
    for _ in range(5):
        inicio = time.monotonic()
        motor = partida.abrir_motor(caminho, THREADS, HASH_MB)
        abrir.append(time.monotonic() - inicio)
        inicio = time.monotonic()
        motor.quit()
        motor = partida.abrir_motor(caminho, THREADS, HASH_MB)
        reiniciar.append(time.monotonic() - inicio)
        motor.quit()
    saida(f"abrir o motor:     média {_media(abrir) * 1000:.0f} ms, pior {max(abrir) * 1000:.0f} ms")
    saida(f"reiniciar o motor: média {_media(reiniciar) * 1000:.0f} ms, pior {max(reiniciar) * 1000:.0f} ms")

    motor = partida.abrir_motor(caminho, THREADS, HASH_MB)
    piores = {}
    try:
        saida("\nestouro = tempo medido - tempo pedido (em milissegundos), em %d posições:" % posicoes)
        saida("pedido(s) | média(ms) | p95(ms) | pior(ms)   [Limit(time=...)]   |   [escolher_lance com analysis]")
        for pedido in tempos_s:
            estouros_play, estouros_analise = [], []
            for lances in aberturas:
                board = chess.Board()
                for lance in lances:
                    board.push(lance)
                inicio = time.monotonic()
                motor.play(board, chess.engine.Limit(time=pedido))
                estouros_play.append((time.monotonic() - inicio - pedido) * 1000)
                inicio = time.monotonic()
                with motor.analysis(board, chess.engine.Limit(time=pedido)) as analise:
                    for _ in analise:
                        pass
                    analise.wait()
                estouros_analise.append((time.monotonic() - inicio - pedido) * 1000)
            piores[pedido] = max(estouros_play + estouros_analise)
            p95 = sorted(estouros_play)[max(0, math.ceil(0.95 * len(estouros_play)) - 1)]
            saida(f"{pedido:>9g} | {_media(estouros_play):9.1f} | {p95:7.1f} | {max(estouros_play):8.1f}"
                  f"   |   média {_media(estouros_analise):6.1f}, pior {max(estouros_analise):6.1f}")
    finally:
        motor.quit()
    pior_geral = max(piores.values())
    saida(f"\npior estouro observado: {pior_geral:.0f} ms. A folga do watchdog tem que ser MAIOR que isso "
          f"(com margem). Decisão do grupo; meça de novo no notebook do torneio.")
    return {"abrir_s": abrir, "reiniciar_s": reiniciar, "pior_estouro_ms": pior_geral}


# ======================================================================================
# Linha de comando
# ======================================================================================

def main(argv=None):
    parser = argparse.ArgumentParser(description="Simulador de partidas (relógio simulado) entre versões.")
    sub = parser.add_subparsers(dest="comando", required=True)

    c = sub.add_parser("confronto", help="joga N partidas entre duas versões")
    c.add_argument("--a", required=True, choices=VERSOES)
    c.add_argument("--b", required=True, choices=VERSOES)
    c.add_argument("--perfil", required=True, choices=("15+10", "25+0", "armageddon"))
    c.add_argument("--partidas", type=int, default=20)
    c.add_argument("--atraso-s", type=float, required=True,
                   help="atraso humano por lance, em segundos REAIS (obrigatório: não inventamos esse valor)")
    c.add_argument("--escala", type=float, default=0.2, help="fração do relógio real (padrão 0.2)")
    c.add_argument("--tempo-fixo", type=float, default=None, help="segundos REAIS por lance da versão 'fixa'")
    c.add_argument("--ajuste", action="append", default=[], metavar="NOME=VALOR",
                   help="troca uma constante do tempo.py só no simulador (repetível)")
    c.add_argument("--paralelo", type=int, default=PARALELO_MAXIMO)
    c.add_argument("--semente", type=int, default=1)
    c.add_argument("--max-plies", type=int, default=MAX_PLIES_PADRAO)
    c.add_argument("--threads", type=int, default=THREADS, help="threads de CADA motor (padrão 1)")
    c.add_argument("--hash", type=int, default=HASH_MB, help="hash de CADA motor, em MB (padrão 16)")
    c.add_argument("--saida", default=PASTA_RESULTADOS, help="pasta dos resultados (.md, .csv, .pgn)")
    c.add_argument("--nome", default=None, help="nome base dos arquivos de resultado")

    e = sub.add_parser("estouro", help="mede o estouro do Limit(time=...) e o tempo de reiniciar o motor")
    e.add_argument("--posicoes", type=int, default=20)

    args = parser.parse_args(argv)
    if args.comando == "estouro":
        medir_estouro(posicoes=args.posicoes)
        return 0

    if not 0 < args.escala <= 1:
        parser.error("--escala precisa estar entre 0 (exclusive) e 1")
    resultados = rodar_torneio(args.a, args.b, args.partidas, args.perfil, args.atraso_s, args.escala,
                               args.tempo_fixo, interpretar_ajustes(args.ajuste), args.paralelo, args.semente,
                               args.max_plies, threads=args.threads, hash_mb=args.hash)
    linhas = resumir(resultados, args.a, args.b)
    titulo = (f"{args.a} x {args.b} | perfil {args.perfil} | {args.partidas} partidas | escala {args.escala:g} | "
              f"atraso {args.atraso_s:g} s | semente {args.semente} | {args.threads} thread(s), {args.hash} MB"
              + (f" | ajustes {args.ajuste}" if args.ajuste else ""))
    print("\n" + tabela_markdown(linhas, titulo))
    nome = args.nome or f"{args.a}_x_{args.b}_{args.perfil.replace('+', 'mais')}"
    print("salvo em", salvar_resultados(resultados, linhas, args.saida, nome, titulo) + ".{md,csv,pgn}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
