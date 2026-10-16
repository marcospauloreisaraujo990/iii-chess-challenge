"""
Testes da gestão de tempo — card do Junio (Sprint 2 e Sprint 3).

Pendentes até o time_manager ser implementado.
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine import time_manager  # noqa: E402
from tests import pendente  # noqa: E402


class TestTimeManager(unittest.TestCase):
    @pendente
    def test_orcamento_positivo_e_bem_menor_que_o_relogio(self):
        tempo = time_manager.compute_time_budget(900, 10, 1)
        self.assertGreater(tempo, 0)
        self.assertLess(tempo, 900 / 4)

    @pendente
    def test_relogio_quase_zerado_nao_estoura(self):
        self.assertLess(time_manager.compute_time_budget(8, 0, 40), 8)

    @pendente
    def test_parse_clock(self):
        self.assertEqual(time_manager.parse_clock("12:34"), 754)

    @pendente
    def test_clock_sync(self):
        relogio = time_manager.Clock()
        relogio.sync(600)
        self.assertEqual(relogio.remaining_s, 600)

    # TODO (Junio): Clock.spend() desconta o tempo + atraso e soma o incremento.


if __name__ == "__main__":
    unittest.main()
