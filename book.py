"""Opening book Polyglot local. Dono: Léo.

Regra do torneio: só até 10 meios-lances. Depois disso nunca consulta o book.

O arquivo book/book.bin é gerado por ferramentas/gerar_book.py a partir das aberturas da
Lichess (chess-openings, licença CC0). Aqui só LEMOS o arquivo: nada de rede.
"""
import random

import chess
import chess.polyglot

PLY_MAXIMO_BOOK = 10

# Um lance só entra no sorteio se tiver pelo menos esta fração do peso da posição. Evita
# jogar lances raros e fracos (h2h4, a2a4...) só porque aparecem em alguma abertura obscura.
# É escolha de qualidade de abertura, não de tempo. Na posição inicial deixa e4, d4, c4 e Nf3.
FRACAO_MINIMA_DO_PESO = 0.02


def lance_do_book(board, caminho_book, aleatorio=random):
    """Devolve um chess.Move do book só se board.ply() < 10; senão (ou se não achar) devolve None.

    Duas travas ANTES de abrir o arquivo (o partida.py tem uma terceira):
      1. board.ply() < 10: depois do meio-lance 10 nunca consulta o book.
      2. A partida precisa ter começado da posição inicial. Depois do comando `fen` o
         contador de lances zera, e consultar o book no meio da partida violaria a regra.

    O lance é sorteado pelo peso (lances mais comuns saem mais vezes). Qualquer problema
    com o arquivo (não existe, corrompido, sem permissão) devolve None: o programa joga
    normalmente, sem book. Nunca levanta erro.
    `aleatorio` existe para os testes poderem fixar a semente (ex.: random.Random(1)).
    """
    if board.ply() >= PLY_MAXIMO_BOOK:
        return None
    if board.root().fen() != chess.STARTING_FEN:
        return None
    try:
        with chess.polyglot.open_reader(caminho_book) as leitor:
            entradas = list(leitor.find_all(board))
    except Exception:
        return None
    if not entradas:
        return None
    maior = max(entrada.weight for entrada in entradas)
    candidatas = [e for e in entradas
                  if e.weight >= maior * FRACAO_MINIMA_DO_PESO and e.move in board.legal_moves]
    if not candidatas:
        return None
    pesos = [e.weight for e in candidatas]
    return aleatorio.choices(candidatas, weights=pesos, k=1)[0].move
