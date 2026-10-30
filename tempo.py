"""Gestão de tempo própria (componente autoral). Dono: Marcos Paulo.

Decide quanto tempo o Stockfish pensa em cada lance e quando parar.

Ideia em uma frase: dividir o relógio que sobra pelos lances que ainda devem
faltar, somar o incremento, descontar o tempo que a gente gasta na mesa
(anunciar, mover a peça, apertar o relógio, digitar) e nunca arriscar a
partida num único lance.

Como o partida.py usa este arquivo (caminho de um lance):
    1. atalho_tempo_zero()  -> lance na hora, sem pensar (lance único ou book).
    2. calcular_tempo()     -> (alvo, máximo) do lance.
       O máximo vai para o Stockfish como limite DURO (Limit(time=máximo)).
    3. deve_parar()         -> chamado a cada profundidade nova que o Stockfish
       termina. Passou do alvo e o lance está firme: para. Ainda em dúvida:
       continua até o máximo.
    4. sincronizar()        -> comando "t mm:ss" para acertar o relógio interno
       com o relógio físico da mesa.
"""

import re

import chess

# (tempo inicial em segundos, incremento em segundos por lance)
PERFIS = {
    "15+10": (900, 10),
    "25+0": (1500, 0),
    "armageddon_brancas": (300, 0),
    "armageddon_pretas": (240, 0),
}

# ----------------------------------------------------------------------------------
# VALORES INICIAIS. Todos os números da gestão de tempo ficam aqui, num lugar só,
# para o Léo calibrar com testes/torneio.py (regra 4 do CLAUDE.md). O motivo de
# cada valor inicial está ao lado.
# ----------------------------------------------------------------------------------

# Quantos lances ainda devem faltar: LANCES_ESPERADOS - número do lance, mas
# nunca menos que o mínimo. Até o lance 45 a estimativa cai (na abertura
# pensamos menos, guardando relógio para o meio-jogo); depois fica fixa em 55.
# Sem incremento (25+0, armageddon) o mínimo é o que impede o relógio de acabar
# numa partida longa: nas simulações, com mínimo 20 o 25+0 estourava perto do
# lance 80; com 40 passa do lance 120 (atraso de 5 s por lance).
#
# CALIBRAÇÃO de 29/10 (testes/resultados/velocidade_*.md): os valores iniciais eram
# 70/40 (~15 s por lance no 15+10). Com o atraso humano MEDIDO no ensaio (12 s), 8
# partidas por configuração contra o Stockfish com a gestão de tempo dele:
#     70/40  ~15 s/lance   6,5 pontos   0 derrotas nossas por tempo
#    100/55  ~10 s/lance   7   pontos   0 derrotas nossas por tempo   <- escolhido
#    130/70  ~7,5 s/lance  7   pontos   0 derrotas nossas por tempo
# Escolhido 100/55: um terço mais rápido, sem perder no tempo e sem perder pontos.
# Mais lances restantes = alvo menor = resposta mais rápida. O adversário perdeu
# por tempo 17 vezes em 24 partidas; nós, nenhuma.
LANCES_ESPERADOS = 100
LANCES_RESTANTES_MINIMO = 55

# Reserva que nunca é usada para pensar: o colchão contra imprevisto (Stockfish
# demorar para responder, operador errar a digitação). É uma fração do relógio,
# com piso (a demora do Stockfish não diminui quando o relógio diminui) e teto
# (para não desperdiçar tempo no início da partida). O piso deve ser conferido
# medindo quanto o Limit(time=...) passa do pedido na máquina do torneio.
RESERVA_FRACAO = 0.05
RESERVA_MINIMA_S = 1.0
RESERVA_MAXIMA_S = 10.0

# O máximo do lance é algumas vezes o alvo (para posições difíceis), mas nunca
# mais que uma fatia do relógio disponível.
FATOR_MAXIMO = 2.5
FRACAO_MAXIMA_DO_RELOGIO = 0.2

