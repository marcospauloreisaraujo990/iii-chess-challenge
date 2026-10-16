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

# Dama preta solta em d5, o peão de e4 captura (a torre garante que o final é ganho).
DAMA_SOLTA = "4k3/8/8/3q4/4P3/8/8/R3K3 w - - 0 1"

# Peão preto em d6 defendido pelo peão de c7: Dxd6 perde a dama.
PEAO_DEFENDIDO = "4k3/2p5/3p4/8/8/8/8/3QK3 w - - 0 1"

# Uma posição de meio-jogo qualquer (Italiana).
MEIO_JOGO = "r1bqkb1r/pppp1ppp/2n2n2/4p3/2B1P3/5N2/PPPP1PPP/RNBQK2R w KQkq - 4 4"


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

    @pendente
    def test_nao_altera_o_board_recebido(self):
        board = chess.Board(MEIO_JOGO)
        antes = (board.fen(), list(board.move_stack))
        search.search(board, time_limit_s=0.5)
        self.assertEqual((board.fen(), list(board.move_stack)), antes)

    @pendente
    def test_captura_peca_solta(self):
        resultado = search.search(chess.Board(DAMA_SOLTA), time_limit_s=1.0)
        self.assertEqual(resultado.move, chess.Move.from_uci("e4d5"))
        self.assertGreater(resultado.score, 500)

    @pendente
    def test_nao_entrega_peca_de_graca(self):
        """A quiescence vê a recaptura: não troca a dama por um peão defendido."""
        resultado = search.search(chess.Board(PEAO_DEFENDIDO), time_limit_s=1.0)
        self.assertNotEqual(resultado.move, chess.Move.from_uci("d1d6"))

    @pendente
    def test_sem_lances_devolve_none(self):
        mate = chess.Board("6k1/5ppp/8/8/8/8/5PPP/R5K1 w - - 0 1")
        mate.push_uci("a1a8")
        self.assertIsNone(search.search(mate, time_limit_s=0.5).move)

    @pendente
    def test_capturas_primeiro(self):
        board = chess.Board(DAMA_SOLTA)
        lances = search.order_moves(board)
        self.assertTrue(board.is_capture(lances[0]))


if __name__ == "__main__":
    unittest.main()
