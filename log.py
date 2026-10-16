"""Log .txt por partida: uma linha por lance, flush a cada lance. Dono: Junio.

Formato: 12 | brancas | g1f3 | prof 26 | nós 41203118 | aval +0.35 | pv g1f3 d7d5 c2c4 | 14.2 s
Lance de book: profundidade 0 e a palavra book no fim da linha.
"""
import os
import sys


def abrir_log(caminho):
    """Abre (ou continua) o .txt da partida. Cria a pasta se precisar.

    Modo "a": se o programa reiniciar no meio da partida, o log antigo não é apagado.
    """
    pasta = os.path.dirname(caminho)
    if pasta:
        os.makedirs(pasta, exist_ok=True)
    return open(caminho, "a", encoding="utf-8")


def _formatar_avaliacao(avaliacao):
    """Número vira +0.35 / -1.20 (peões). Texto (ex.: "#3" de mate) passa como está."""
    if isinstance(avaliacao, (int, float)):
        return f"{avaliacao:+.2f}"
    return str(avaliacao)


def registrar_lance(arquivo, numero, cor, lance_uci, profundidade, nos, avaliacao, pv, tempo_s, book=False):
    """Escreve a linha e dá flush imediatamente. Devolve True se gravou, False se falhou.

    Falha de disco não pode derrubar a partida (travar = derrota): o erro vai para a
    tela e o jogo continua.
    """
    if book:
        profundidade = 0
    if not isinstance(pv, str):
        pv = " ".join(pv)
    campos = [
        str(numero),
        cor,
        lance_uci,
        f"prof {profundidade}",
        f"nós {nos}",
        f"aval {_formatar_avaliacao(avaliacao)}",
        f"pv {pv}",
        f"{tempo_s:.1f} s",
    ]
    if book:
        campos.append("book")
    try:
        arquivo.write(" | ".join(campos) + "\n")
        arquivo.flush()
        os.fsync(arquivo.fileno())
        return True
    except (OSError, ValueError) as erro:
        print(f"[log] não consegui gravar o lance {numero}: {erro}", file=sys.stderr)
        return False
