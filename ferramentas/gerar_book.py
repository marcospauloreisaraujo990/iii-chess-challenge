"""Gera o opening book Polyglot (book/book.bin) a partir de aberturas de domínio público.

Origem dos dados: https://github.com/lichess-org/chess-openings (licença CC0, domínio
público). Os arquivos a.tsv ... e.tsv ficam em ferramentas/dados/chess-openings/ junto com
o texto da licença, então gerar o book NÃO precisa de internet.

Como funciona, em linguagem simples:
  - Cada linha dos arquivos é uma abertura com nome e a sequência de lances (PGN).
  - Para cada abertura, percorremos os lances até o meio-lance 10 (regra do torneio).
  - Para cada (posição, lance jogado nela) contamos em quantas aberturas aquele lance
    aparece. Esse número é o PESO: lances muito usados pesam mais e são sorteados mais
    vezes (book.py sorteia pelo peso).
  - Gravamos no formato Polyglot (.bin): uma lista ordenada de entradas de 16 bytes.

Formato de cada entrada Polyglot (big-endian):
    chave (8 bytes, hash Zobrist da posição) | lance (2) | peso (2) | aprendizado (4, não usamos)
    lance, 16 bits: destino-coluna(3) destino-linha(3) origem-coluna(3) origem-linha(3) promoção(3)
    roque é guardado como "rei vai até a torre" (e1h1, e1a1, e8h8, e8a8).

Uso:
    python ferramentas/gerar_book.py                    # gera book/book.bin
    python ferramentas/gerar_book.py --saida outro.bin
    python ferramentas/gerar_book.py --baixar           # busca de novo os .tsv na internet
"""
import argparse
import collections
import csv
import glob
import io
import os
import struct
import sys
import urllib.request

import chess
import chess.pgn
import chess.polyglot

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PASTA_TSV = os.path.join(RAIZ, "ferramentas", "dados", "chess-openings")
SAIDA_PADRAO = os.path.join(RAIZ, "book", "book.bin")
URL_BASE = "https://raw.githubusercontent.com/lichess-org/chess-openings/master/"

# Regra do torneio: o book só vale até o meio-lance 10. A última posição de onde um lance
# do book sai tem board.ply() == 9, então gravamos lances jogados a partir de ply 0..9.
PLY_MAXIMO_BOOK = 10
PESO_MAXIMO = 0xFFFF   # o peso cabe em 16 bits


def baixar_tsv(pasta=PASTA_TSV):
    """Busca de novo os 5 arquivos (a..e.tsv) e a licença. Só roda com --baixar."""
    os.makedirs(pasta, exist_ok=True)
    for nome in ("a.tsv", "b.tsv", "c.tsv", "d.tsv", "e.tsv", "COPYING.txt"):
        with urllib.request.urlopen(URL_BASE + nome, timeout=60) as resposta:
            dados = resposta.read()
        with open(os.path.join(pasta, nome), "wb") as arquivo:
            arquivo.write(dados)
        print(f"baixado {nome} ({len(dados)} bytes)")


def ler_aberturas(pasta=PASTA_TSV):
    """Devolve [(eco, nome, [lances])]. Linha com PGN inválido é ignorada (e contada)."""
    aberturas, ignoradas = [], 0
    arquivos = sorted(glob.glob(os.path.join(pasta, "*.tsv")))
    if not arquivos:
        raise FileNotFoundError(f"nenhum .tsv em {pasta}. Use --baixar.")
    for caminho in arquivos:
        with open(caminho, encoding="utf-8", newline="") as f:
            for linha in csv.DictReader(f, delimiter="\t"):
                jogo = chess.pgn.read_game(io.StringIO(linha["pgn"]))
                if jogo is None or jogo.errors:
                    ignoradas += 1
                    continue
                aberturas.append((linha["eco"], linha["name"], list(jogo.mainline_moves())))
    if ignoradas:
        print(f"aviso: {ignoradas} linha(s) com PGN inválido ignoradas", file=sys.stderr)
    return aberturas


def codificar_lance(board, lance):
    """Lance -> inteiro de 16 bits do Polyglot (roque vira rei->torre, promoção em 3 bits)."""
    origem, destino = lance.from_square, lance.to_square
    if board.is_castling(lance):
        coluna_torre = 7 if board.is_kingside_castling(lance) else 0
        destino = chess.square(coluna_torre, chess.square_rank(origem))
    promocao = (lance.promotion - 1) if lance.promotion else 0   # cavalo=1, bispo=2, torre=3, dama=4
    return (chess.square_file(destino) | (chess.square_rank(destino) << 3)
            | (chess.square_file(origem) << 6) | (chess.square_rank(origem) << 9) | (promocao << 12))


def montar_entradas(aberturas):
    """Conta, para cada (posição, lance), em quantas aberturas ele aparece. -> {(chave, lance16): peso}"""
    pesos = collections.Counter()
    for _eco, _nome, lances in aberturas:
        board = chess.Board()
        for lance in lances[:PLY_MAXIMO_BOOK]:
            pesos[(chess.polyglot.zobrist_hash(board), codificar_lance(board, lance))] += 1
            board.push(lance)
    return {chave: min(peso, PESO_MAXIMO) for chave, peso in pesos.items()}


def escrever_book(entradas, caminho):
    """Grava o .bin: entradas ordenadas pela chave (exigência do Polyglot, que usa busca binária)."""
    pasta = os.path.dirname(caminho)
    if pasta:
        os.makedirs(pasta, exist_ok=True)
    ordenadas = sorted(entradas.items(), key=lambda item: (item[0][0], -item[1], item[0][1]))
    temporario = caminho + ".tmp"
    with open(temporario, "wb") as arquivo:
        for (chave, lance), peso in ordenadas:
            arquivo.write(struct.pack(">QHHI", chave, lance, peso, 0))
    os.replace(temporario, caminho)   # troca só no fim: nunca deixa um book pela metade
    return len(ordenadas)


def gerar(pasta_tsv=PASTA_TSV, saida=SAIDA_PADRAO):
    aberturas = ler_aberturas(pasta_tsv)
    entradas = montar_entradas(aberturas)
    total = escrever_book(entradas, saida)
    return len(aberturas), total


def main(argv=None):
    parser = argparse.ArgumentParser(description="Gera o book Polyglot a partir de chess-openings (CC0).")
    parser.add_argument("--saida", default=SAIDA_PADRAO, help="onde gravar o .bin")
    parser.add_argument("--tsv", default=PASTA_TSV, help="pasta com a.tsv ... e.tsv")
    parser.add_argument("--baixar", action="store_true", help="baixar os .tsv de novo (usa a internet)")
    args = parser.parse_args(argv)
    if args.baixar:
        baixar_tsv(args.tsv)
    aberturas, entradas = gerar(args.tsv, args.saida)
    print(f"{aberturas} aberturas -> {entradas} entradas em {args.saida} "
          f"({os.path.getsize(args.saida)} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
