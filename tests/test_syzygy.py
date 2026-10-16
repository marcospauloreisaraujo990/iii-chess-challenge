"""
Testes das tablebases — card do Léo (Sprint 2).

Pendentes até o syzygy.py ser implementado.
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import chess  # noqa: E402

from engine import syzygy  # noqa: E402
from tests import pendente  # noqa: E402


class TestSyzygy(unittest.TestCase):
    @pendente
    def test_mais_de_5_pecas_devolve_none(self):  # FAQ 4
        self.assertIsNone(syzygy.probe_wdl(chess.Board()))

    # TODO (Léo), depois de baixar as tabelas em assets/syzygy/:
    #   - KQ x K (ex.: "8/8/8/8/8/8/1Q6/K6k w - - 0 1") é vitória (probe_wdl == 2)
    #   - best_move() devolve lance legal
    #   - nenhum arquivo da pasta tem mais de 5 peças


if __name__ == "__main__":
    unittest.main()