# Menor tempo que pedimos ao motor. Com o relógio quase zerado, ainda assim
# pedimos um lance rápido em vez de zero (zero não é um tempo válido).
TEMPO_MINIMO_S = 0.05

# Lance "firme": quantas profundidades SEGUIDAS repetiram o melhor lance da
# anterior (o partida.py conta 0 na primeira). Com 2, o mesmo lance apareceu em
# 3 profundidades seguidas.
PROFUNDIDADES_ESTAVEIS = 2

# Modo economia: final calmo (avaliação perto de zero por muitos lances e pouco
# material). Nessas posições pensar muito raramente muda o resultado.
ECONOMIA_LANCES = 10
ECONOMIA_AVALIACAO_CP = 30
ECONOMIA_MATERIAL_CP = 2600   # material das DUAS cores, sem os reis, em centipawns
FATOR_ECONOMIA = 0.5          # quem chama corta o alvo por este fator


def calcular_tempo(restante_s, incremento_s, numero_lance, atraso_humano_s):
    """Devolve (alvo_s, maximo_s) para o lance atual.

    restante_s      : quanto falta no NOSSO relógio agora.
    incremento_s    : quanto o relógio soma depois de cada lance nosso.
    numero_lance    : número do lance (board.fullmove_number, começa em 1).
    atraso_humano_s : tempo que a equipe gasta na mesa por lance.

    Conta, passo a passo:
        disponível = restante - atraso - reserva
        alvo       = disponível / lances_restantes + incremento - atraso
        máximo     = min(alvo × FATOR_MAXIMO, disponível × FRACAO_MAXIMA)

    Por que o atraso aparece duas vezes: a primeira (em "disponível") garante
    que, mesmo neste lance, sobra tempo para anunciar e apertar o relógio. A
    segunda (em "alvo") é o custo de cada lance futuro: o incremento só vira
    tempo de pensar depois de pagar o tempo da mesa. No 25+0 o incremento é
    zero, então o atraso sai inteiro do alvo.

    Invariante: o máximo nunca passa de restante - atraso - reserva, ou seja,
    sobra tempo para a mesa. A única exceção é o relógio já no limite (sem
    sobra nem para a mesa): aí devolvemos TEMPO_MINIMO_S, o lance mais rápido
    possível, e o partida.py ainda corta para busca de profundidade 1.
    """
    restante_s = float(restante_s)
    incremento_s = max(0.0, float(incremento_s))
    atraso_humano_s = max(0.0, float(atraso_humano_s))
    numero_lance = max(1, int(numero_lance))

    reserva = min(RESERVA_MAXIMA_S, max(RESERVA_MINIMA_S, restante_s * RESERVA_FRACAO))
    disponivel = restante_s - atraso_humano_s - reserva
    if disponivel <= TEMPO_MINIMO_S:
        # Relógio no limite: lance o mais rápido possível.
        return TEMPO_MINIMO_S, TEMPO_MINIMO_S

    lances_restantes = max(LANCES_RESTANTES_MINIMO, LANCES_ESPERADOS - numero_lance)
    alvo = disponivel / lances_restantes + incremento_s - atraso_humano_s
    maximo = min(alvo * FATOR_MAXIMO, disponivel * FRACAO_MAXIMA_DO_RELOGIO)

    # Piso e teto: nunca abaixo do mínimo, nunca acima do que dá para gastar,
    # e o alvo nunca passa do máximo.
    maximo = min(max(maximo, TEMPO_MINIMO_S), disponivel)
    alvo = min(max(alvo, TEMPO_MINIMO_S), maximo)
    return alvo, maximo


