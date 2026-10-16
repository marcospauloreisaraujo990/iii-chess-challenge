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
    [ ] Usar python-chess para percorrer as peças do tabuleiro
        (board.piece_map() ou board.pieces(tipo, cor)).
    [ ] Pontuação por material com os valores de PIECE_VALUES.
    [ ] Tabelas de casas (PST): bônus para cavalos e peões centralizados e
        para o rei protegido. Preencher PST abaixo.
    [ ] Testes em tests/test_evaluation.py: posição com peça a mais recebe nota maior.
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
# TODO (Marcos): trocar os zeros pelos bônus e penalidades de cada casa.
PST: Dict[int, List[int]] = {tipo: [0] * 64 for tipo in PIECE_VALUES}


def evaluate(board: chess.Board) -> int:
    """Nota da posição em centipawns, do ponto de vista de board.turn.

    Ideia geral (a implementar):
        nota_brancas = (material + PST das brancas) - (material + PST das pretas)
        return nota_brancas se board.turn == chess.WHITE, senão -nota_brancas

    Sugestão: mate e afogamento ficam com a busca (search.py), que os detecta
    antes de chamar evaluate().
    """
    raise NotImplementedError("evaluation.evaluate() — Sprint 1, card do Marcos")
