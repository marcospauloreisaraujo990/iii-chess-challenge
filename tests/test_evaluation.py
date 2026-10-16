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

    # TODO (Marcos):
    #   - peça a mais para as pretas
    #   - cavalo no centro vale mais que cavalo no canto (PST)
    #   - posição espelhada (chess.Board.mirror) dá a mesma nota


if __name__ == "__main__":
    unittest.main()
