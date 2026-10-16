"""
Opening book local (Polyglot .bin) com limite estrito de 10 meios-lances.

Responsável: Léo
Sprint 1 · Card "Opening Book Local (.bin) com limite estrito" · Epic 1 (Regras) · 4 pontos

REGRA (FAQ, item 3)
-------------------
O book só pode decidir os 10 primeiros meios-lances da partida.
board.ply() conta os meios-lances já jogados: 0 = 1º lance das brancas,
1 = 1º das pretas, ..., 9 = 5º lance das pretas. Então:

    board.ply() <  10  ->  pode procurar no book
    board.ply() >= 10  ->  devolve None sem abrir o arquivo (o motor pensa sozinho)

Book não conta como autoria da equipe.

O que este módulo entrega (CONTRATO)
------------------------------------
    get_book_move(board, path=DEFAULT_BOOK_PATH) -> chess.Move ou None
        None quando: ply >= 10, arquivo não existe, posição fora do book ou
        qualquer erro de leitura. Nunca levanta exceção: a partida não pode cair.

Checklist do card
-----------------
    [ ] Baixar um Polyglot .bin leve e livre de direitos para assets/book/book.bin
        (anotar origem e licença em assets/book/LEIA.txt).
    [ ] Implementar get_book_move() com chess.polyglot.open_reader().
    [ ] Garantir a regra dos 10 meios-lances (testes em tests/test_book.py).
"""

from pathlib import Path
from typing import Optional, Union

import chess

MAX_BOOK_PLY = 10   # FAQ 3: book só nos meios-lances 1 a 10 (board.ply() de 0 a 9)

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_BOOK_PATH = ROOT / "assets" / "book" / "book.bin"


def get_book_move(board: chess.Board,
                  path: Union[str, Path] = DEFAULT_BOOK_PATH) -> Optional[chess.Move]:
    """Lance do book para a posição, ou None (ver regras no topo do arquivo)."""
    raise NotImplementedError("book.get_book_move() — Sprint 1, card do Léo")
