"""
Testes do log da banca — card do Junio (Sprint 1).

Pendentes até o logger ser implementado. Se a equipe mudar o formato da linha
(ver engine/logger.py), ajuste este teste junto.
"""

import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import chess  # noqa: E402

from engine import logger  # noqa: E402
from tests import pendente  # noqa: E402


class TestLogger(unittest.TestCase):
    @pendente
    def test_linha_tem_os_8_campos_na_ordem(self):
        with tempfile.TemporaryDirectory() as pasta:
            caminho = logger.start_game_log("brancas", "15+10", log_dir=pasta)
            pv = [chess.Move.from_uci("e2e4"), chess.Move.from_uci("e7e5")]
            linha = logger.log_move(1, "Brancas", "e2e4", 5, 12345, 30, pv, 1.5)

            partes = linha.split(" | ")
            self.assertEqual(len(partes), 8, linha)
            for campo, parte in zip(logger.FIELDS, partes):
                self.assertTrue(parte.startswith(campo + "="), f"esperava {campo}=..., veio {parte}")

            with open(caminho, encoding="utf-8") as arquivo:
                self.assertIn(linha, arquivo.read(), "a linha precisa estar gravada no arquivo")

    # TODO (Junio):
    #   - log_event() grava linha começando com "#"
    #   - avaliação de mate aparece de forma legível (ex.: "mate em 3")
    #   - erro de gravação (pasta sem permissão) não levanta exceção


if __name__ == "__main__":
    unittest.main()
