"""Verifica se o PC está pronto para o torneio e MEDE quantas threads usar. Dono: Léo.

Rode no PC que vai para a mesa, com o ambiente ativado:
    python ferramentas/verificar_maquina.py            # completo (uns 2 a 3 minutos)
    python ferramentas/verificar_maquina.py --rapido   # sem conferir o MD5 das tablebases

O que ele faz, em linguagem simples:
  1. Confere o básico: versão do Python e do python-chess, Stockfish encontrado e respondendo,
     book, tablebases (com o MD5 da lista fixada no Git) e uma busca usando tablebase.
  2. Mede a velocidade do Stockfish (nós por segundo) com várias quantidades de threads e
     RECOMENDA a quantidade: a maior que ainda traz ganho, deixando 1 thread para o sistema.
  3. Mede o estouro do Limit(time=...) nesta máquina (dado para a folga do vigia).
  4. Imprime os comandos prontos para o dia (Linux/Mac, PowerShell e cmd do Windows).

Nada aqui é decidido no chute: os números saem da medição nesta máquina (regra 4 do CLAUDE.md).
"""
import argparse
import os
import platform
import sys
import time

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if RAIZ not in sys.path:
    sys.path.insert(0, RAIZ)

import chess
import chess.engine

import book
import partida
from ferramentas import baixar_tablebases

VERSAO_CHESS = "1.11.2"
# Posições de meio-jogo variadas para medir a velocidade (nós por segundo).
POSICOES_DE_MEDIDA = [
    "r1bq1rk1/pp2bppp/2n1pn2/2pp4/3P4/2PBPN2/PP1N1PPP/R2QK2R w KQ - 0 8",
    "r2q1rk1/pp1nbppp/2p1pn2/3p4/2PP4/1PN1PN2/P3BPPP/R2Q1RK1 b - - 0 9",
    "rnbqk2r/pp2ppbp/3p1np1/8/3NP3/2N1B3/PPP2PPP/R2QKB1R w KQkq - 0 7",
]
GANHO_MINIMO = 0.03   # uma thread a mais só vale se a velocidade subir pelo menos 3%


class Relatorio:
    def __init__(self, saida=print):
        self.saida = saida
        self.falhas = []

    def ok(self, texto):
        self.saida(f"  [OK]    {texto}")

    def aviso(self, texto):
        self.saida(f"  [AVISO] {texto}")

    def falha(self, texto):
        self.falhas.append(texto)
        self.saida(f"  [FALHA] {texto}")


