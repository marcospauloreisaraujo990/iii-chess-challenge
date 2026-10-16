"""
Função de avaliação heurística — COMPONENTE AUTORAL DA EQUIPE.

Responsável: Marcos Paulo
Sprint 1 · Card "Representação e Função de Avaliação Heurística" · Epic 1 (Inteligência) · 4 pontos

O que este módulo entrega para o resto do motor (CONTRATO)
----------------------------------------------------------
    evaluate(board) -> int
        Nota da posição em centipawns (100 = um peão), do ponto de vista de
        QUEM VAI JOGAR AGORA (board.turn). Positivo = bom para quem joga.
        É a convenção do Negamax: search.py (Sprint 2) chama evaluate() nas
        folhas da árvore e só inverte o sinal ao voltar um nível.

    PIECE_VALUES, MATE_SCORE, MATE_THRESHOLD
        Usados também pela busca (ordenar capturas, pontuar mate) e pelo log.

Checklist do card
-----------------
    [x] Usar python-chess para percorrer as peças do tabuleiro
        (board.piece_map() ou board.pieces(tipo, cor)).
    [x] Pontuação por material com os valores de PIECE_VALUES.
    [x] Tabelas de casas (PST): bônus para cavalos e peões centralizados e
        para o rei protegido. Preencher PST abaixo.
    [x] Testes em tests/test_evaluation.py: posição com peça a mais recebe nota maior.
"""

from typing import Dict, List

import chess

# Valores do card, em centipawns. O rei não tem valor material.
PIECE_VALUES: Dict[int, int] = {
    chess.PAWN: 100,
    chess.KNIGHT: 320,
    chess.BISHOP: 330,
    chess.ROOK: 500,
    chess.QUEEN: 900,
    chess.KING: 0,
}

# Nota de mate. Convenção sugerida para a busca: mate em N meios-lances = MATE_SCORE - N
# (assim o motor prefere o mate mais rápido). |nota| >= MATE_THRESHOLD significa mate.
MATE_SCORE = 100_000
MATE_THRESHOLD = 90_000

# Tabelas de casas (Piece-Square Tables), uma por tipo de peça.
#
# Formato combinado: lista de 64 inteiros indexada por chess.Square
# (a1 = 0, b1 = 1, ..., h1 = 7, a2 = 8, ..., h8 = 63), do ponto de vista das BRANCAS.
# Para uma peça preta, consulte PST[tipo][chess.square_mirror(casa)].
#
# Valores baseados na "Simplified Evaluation Function" (Chess Programming Wiki).
# Abaixo as tabelas estão escritas como se vê o tabuleiro (8ª fileira em cima,
# coluna a à esquerda) para ficarem legíveis; _por_casa() converte para a ordem
# de chess.Square.


def _por_casa(tabela_visual: List[int]) -> List[int]:
    """Converte uma tabela escrita da 8ª fileira para a 1ª em índices a1..h8."""
    fileiras = [tabela_visual[i:i + 8] for i in range(0, 64, 8)]
    return [valor for fileira in reversed(fileiras) for valor in fileira]


_PEAO = [
     0,   0,   0,   0,   0,   0,   0,   0,
    50,  50,  50,  50,  50,  50,  50,  50,
    10,  10,  20,  30,  30,  20,  10,  10,
     5,   5,  10,  25,  25,  10,   5,   5,
     0,   0,   0,  20,  20,   0,   0,   0,
     5,  -5, -10,   0,   0, -10,  -5,   5,
     5,  10,  10, -20, -20,  10,  10,   5,
     0,   0,   0,   0,   0,   0,   0,   0,
]

_CAVALO = [
    -50, -40, -30, -30, -30, -30, -40, -50,
    -40, -20,   0,   0,   0,   0, -20, -40,
    -30,   0,  10,  15,  15,  10,   0, -30,
    -30,   5,  15,  20,  20,  15,   5, -30,
    -30,   0,  15,  20,  20,  15,   0, -30,
    -30,   5,  10,  15,  15,  10,   5, -30,
    -40, -20,   0,   5,   5,   0, -20, -40,
    -50, -40, -30, -30, -30, -30, -40, -50,
]

_BISPO = [
    -20, -10, -10, -10, -10, -10, -10, -20,
    -10,   0,   0,   0,   0,   0,   0, -10,
    -10,   0,   5,  10,  10,   5,   0, -10,
    -10,   5,   5,  10,  10,   5,   5, -10,
    -10,   0,  10,  10,  10,  10,   0, -10,
    -10,  10,  10,  10,  10,  10,  10, -10,
    -10,   5,   0,   0,   0,   0,   5, -10,
    -20, -10, -10, -10, -10, -10, -10, -20,
]

_TORRE = [
     0,   0,   0,   0,   0,   0,   0,   0,
     5,  10,  10,  10,  10,  10,  10,   5,
    -5,   0,   0,   0,   0,   0,   0,  -5,
    -5,   0,   0,   0,   0,   0,   0,  -5,
    -5,   0,   0,   0,   0,   0,   0,  -5,
    -5,   0,   0,   0,   0,   0,   0,  -5,
    -5,   0,   0,   0,   0,   0,   0,  -5,
     0,   0,   0,   5,   5,   0,   0,   0,
]

_DAMA = [
    -20, -10, -10,  -5,  -5, -10, -10, -20,
    -10,   0,   0,   0,   0,   0,   0, -10,
    -10,   0,   5,   5,   5,   5,   0, -10,
     -5,   0,   5,   5,   5,   5,   0,  -5,
      0,   0,   5,   5,   5,   5,   0,  -5,
    -10,   5,   5,   5,   5,   5,   0, -10,
    -10,   0,   5,   0,   0,   0,   0, -10,
    -20, -10, -10,  -5,  -5, -10, -10, -20,
]

# Rei no meio-jogo: protegido atrás dos peões, na ala do roque.
_REI = [
    -30, -40, -40, -50, -50, -40, -40, -30,
    -30, -40, -40, -50, -50, -40, -40, -30,
    -30, -40, -40, -50, -50, -40, -40, -30,
    -30, -40, -40, -50, -50, -40, -40, -30,
    -20, -30, -30, -40, -40, -30, -30, -20,
    -10, -20, -20, -20, -20, -20, -20, -10,
     20,  20,   0,   0,   0,   0,  20,  20,
     20,  30,  10,   0,   0,  10,  30,  20,
]

PST: Dict[int, List[int]] = {
    chess.PAWN: _por_casa(_PEAO),
    chess.KNIGHT: _por_casa(_CAVALO),
    chess.BISHOP: _por_casa(_BISPO),
    chess.ROOK: _por_casa(_TORRE),
    chess.QUEEN: _por_casa(_DAMA),
    chess.KING: _por_casa(_REI),
}


def evaluate(board: chess.Board) -> int:
    """Nota da posição em centipawns, do ponto de vista de board.turn.

    nota_brancas = (material + PST das brancas) - (material + PST das pretas),
    com o sinal invertido quando são as pretas que jogam.

    Mate e afogamento ficam com a busca (search.py), que os detecta antes de
    chamar evaluate().
    """
    nota_brancas = 0
    for casa, peca in board.piece_map().items():
        tipo = peca.piece_type
        if peca.color == chess.WHITE:
            nota_brancas += PIECE_VALUES[tipo] + PST[tipo][casa]
        else:
            nota_brancas -= PIECE_VALUES[tipo] + PST[tipo][chess.square_mirror(casa)]
    return nota_brancas if board.turn == chess.WHITE else -nota_brancas
