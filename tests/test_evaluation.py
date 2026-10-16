"""
Testes da avaliação — card do Marcos (Sprint 1).

Pendentes até evaluate() ser implementada. Exemplos para começar; o card pede
mais testes garantindo que posições com peças a mais recebem notas maiores.
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import chess  # noqa: E402

from engine.evaluation import evaluate  # noqa: E402
from tests import pendente  # noqa: E402

# Posição inicial sem a dama preta (d8 vazia).
SEM_DAMA_PRETA = "rnb1kbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR {vez} KQkq - 0 1"


class TestEvaluation(unittest.TestCase):
    @pendente
    def test_posicao_inicial_equilibrada(self):
        self.assertLessEqual(abs(evaluate(chess.Board())), 50)

    @pendente
    def test_dama_a_mais_vale_mais(self):
        board = chess.Board(SEM_DAMA_PRETA.format(vez="w"))
        self.assertGreater(evaluate(board), 500)

    @pendente
    def test_nota_do_ponto_de_vista_de_quem_joga(self):
        """Convenção do Negamax: mesma posição, vez das pretas -> nota negativa."""
        board = chess.Board(SEM_DAMA_PRETA.format(vez="b"))
        self.assertLess(evaluate(board), -500)

    @pendente
    def test_peca_a_mais_para_as_pretas(self):
        # Posição inicial sem a torre branca de a1.
        board = chess.Board("rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/1NBQKBNR b Kkq - 0 1")
        self.assertGreater(evaluate(board), 300)
        board.turn = chess.WHITE
        self.assertLess(evaluate(board), -300)

    @pendente
    def test_cavalo_no_centro_vale_mais_que_no_canto(self):
        centro = chess.Board("4k3/8/8/8/4N3/8/8/4K3 w - - 0 1")
        canto = chess.Board("4k3/8/8/8/8/8/8/N3K3 w - - 0 1")
        self.assertGreater(evaluate(centro), evaluate(canto))

    @pendente
    def test_posicao_espelhada_da_a_mesma_nota(self):
        board = chess.Board("r1bqkb1r/pppp1ppp/2n2n2/4p3/2B1P3/5N2/PPPP1PPP/RNBQK2R w KQkq - 4 4")
        self.assertEqual(evaluate(board), evaluate(board.mirror()))


if __name__ == "__main__":
    unittest.main()
