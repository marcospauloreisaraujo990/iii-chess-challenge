"""Opening book Polyglot local. Dono: Léo.

Regra do torneio: só até 10 meios-lances. Depois disso nunca consulta o book.
"""
import chess
import chess.polyglot


def lance_do_book(board, caminho_book):
    """Devolve um chess.Move do book só se board.ply() < 10; senão (ou se não achar) devolve None."""
    raise NotImplementedError
