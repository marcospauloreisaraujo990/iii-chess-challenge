"""
Estrutura do projeto e regras fixas (card "Estrutura inicial do projeto e Configurações").

Estes testes já passam e devem continuar passando: se alguém mudar sem querer
um limite do regulamento (ex.: o book para 12 meios-lances), o teste acusa.
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tests import ROOT  # noqa: E402


class TestAmbiente(unittest.TestCase):
    def test_versao_do_python(self):
        self.assertGreaterEqual(sys.version_info[:2], (3, 8), "use Python 3.8 ou mais novo")

    def test_python_chess_instalado(self):
        try:
            import chess  # noqa: F401
        except ImportError:
            self.fail("python-chess não instalado: rode  pip install -r requirements.txt")

    def test_requirements_tem_somente_python_chess(self):
        with open(os.path.join(ROOT, "requirements.txt"), encoding="utf-8") as arquivo:
            pacotes = [linha.split("#")[0].strip() for linha in arquivo]
        pacotes = [p for p in pacotes if p]
        self.assertEqual(len(pacotes), 1, f"requirements.txt deve ter só o python-chess: {pacotes}")
        self.assertTrue(pacotes[0].lower().startswith("chess"), pacotes[0])


class TestPastasEModulos(unittest.TestCase):
    def test_pastas(self):
        for pasta in ("engine", "tests", "assets", "assets/book", "assets/syzygy", "logs"):
            self.assertTrue(os.path.isdir(os.path.join(ROOT, pasta)), f"falta a pasta {pasta}/")

    def test_contratos_dos_modulos(self):
        """Funções que os outros módulos usam: os nomes não podem mudar sem avisar a equipe."""
        import main
        from engine import book, evaluation, logger, search, syzygy, time_manager

        contratos = {
            evaluation: ["evaluate"],
            search: ["search", "SearchResult"],
            book: ["get_book_move"],
            syzygy: ["open_tablebase", "probe_wdl", "best_move", "close"],
            time_manager: ["compute_time_budget", "Clock", "parse_clock", "format_clock"],
            logger: ["start_game_log", "log_move", "log_event"],
            main: ["main", "game_loop", "read_opponent_move", "choose_our_move"],
        }
        for modulo, nomes in contratos.items():
            for nome in nomes:
                self.assertTrue(callable(getattr(modulo, nome, None)),
                                f"{modulo.__name__}.{nome} sumiu ou mudou de nome")


class TestRegrasFixas(unittest.TestCase):
    def test_book_so_ate_10_meios_lances(self):  # FAQ 3
        from engine import book
        self.assertEqual(book.MAX_BOOK_PLY, 10)

    def test_tablebases_ate_5_pecas(self):  # FAQ 4
        from engine import syzygy
        self.assertEqual(syzygy.MAX_PIECES, 5)

    def test_log_tem_8_campos(self):
        from engine import logger
        self.assertEqual(len(logger.FIELDS), 8)

    def test_valores_das_pecas_do_card(self):
        import chess
        from engine import evaluation
        esperado = {chess.PAWN: 100, chess.KNIGHT: 320, chess.BISHOP: 330,
                    chess.ROOK: 500, chess.QUEEN: 900}
        for peca, valor in esperado.items():
            self.assertEqual(evaluation.PIECE_VALUES[peca], valor)

    def test_controle_de_tempo_padrao_15_mais_10(self):
        from engine import time_manager
        self.assertEqual(time_manager.DEFAULT_INITIAL_S, 900)
        self.assertEqual(time_manager.DEFAULT_INCREMENT_S, 10)


if __name__ == "__main__":
    unittest.main()
