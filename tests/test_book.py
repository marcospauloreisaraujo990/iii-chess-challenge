"""
Testes do opening book — card do Léo (Sprint 1).

Pendentes até get_book_move() ser implementada.
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import chess  # noqa: E402

from engine import book  # noqa: E402
from tests import pendente  # noqa: E402

# Ruy Lopez: 10 meios-lances (1.e4 e5 2.Nf3 Nc6 3.Bb5 a6 4.Ba4 Nf6 5.O-O Be7)
DEZ_MEIOS_LANCES = "e2e4 e7e5 g1f3 b8c6 f1b5 a7a6 b5a4 g8f6 e1g1 f8e7".split()


class TestBook(unittest.TestCase):
    @pendente
    def test_a_partir_do_meio_lance_10_devolve_none(self):  # FAQ 3
        board = chess.Board()
        for uci in DEZ_MEIOS_LANCES:
            board.push_uci(uci)
        self.assertEqual(board.ply(), 10)
        self.assertIsNone(book.get_book_move(board))

    @pendente
    def test_arquivo_inexistente_devolve_none_sem_erro(self):
        self.assertIsNone(book.get_book_move(chess.Board(), path="arquivo_que_nao_existe.bin"))

    # TODO (Léo), depois de baixar o assets/book/book.bin:
    #   - posição inicial devolve um lance legal
    #   - com 9 meios-lances (ply 9) o book ainda é consultado
    #   - posição fora do book devolve None


if __name__ == "__main__":
    unittest.main()
