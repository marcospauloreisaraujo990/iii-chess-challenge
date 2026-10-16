"""Log .txt por partida: uma linha por lance, flush a cada lance. Dono: Junio.

Formato: 12 | brancas | g1f3 | prof 26 | nós 41203118 | aval +0.35 | pv g1f3 d7d5 c2c4 | 14.2 s
Lance de book: profundidade 0 e a palavra book no fim da linha.
"""
import os
import sys

LOG_EMERGENCIA = "log_emergencia.txt"


def abrir_log(caminho):
    """Abre (ou continua) o .txt da partida. Cria a pasta se precisar.

    Modo "a": se o programa reiniciar no meio da partida, o log antigo não é apagado.
    """
    try:
        pasta = os.path.dirname(caminho)
        if pasta:
            os.makedirs(pasta, exist_ok=True)
        return open(caminho, "a", encoding="utf-8")
    except OSError as erro:
        # Pasta sem permissão, disco cheio...: a partida não pode nem começar sem log?
        # Pode: cai para um arquivo ao lado do programa e avisa na tela.
        print(f"[log] não consegui abrir {caminho}: {erro}. Usando {LOG_EMERGENCIA}.", file=sys.stderr)
        try:
            return open(LOG_EMERGENCIA, "a", encoding="utf-8")
        except OSError as erro2:
            print(f"[log] nem o log de emergência abriu: {erro2}. Partida segue SEM log.", file=sys.stderr)
            return None


def _formatar_avaliacao(avaliacao):
    """Número vira +0.35 / -1.20 (peões). Texto (ex.: "#3" de mate) passa como está."""
    if isinstance(avaliacao, (int, float)):
        return f"{avaliacao:+.2f}"
    return str(avaliacao)


def _como_texto(valor):
    """Aceita texto, chess.Move ou lista deles (o python-chess devolve a PV como lista de Move)."""
    if isinstance(valor, str):
        return valor
    if hasattr(valor, "uci"):
        return valor.uci()
    return " ".join(_como_texto(item) for item in valor)


def registrar_lance(arquivo, numero, cor, lance_uci, profundidade, nos, avaliacao, pv, tempo_s, book=False):
    """Escreve a linha e dá flush imediatamente. Devolve True se gravou, False se falhou.

    Nada aqui pode derrubar a partida (travar = derrota): qualquer problema, seja de
    disco ou de dado estranho, vai para a tela e o jogo continua.
    """
    try:
        if book:
            profundidade = 0
        campos = [
            str(numero),
            cor,
            _como_texto(lance_uci),
            f"prof {profundidade}",
            f"nós {nos}",
            f"aval {_formatar_avaliacao(avaliacao)}",
            f"pv {_como_texto(pv)}",
            f"{tempo_s:.1f} s",
        ]
        if book:
            campos.append("book")
        arquivo.write(" | ".join(campos) + "\n")
        arquivo.flush()
        os.fsync(arquivo.fileno())
        return True
    except Exception as erro:
        print(f"[log] não consegui gravar o lance {numero}: {erro}", file=sys.stderr)
        return False
