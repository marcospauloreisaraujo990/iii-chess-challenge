#!/usr/bin/env python3
"""
Programa da mesa — III Chess Challenge (Equipe ICEV).

Responsável: Junio
Sprint 1 · Card "CLI Principal, Entradas e Sistema de Logs" · 4 pontos
Sprint 3 · Card "Ligar comandos de emergência na mesa" · 3 pontos

Fluxo de um lance NOSSO (como os módulos se conectam)
-----------------------------------------------------
    1. book.get_book_move(board)               -> lance ou None  (só até o meio-lance 10)
    2. syzygy.best_move(board)                 -> lance ou None  (só com 5 peças ou menos)
    3. time_manager.compute_time_budget(...)   -> segundos para pensar
       search.search(board, segundos)          -> SearchResult
    4. logger.log_move(...)                    -> linha com os 8 campos
    5. anunciar o lance em UCI, bem visível (ex.: e7e8q)

Fluxo de um lance do ADVERSÁRIO
-------------------------------
    ler o texto em UCI -> validar contra board.legal_moves -> aplicar.
    Entrada errada NUNCA derruba o programa: avisa e pede de novo.

Checklist (Sprint 1)
    [ ] game_loop(): loop alternando Brancas e Pretas.
    [ ] read_opponent_move(): UCI validado contra board.legal_moves, sem crash.
    [ ] Gravar o log a cada lance nosso (engine/logger.py).
Checklist (Sprint 3)
    [ ] Comando  desfazer  (board.pop()).
    [ ] Comando  t mm:ss   (sincroniza o relógio virtual com o físico).
    [ ] Mostrar com destaque o lance que devemos falar em voz alta (ex.: e7e8q).

Uso:
    python main.py
    python main.py --cor brancas --tempo 15+10
"""

import argparse
import sys
from typing import List, Optional

import chess

from engine import book, logger, search, syzygy, time_manager  # noqa: F401  (usados no loop)
from engine.search import SearchResult


def parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Programa da mesa do III Chess Challenge.")
    parser.add_argument("--cor", choices=["brancas", "pretas"],
                        help="nossa cor (se faltar, o programa pergunta)")
    parser.add_argument("--tempo", default="15+10",
                        help="controle de tempo em minutos+incremento (padrão 15+10)")
    return parser.parse_args(argv)


def read_opponent_move(board: chess.Board) -> chess.Move:
    """Pede o lance do adversário em UCI até receber um lance legal."""
    raise NotImplementedError("main.read_opponent_move() — Sprint 1, card do Junio")


def choose_our_move(board: chess.Board, clock: time_manager.Clock) -> SearchResult:
    """Book -> tablebase -> busca, nessa ordem (ver o fluxo no topo do arquivo)."""
    raise NotImplementedError("main.choose_our_move() — Sprint 1/2, card do Junio")


def announce(board: chess.Board, result: SearchResult) -> None:
    """Mostra com destaque o lance que vamos falar e mover."""
    raise NotImplementedError("main.announce() — Sprint 3, card do Junio")


def handle_command(text: str, board: chess.Board, clock: time_manager.Clock) -> bool:
    """Trata comandos da mesa (desfazer, t mm:ss...). True se o texto era um comando."""
    raise NotImplementedError("main.handle_command() — Sprint 3, card do Junio")


def game_loop(args: argparse.Namespace) -> None:
    """Loop principal da partida."""
    raise NotImplementedError("main.game_loop() — Sprint 1, card do Junio")


def main(argv: Optional[List[str]] = None) -> int:
    args = parse_args(argv)
    print("=== III Chess Challenge — Equipe ICEV (Marcos Paulo, Junio e Léo) ===")
    print(f"python-chess {chess.__version__} | cor: {args.cor or 'a definir'} | tempo: {args.tempo}\n")
    print(chess.Board())
    try:
        game_loop(args)
    except NotImplementedError as pendente:
        # Enquanto o projeto é esqueleto: mostra o que falta em vez de um traceback.
        # (Junio: quando o loop estiver pronto, este except pode sair.)
        print(f"\nAmbiente OK. Próximo passo: {pendente}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
