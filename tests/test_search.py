"""
Testes da busca — card do Marcos (Sprint 2).

Pendentes até search() ser implementada.
"""

import os
import sys
import time
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import chess  # noqa: E402

from engine import search  # noqa: E402
from tests import pendente  # noqa: E402

# Mate do corredor: Ra8#.
MATE_EM_1 = "6k1/5ppp/8/8/8/8/5PPP/R5K1 w - - 0 1"


class TestSearch(unittest.TestCase):
    @pendente
    def test_encontra_mate_em_1(self):
        resultado = search.search(chess.Board(MATE_EM_1), time_limit_s=2.0)
        self.assertEqual(resultado.move, chess.Move.from_uci("a1a8"))

    @pendente
    def test_devolve_lance_legal_e_dados_do_log(self):
        board = chess.Board()
        resultado = search.search(board, time_limit_s=1.0)
        self.assertIn(resultado.move, board.legal_moves)
        self.assertGreater(resultado.depth, 0)
        self.assertGreater(resultado.nodes, 0)
        self.assertTrue(resultado.pv)

    @pendente
    def test_respeita_o_limite_de_tempo(self):
        inicio = time.perf_counter()
        search.search(chess.Board(), time_limit_s=0.5)
        self.assertLess(time.perf_counter() - inicio, 0.5 + 0.3)

    # TODO (Marcos): não altera o board recebido; ganha material quando há peça solta.


if __name__ == "__main__":
    unittest.main()