def deve_parar(decorrido_s, alvo_s, maximo_s, profundidades_estaveis, melhor_lance_mudou, avaliacao_caiu):
    """Chamada a cada profundidade (engine.analysis). True = parar a busca.

    Ordem das perguntas:
        1. Chegou ao máximo?            -> para sempre (o relógio vem primeiro).
        2. Ainda não chegou ao alvo?    -> continua.
        3. Melhor lance mudou ou a avaliação caiu? -> continua até o máximo:
           o motor achou algo novo e merece mais tempo para confirmar.
        4. Lance firme há PROFUNDIDADES_ESTAVEIS profundidades? -> para.
    """
    if decorrido_s >= maximo_s:
        return True
    if decorrido_s < alvo_s:
        return False
    if melhor_lance_mudou or avaliacao_caiu:
        return False
    return profundidades_estaveis >= PROFUNDIDADES_ESTAVEIS


def atalho_tempo_zero(board, lance_book, em_tablebase):
    """Lance imediato: lance de book ou único lance legal. None se não houver.

    Hoje o partida.py consulta o book antes e passa lance_book=None, então quem
    decide aqui na prática é o lance único. Os dois parâmetros ficam como ganchos
    do contrato (CLAUDE.md), para o caso de o book passar a ser consultado aqui.

    Posição de tablebase (5 peças ou menos) NÃO devolve lance aqui: este arquivo
    não sabe qual é o lance certo, só o Stockfish (que lê as tablebases) sabe.
    Nesse caso devolvemos None e o Stockfish decide; com as tablebases ele acha
    o resultado quase na hora e o deve_parar encerra no alvo.
    """
    legais = list(board.legal_moves)
    if lance_book is not None and lance_book in legais:
        return lance_book
    if len(legais) == 1:
        return legais[0]
    return None


def modo_economia(historico_avaliacoes, material_restante):
    """True se avaliação perto de zero por muitos lances com pouco material.

    historico_avaliacoes : avaliações dos nossos últimos lances, em centipawns.
                           Mate ("#3"), None ou qualquer coisa que não é número
                           conta como posição NÃO calma: sem economia.
    material_restante    : material das duas cores sem os reis, em centipawns
                           (use material_em_centipawns(board)).
    Quando True, quem chama corta o alvo por FATOR_ECONOMIA.
    """
    ultimas = list(historico_avaliacoes)[-ECONOMIA_LANCES:]
    if len(ultimas) < ECONOMIA_LANCES or material_restante > ECONOMIA_MATERIAL_CP:
        return False
    numero = (int, float)
    return all(isinstance(a, numero) and not isinstance(a, bool) and abs(a) <= ECONOMIA_AVALIACAO_CP
               for a in ultimas)


def material_em_centipawns(board):
    """Material das duas cores, sem os reis (peão 100, cavalo e bispo 300, torre 500, dama 900)."""
    valores = {chess.PAWN: 100, chess.KNIGHT: 300, chess.BISHOP: 300, chess.ROOK: 500, chess.QUEEN: 900}
    return sum(valores.get(peca.piece_type, 0) for peca in board.piece_map().values())


_FORMATO_T = re.compile(r"^\s*t\s+(?:([0-9]+):)?([0-9]{1,3}):([0-9]{2})\s*$", re.IGNORECASE)


def sincronizar(texto_comando):
    """Interpreta 't 12:34' e devolve o tempo restante em segundos (corrige o relógio interno).

    Aceita "t mm:ss" (t 12:34 -> 754) e "t h:mm:ss" (t 1:02:03 -> 3723).
    Os segundos (e os minutos, no formato com hora) vão de 00 a 59.
    "t 0:00" devolve 0, que o partida.py recusa (o relógio só aceita > 0).
    Qualquer outra coisa levanta ValueError com a explicação, que o partida.py
    mostra na tela sem mexer no relógio.
    """
    achou = _FORMATO_T.match(texto_comando or "")
    if not achou:
        raise ValueError(f"use t mm:ss (exemplo: t 12:34), recebido {texto_comando!r}")
    horas, minutos, segundos = (int(g) if g else 0 for g in achou.groups())
    if segundos > 59 or (achou.group(1) is not None and minutos > 59):
        raise ValueError(f"minutos e segundos vão de 00 a 59, recebido {texto_comando!r}")
    return horas * 3600 + minutos * 60 + segundos
