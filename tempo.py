"""Gestão de tempo própria (componente autoral). Dono: Marcos Paulo.

Decide quanto tempo o Stockfish pensa em cada lance e quando parar.
NÃO implementar a lógica aqui: apenas o esqueleto. Os números finais saem dos testes.
"""

# (tempo inicial em segundos, incremento em segundos por lance)
PERFIS = {
    "15+10": (900, 10),
    "25+0": (1500, 0),
    "armageddon_brancas": (300, 0),
    "armageddon_pretas": (240, 0),
}


def calcular_tempo(restante_s, incremento_s, numero_lance, atraso_humano_s):
    """Devolve (alvo_s, maximo_s) para o lance atual.

    Ideia (ponto de partida, ajustar com testes): alvo = restante / lances que ainda
    devem faltar (estimativa decrescente com mínimo) + parte do incremento, descontando
    o atraso humano; máximo = algumas vezes o alvo, nunca uma fatia grande do relógio.
    Invariante: com poucos segundos no relógio, nunca pede mais do que pode gastar.
    """
    raise NotImplementedError


def deve_parar(decorrido_s, alvo_s, maximo_s, profundidades_estaveis, melhor_lance_mudou, avaliacao_caiu):
    """Chamada a cada profundidade (engine.analysis). True = parar a busca.

    Passou do alvo e melhor lance estável há algumas profundidades -> para.
    Melhor lance mudou ou avaliação caiu -> continua até o máximo.
    Chegou ao máximo -> para sempre.
    """
    raise NotImplementedError


def atalho_tempo_zero(board, lance_book, em_tablebase):
    """Lance imediato: único lance legal, lance de book ou posição de tablebase. None se não houver."""
    raise NotImplementedError


def modo_economia(historico_avaliacoes, material_restante):
    """True se avaliação perto de zero por muitos lances com pouco material (cortar alvo pela metade)."""
    raise NotImplementedError


def sincronizar(texto_comando):
    """Interpreta 't 12:34' e devolve o tempo restante em segundos (corrige o relógio interno)."""
    raise NotImplementedError
