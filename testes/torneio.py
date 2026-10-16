"""Partidas automáticas entre duas versões do programa. Dono: Léo.

Relógio simulado + atraso artificial por lance (proporcional ao controle, ex.: 1 min + 1 s).
Alternar cores e começar de aberturas variadas do book.
No fim imprimir vitórias, empates, derrotas e o tempo médio que sobrou.
Comparações pedidas pelo Marcos: nossa gestão x tempo fixo por lance x gestão padrão do Stockfish.
Guardar os resultados em tabela (para a arguição técnica).
"""


def jogar_partida(versao_a, versao_b, abertura, perfil, atraso_s):
    raise NotImplementedError


def rodar_torneio(versao_a, versao_b, n_partidas, perfil):
    raise NotImplementedError


if __name__ == "__main__":
    raise SystemExit("implementar")