def candidatos_de_threads(cpus):
    """Quantidades de threads a medir: 1, metade, e as do topo (todas menos 2, menos 1, todas)."""
    valores = {1, max(1, cpus // 2), max(1, cpus - 2), max(1, cpus - 1), cpus}
    return sorted(valores)


def escolher_threads(medidas, cpus, ganho_minimo=GANHO_MINIMO):
    """Recomenda threads a partir de {threads: nós_por_segundo}.

    Sobe enquanto cada passo der pelo menos `ganho_minimo` de velocidade, e nunca usa todas as
    threads da CPU (deixa 1 para o sistema e para o nosso programa).
    """
    limite = max(1, cpus - 1)
    ordenadas = sorted(t for t in medidas if t <= limite)
    escolhida = ordenadas[0]
    for atual in ordenadas[1:]:
        # só troca se for pelo menos `ganho_minimo` mais rápido que a MELHOR escolha até agora
        if medidas[atual] >= medidas[escolhida] * (1 + ganho_minimo):
            escolhida = atual
    return escolhida


def medir_nos_por_segundo(caminho, threads, hash_mb=256, segundos=2.0):
    motor = partida.abrir_motor(caminho, threads, hash_mb)
    try:
        total_nos, total_tempo = 0, 0.0
        for fen in POSICOES_DE_MEDIDA:
            motor.configure({"Clear Hash": None})
            inicio = time.monotonic()
            info = motor.analyse(chess.Board(fen), chess.engine.Limit(time=segundos))
            total_tempo += time.monotonic() - inicio
            total_nos += info.get("nodes", 0)
        return total_nos / total_tempo if total_tempo else 0.0
    finally:
        motor.quit()


def verificar(rapido=False, saida=print, pausa_s=3.0):
    r = Relatorio(saida)
    cpus = os.cpu_count() or 1
    ram = partida._ram_total_mb()

    saida("\n1) BÁSICO")
    r.ok(f"sistema: {platform.system()} {platform.release()} | {cpus} threads de CPU | "
         f"RAM: {('%d MB' % ram) if ram else 'não consegui ler'}")
    if sys.version_info >= (3, 11):
        r.ok(f"Python {platform.python_version()}")
    else:
        r.falha(f"Python {platform.python_version()}: o projeto pede 3.11 ou mais novo")
    if chess.__version__ == VERSAO_CHESS:
        r.ok(f"python-chess {chess.__version__}")
    else:
        r.falha(f"python-chess {chess.__version__}: o requirements.txt fixa {VERSAO_CHESS}")

    caminho = partida._achar_stockfish()
    if caminho is None:
        r.falha(f"Stockfish não encontrado em {partida.PASTA_STOCKFISH} (veja o README)")
        return r, None
    try:
        motor = partida.abrir_motor(caminho, 1, 16)
        nome = motor.id.get("name", "?")
        lance = motor.play(chess.Board(), chess.engine.Limit(time=0.2)).move
        motor.quit()
        r.ok(f"{nome} respondendo ({os.path.basename(caminho)}), primeiro lance {lance.uci()}")
    except Exception as erro:
        r.falha(f"o Stockfish não abriu: {type(erro).__name__}: {erro}")
        return r, None

    lance_book = book.lance_do_book(chess.Board(), partida.CAMINHO_BOOK)
    if lance_book is not None:
        r.ok(f"book encontrado ({partida.CAMINHO_BOOK}), sugere {lance_book.uci()} na posição inicial")
    else:
        r.aviso(f"book não encontrado ou vazio em {partida.CAMINHO_BOOK}: o programa joga sem book")

    pasta_tb = partida.PASTA_TABLEBASES
    if not os.path.isdir(pasta_tb):
        r.aviso(f"sem tablebases em {pasta_tb}: rode python ferramentas/baixar_tablebases.py")
    else:
        with open(baixar_tablebases.LISTA_FIXADA, encoding="ascii") as arquivo:
            esperado = baixar_tablebases.ler_md5_oficial(arquivo.read())
        if rapido:
            presentes = [f for f in os.listdir(pasta_tb) if f.endswith((".rtbw", ".rtbz"))]
            proibidos = [f for f in presentes if baixar_tablebases.pecas_no_nome(f) > 5]
            faltando = sorted(set(esperado) - set(presentes))
            corrompidos = []
            r.ok(f"tablebases: {len(presentes)} arquivos (MD5 não conferido no modo --rapido)")
        else:
            saida("  ... conferindo o MD5 das tablebases (~1 GB, pode levar um minuto)")
            ok, faltando, corrompidos, proibidos = baixar_tablebases.conferir_pasta(pasta_tb, esperado)
            r.ok(f"tablebases: {ok} arquivos com MD5 correto")
        if proibidos:
            r.falha(f"tablebases com 6+ peças na pasta (proibido): {proibidos[:3]}")
        if faltando:
            r.aviso(f"{len(faltando)} tablebase(s) faltando: rode python ferramentas/baixar_tablebases.py")
        if corrompidos:
            r.falha(f"{len(corrompidos)} tablebase(s) corrompida(s): rode o baixador de novo")
        motor = partida.abrir_motor(caminho, 1, 16, pasta_tb)
        try:
            with motor.analysis(chess.Board("8/5k2/8/8/8/2K5/3PQ3/7r w - - 0 1"),
                                chess.engine.Limit(time=0.5)) as analise:
                acertos = max((info.get("tbhits", 0) for info in analise), default=0)
        finally:
            motor.quit()
        if acertos > 0:
            r.ok(f"o motor usa as tablebases num final de 5 peças ({acertos} consultas)")
        else:
            r.aviso("o motor não consultou as tablebases no teste de 5 peças")

    saida("\n2) VELOCIDADE DO STOCKFISH POR NÚMERO DE THREADS (nós por segundo, mais = melhor)")
    medidas = {}
    for threads in candidatos_de_threads(cpus):
        time.sleep(pausa_s)   # deixa a CPU esfriar: o calor da medida anterior não pode contaminar a próxima
        medidas[threads] = medir_nos_por_segundo(caminho, threads, segundos=1.0 if rapido else 2.0)
        saida(f"  {threads:>3} thread(s): {medidas[threads] / 1e6:7.2f} milhões de nós/s")
    threads = escolher_threads(medidas, cpus)
    hash_mb = partida.hash_automatico_mb()
    r.ok(f"recomendado: {threads} threads (deixa {cpus - threads} livre(s)), {hash_mb} MB de hash")
    if threads < partida.threads_automaticas():
        r.aviso(f"nesta máquina MAIS threads deixam o motor MAIS LENTO (limite de energia/temperatura): "
                f"use {threads}, não o automático ({partida.threads_automaticas()}). Defina CAPABLANCA_THREADS.")

    saida("\n3) ESTOURO DO MOTOR NESTA MÁQUINA (dado para a folga do vigia)")
    from testes import torneio
    estouro = torneio.medir_estouro(tempos_s=(0.1, 0.5), posicoes=4 if rapido else 10,
                                    saida=lambda linha: saida("  " + linha))

    saida("\n4) COMANDOS PARA O DIA (copie o do seu sistema)")
    saida(f"  Linux/Mac:   export CAPABLANCA_THREADS={threads} CAPABLANCA_HASH_MB={hash_mb}")
    saida(f"  PowerShell:  $env:CAPABLANCA_THREADS={threads}; $env:CAPABLANCA_HASH_MB={hash_mb}")
    saida(f"  cmd:         set CAPABLANCA_THREADS={threads} && set CAPABLANCA_HASH_MB={hash_mb}")
    saida("  Depois: python partida.py")

    saida("\nRESULTADO: " + ("TUDO CERTO" if not r.falhas else f"{len(r.falhas)} FALHA(S): " + " | ".join(r.falhas)))
    return r, {"threads": threads, "hash_mb": hash_mb, "medidas": medidas,
               "pior_estouro_ms": estouro["pior_estouro_ms"]}


def main(argv=None):
    parser = argparse.ArgumentParser(description="Verifica o PC do torneio e mede quantas threads usar.")
    parser.add_argument("--rapido", action="store_true", help="não confere o MD5 das tablebases e mede mais rápido")
    args = parser.parse_args(argv)
    relatorio, _ = verificar(rapido=args.rapido)
    return 1 if relatorio.falhas else 0


if __name__ == "__main__":
    raise SystemExit(main())
