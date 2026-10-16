"""
Testes automáticos. Rode a partir da pasta do projeto:

    python -m unittest discover -s tests -t . -v

ou pelo VS Code: aba Testes (ícone de frasco).

Cada card tem o seu arquivo de teste. Os testes dos cards ainda não
implementados aparecem como "skipped" (pendentes) em vez de falhar: o
decorador @pendente transforma NotImplementedError em skip. Quando o card for
implementado, o teste passa a valer automaticamente.
"""

import functools
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)


def pendente(teste):
    """Marca um teste de card ainda não implementado: NotImplementedError vira skip."""
    @functools.wraps(teste)
    def wrapper(self, *args, **kwargs):
        try:
            return teste(self, *args, **kwargs)
        except NotImplementedError as erro:
            self.skipTest(f"pendente: {erro}")
    return wrapper
