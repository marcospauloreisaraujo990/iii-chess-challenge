"""
Busca Negamax com poda Alfa-Beta e aprofundamento iterativo — COMPONENTE AUTORAL DA EQUIPE.

Responsável: Marcos Paulo
Sprint 2 · Card "Algoritmo Negamax com Poda Alpha-Beta" · Epic 2 (Busca) · 5 pontos
Depende de: evaluation.evaluate() (Sprint 1, Marcos) e do tempo calculado por
time_manager.compute_time_budget() (Sprint 2, Junio).

O que este módulo entrega (CONTRATO)
------------------------------------
    search(board, time_limit_s) -> SearchResult
        Aprofundamento iterativo: profundidade 1, 2, 3... enquanto houver tempo.
        Se o tempo acabar no meio de uma profundidade, devolve o melhor lance da
        última profundidade COMPLETA. Nunca devolve lance ilegal e não passa do
        limite (o nosso relógio depende disso).

    SearchResult
        O lance e tudo o que o log da banca precisa: profundidade, nós,
        avaliação, PV e tempo. O main.py usa o mesmo formato para lances
        vindos do book e da tablebase (campo `source`).

    negamax() e order_moves() abaixo são só sugestões de organização: o que
    os outros módulos usam é search() e SearchResult.

Checklist do card
-----------------
    [x] Aprofundamento iterativo chamando evaluation.evaluate().
    [x] Negamax com poda Alfa-Beta.
    [x] Ordenação básica de lances (capturas primeiro).
    [x] Parar quando o limite de tempo chegar (conferir o relógio a cada N nós).
    [x] (Com o Léo) usar syzygy.probe_wdl() quando houver 5 peças ou menos.
    [x] Testes em tests/test_search.py.
"""

import math
import time
from dataclasses import dataclass, field
from typing import List, Optional

import chess

from engine import syzygy
from engine.evaluation import MATE_SCORE, MATE_THRESHOLD, PIECE_VALUES, evaluate

# Nota de uma vitória/derrota confirmada pela tablebase. Fica abaixo de
# MATE_THRESHOLD para não ser confundida com um mate de verdade.
TB_WIN_SCORE = MATE_THRESHOLD - 10_000

# De quantos em quantos nós a busca confere o relógio.
CHECK_EVERY_NODES = 256

# Se uma profundidade já usou esta fração do tempo, a próxima (que demora
# várias vezes mais) não terminaria: paramos antes e economizamos relógio.
NEXT_DEPTH_TIME_FRACTION = 0.5


@dataclass
class SearchResult:
    """O lance escolhido pelo nosso software e os dados que vão para o log."""
    move: Optional[chess.Move]
    depth: int = 0                  # última profundidade completa
    nodes: int = 0                  # posições visitadas
    score: Optional[int] = None     # centipawns do NOSSO ponto de vista (+ = bom para nós)
    pv: List[chess.Move] = field(default_factory=list)   # variante principal
    time_s: float = 0.0             # tempo gasto pensando
    source: str = "search"          # "search" | "book" | "syzygy"


class SearchTimeout(Exception):
    """Levantada dentro da busca quando o tempo acaba; capturada em search()."""


# Estado da busca em andamento (uma busca por vez).
_nodes = 0
_deadline = math.inf
_tablebase_ok = True   # vira False se o syzygy ainda não estiver implementado


def search(board: chess.Board, time_limit_s: float, max_depth: int = 64) -> SearchResult:
    """Escolhe o lance de quem joga em `board` sem passar de `time_limit_s` segundos.

    Não altera o board recebido: trabalha numa cópia (board.copy()).
    """
    global _nodes, _deadline
    inicio = time.perf_counter()
    b = board.copy()
    _nodes = 0

    lances = order_moves(b)
    if not lances:
        return SearchResult(move=None, time_s=time.perf_counter() - inicio)

    melhor = SearchResult(move=lances[0])
    for depth in range(1, max_depth + 1):
        # A profundidade 1 roda sem limite: assim sempre há um lance calculado.
        _deadline = math.inf if depth == 1 else inicio + time_limit_s
        pv: List[chess.Move] = []
        try:
            score = negamax(b, depth, -MATE_SCORE, MATE_SCORE, 0, pv, melhor.pv[:1])
        except SearchTimeout:
            break   # fica com a última profundidade completa

        melhor = SearchResult(move=pv[0], depth=depth, score=score, pv=pv)
        gasto = time.perf_counter() - inicio
        if len(lances) == 1 or abs(score) >= MATE_THRESHOLD:
            break   # lance único ou mate encontrado: pensar mais não muda nada
        if gasto >= time_limit_s * NEXT_DEPTH_TIME_FRACTION:
            break

    _deadline = math.inf
    melhor.nodes = _nodes
    melhor.time_s = time.perf_counter() - inicio
    return melhor


