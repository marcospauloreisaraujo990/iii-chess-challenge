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
    [ ] Aprofundamento iterativo chamando evaluation.evaluate().
    [ ] Negamax com poda Alfa-Beta.
    [ ] Ordenação básica de lances (capturas primeiro).
    [ ] Parar quando o limite de tempo chegar (conferir o relógio a cada N nós).
    [ ] (Com o Léo) usar syzygy.probe_wdl() quando houver 5 peças ou menos.
    [ ] Testes em tests/test_search.py.
"""

from dataclasses import dataclass, field
from typing import List, Optional

import chess

from engine.evaluation import MATE_SCORE, evaluate  # noqa: F401  (usados na implementação)


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
    """Sugestão: levantar dentro da busca quando o tempo acabar e capturar em search()."""


def search(board: chess.Board, time_limit_s: float, max_depth: int = 64) -> SearchResult:
    """Escolhe o lance de quem joga em `board` sem passar de `time_limit_s` segundos.

    Não altere o board recebido: trabalhe numa cópia (board.copy()).
    """
    raise NotImplementedError("search.search() — Sprint 2, card do Marcos")


def negamax(board: chess.Board, depth: int, alpha: int, beta: int, ply: int) -> int:
    """Nota da posição para quem joga, olhando `depth` meios-lances à frente.

    ply = distância até a raiz (para preferir o mate mais rápido: MATE_SCORE - ply).
    """
    raise NotImplementedError("search.negamax() — Sprint 2, card do Marcos")


def order_moves(board: chess.Board) -> List[chess.Move]:
    """Lances legais do mais promissor para o menos promissor (capturas antes)."""
    raise NotImplementedError("search.order_moves() — Sprint 2, card do Marcos")
