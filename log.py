"""Log .txt por partida: uma linha por lance, flush a cada lance. Dono: Junio.

Formato: 12 | brancas | g1f3 | prof 26 | nós 41203118 | aval +0.35 | pv g1f3 d7d5 c2c4 | 14.2 s
Lance de book: profundidade 0 e a palavra book.
"""


def abrir_log(caminho):
    raise NotImplementedError


def registrar_lance(arquivo, numero, cor, lance_uci, profundidade, nos, avaliacao, pv, tempo_s, book=False):
    """Escreve a linha e dá flush imediatamente."""
    raise NotImplementedError
