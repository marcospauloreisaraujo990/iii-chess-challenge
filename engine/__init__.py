"""
Motor de xadrez da Equipe ICEV — III Chess Challenge.
Marcos Paulo · Junio · Léo

Módulos (dono · sprint):
    evaluation.py    Marcos · Sprint 1   avaliação heurística (AUTORAL)
    search.py        Marcos · Sprint 2   Negamax + Alfa-Beta + aprofundamento iterativo (AUTORAL)
    book.py          Léo    · Sprint 1   opening book Polyglot, só até o meio-lance 10
    syzygy.py        Léo    · Sprint 2   tablebases de finais, até 5 peças
    time_manager.py  Junio  · Sprint 2   gestão de tempo (orçamento por lance)
    logger.py        Junio  · Sprint 1   log da partida com os 8 campos

O programa da mesa (main.py, Junio) junta tudo. O fluxo completo está no README.
"""