def negamax(board: chess.Board, depth: int, alpha: int, beta: int, ply: int,
            pv: Optional[List[chess.Move]] = None,
            pv_anterior: Optional[List[chess.Move]] = None) -> int:
    """Nota da posição para quem joga, olhando `depth` meios-lances à frente.

    ply = distância até a raiz (para preferir o mate mais rápido: MATE_SCORE - ply).
    pv  = lista preenchida com a variante principal encontrada.
    pv_anterior = variante da profundidade anterior, testada primeiro (melhora a poda).
    """
    _contar_no()

    if ply > 0:
        if board.is_repetition(2) or board.is_fifty_moves() or board.is_insufficient_material():
            return 0
        nota_tb = _consultar_tablebase(board, ply)
        if nota_tb is not None:
            return nota_tb

    if depth <= 0:
        return quiescence(board, alpha, beta)

    lances = order_moves(board, primeiro=pv_anterior[0] if pv_anterior else None)
    if not lances:
        return -(MATE_SCORE - ply) if board.is_check() else 0   # mate ou afogamento

    melhor = -MATE_SCORE
    for lance in lances:
        sub_pv: List[chess.Move] = []
        segue_pv = pv_anterior[1:] if pv_anterior and lance == pv_anterior[0] else None
        board.push(lance)
        score = -negamax(board, depth - 1, -beta, -alpha, ply + 1, sub_pv, segue_pv)
        board.pop()

        if score > melhor:
            melhor = score
            if pv is not None:
                pv[:] = [lance] + sub_pv
        if score > alpha:
            alpha = score
        if alpha >= beta:
            break   # poda beta: o adversário não deixaria chegar aqui
    return melhor


def quiescence(board: chess.Board, alpha: int, beta: int) -> int:
    """Continua só com capturas até a posição ficar calma, antes de avaliar.

    Evita o "efeito horizonte": parar a busca no meio de uma troca e achar
    que ganhou uma peça que vai ser recapturada no lance seguinte.
    """
    _contar_no()
    parado = evaluate(board)   # "stand pat": quem joga pode não capturar nada
    if parado >= beta:
        return parado
    alpha = max(alpha, parado)

    for lance in order_moves(board, so_capturas=True):
        board.push(lance)
        score = -quiescence(board, -beta, -alpha)
        board.pop()
        if score >= beta:
            return score
        alpha = max(alpha, score)
    return alpha


def order_moves(board: chess.Board, primeiro: Optional[chess.Move] = None,
                so_capturas: bool = False) -> List[chess.Move]:
    """Lances legais do mais promissor para o menos promissor (capturas antes).

    Ordem: `primeiro` (melhor lance da profundidade anterior), depois
    promoções e capturas por MVV-LVA (vítima mais valiosa, atacante menos
    valioso), depois os lances quietos.
    """
    def prioridade(lance: chess.Move) -> int:
        if lance == primeiro:
            return 1_000_000
        nota = 0
        if lance.promotion:
            nota += 10_000 + PIECE_VALUES[lance.promotion]
        if board.is_capture(lance):
            vitima = chess.PAWN if board.is_en_passant(lance) else board.piece_type_at(lance.to_square)
            atacante = board.piece_type_at(lance.from_square)
            nota += 10_000 + 10 * PIECE_VALUES[vitima] - PIECE_VALUES[atacante]
        return nota

    if so_capturas:
        lances = [m for m in board.legal_moves if board.is_capture(m) or m.promotion]
    else:
        lances = list(board.legal_moves)
    lances.sort(key=prioridade, reverse=True)
    return lances


def _contar_no() -> None:
    """Conta a posição visitada e, a cada CHECK_EVERY_NODES, confere o relógio."""
    global _nodes
    _nodes += 1
    if _nodes % CHECK_EVERY_NODES == 0 and time.perf_counter() >= _deadline:
        raise SearchTimeout


def _consultar_tablebase(board: chess.Board, ply: int) -> Optional[int]:
    """Nota pela tablebase com 5 peças ou menos, ou None se não houver resposta."""
    global _tablebase_ok
    if not _tablebase_ok or chess.popcount(board.occupied) > syzygy.MAX_PIECES:
        return None
    try:
        wdl = syzygy.probe_wdl(board)
    except NotImplementedError:
        _tablebase_ok = False   # card do Léo ainda não feito: busca segue sem tablebase
        return None
    if wdl is None:
        return None
    if wdl >= 2:
        return TB_WIN_SCORE - ply
    if wdl <= -2:
        return -(TB_WIN_SCORE - ply)
    return 0   # empate (ou vitória/derrota anulada pela regra dos 50 lances)
