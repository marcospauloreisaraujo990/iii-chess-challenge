"""Testes de book.py e do gerador do book (ferramentas/gerar_book.py). Dono: Léo."""
import collections
import os
import random

import chess
import chess.polyglot
import pytest

import book
from ferramentas import gerar_book

BOOK = gerar_book.SAIDA_PADRAO
precisa_book = pytest.mark.skipif(not os.path.isfile(BOOK), reason="book/book.bin não existe")

RUY_LOPEZ_8_PLIES = "e2e4 e7e5 g1f3 b8c6 f1b5 a7a6 b5a4 g8f6".split()


def _tabuleiro(lances):
    board = chess.Board()
    for lance in lances:
        board.push_uci(lance)
    return board


# ---------------- lance_do_book ----------------

@precisa_book
def test_posicao_inicial_devolve_so_lances_principais_e_legais():
    sorteados = {book.lance_do_book(chess.Board(), BOOK, random.Random(semente)).uci() for semente in range(300)}
    assert sorteados <= {"e2e4", "d2d4", "c2c4", "g1f3"}
    assert {"e2e4", "d2d4"} <= sorteados   # os dois mais comuns aparecem


@precisa_book
def test_lances_mais_comuns_saem_mais_vezes():
    sorteio = random.Random(7)
    contagem = collections.Counter(book.lance_do_book(chess.Board(), BOOK, sorteio).uci() for _ in range(2000))
    assert contagem["e2e4"] > contagem["d2d4"] > contagem["c2c4"]


@precisa_book
def test_mesma_semente_da_o_mesmo_lance():
    assert book.lance_do_book(chess.Board(), BOOK, random.Random(3)) == book.lance_do_book(chess.Board(), BOOK, random.Random(3))


@precisa_book
def test_todo_lance_devolvido_e_legal_em_varias_posicoes():
    for lances in ([], ["e2e4"], ["e2e4", "e7e5"], ["d2d4", "d7d5", "c2c4"], RUY_LOPEZ_8_PLIES):
        board = _tabuleiro(lances)
        for semente in range(30):
            lance = book.lance_do_book(board, BOOK, random.Random(semente))
            assert lance is None or lance in board.legal_moves


@precisa_book
def test_roque_do_book_vem_como_lance_normal_de_xadrez():
    """O Polyglot guarda o roque como rei->torre (e1h1); o programa recebe e1g1 (UCI normal)."""
    board = _tabuleiro(RUY_LOPEZ_8_PLIES)
    sorteados = {book.lance_do_book(board, BOOK, random.Random(s)) for s in range(200)}
    assert chess.Move.from_uci("e1g1") in sorteados
    assert chess.Move.from_uci("e1h1") not in sorteados


@precisa_book
def test_no_ply_9_ainda_usa_o_book():
    board = _tabuleiro(RUY_LOPEZ_8_PLIES + ["e1g1"])
    assert board.ply() == 9
    lance = book.lance_do_book(board, BOOK, random.Random(1))
    assert lance in board.legal_moves


@precisa_book
def test_no_ply_10_e_depois_nunca_consulta_o_book():
    board = _tabuleiro(RUY_LOPEZ_8_PLIES + ["e1g1", "f8e7"])
    assert board.ply() == 10
    assert book.lance_do_book(board, BOOK) is None


@precisa_book
def test_nenhuma_abertura_do_arquivo_devolve_lance_no_ply_10():
    """Varre as aberturas reais: em qualquer linha, no ply 10 o book fica calado."""
    for _eco, _nome, lances in gerar_book.ler_aberturas():
        if len(lances) >= 10:
            board = chess.Board()
            for lance in lances[:10]:
                board.push(lance)
            assert book.lance_do_book(board, BOOK) is None


@precisa_book
def test_depois_do_comando_fen_o_book_fica_desligado():
    """`fen` zera o contador de lances (ply 0), mas a partida não é do início: sem book."""
    board = chess.Board("rnbqkbnr/pppp1ppp/8/4p3/4P3/8/PPPP1PPP/RNBQKBNR w KQkq - 0 1")
    assert board.ply() == 0
    assert book.lance_do_book(board, BOOK) is None


@precisa_book
def test_fen_da_posicao_inicial_continua_com_book():
    board = chess.Board()
    board.set_fen(chess.STARTING_FEN)
    assert book.lance_do_book(board, BOOK, random.Random(1)) is not None


@precisa_book
def test_posicao_fora_do_book_devolve_none():
    board = _tabuleiro(["a2a3", "a7a6", "h2h3", "h7h6"])
    assert book.lance_do_book(board, BOOK) is None


def test_arquivo_inexistente_devolve_none(tmp_path):
    assert book.lance_do_book(chess.Board(), str(tmp_path / "nao-existe.bin")) is None


@pytest.mark.parametrize("conteudo", [b"", b"x" * 5, os.urandom(100), b"\x00" * 16, b"\xff" * 64])
def test_arquivo_vazio_ou_corrompido_devolve_none(tmp_path, conteudo):
    caminho = tmp_path / "ruim.bin"
    caminho.write_bytes(conteudo)
    assert book.lance_do_book(chess.Board(), str(caminho)) is None


def test_pasta_no_lugar_do_arquivo_devolve_none(tmp_path):
    assert book.lance_do_book(chess.Board(), str(tmp_path)) is None


def test_lance_ilegal_dentro_do_book_e_ignorado(tmp_path):
    """Entrada de uma posição que casa por hash mas com lance impossível: nunca devolve."""
    board = chess.Board()
    chave = chess.polyglot.zobrist_hash(board)
    entradas = {(chave, gerar_book.codificar_lance(chess.Board(), chess.Move.from_uci("e2e4"))): 10}
    # lance 'e2e5' (impossível) com peso enorme
    impossivel = chess.Move.from_uci("e2e5")
    entradas[(chave, (impossivel.to_square & 7) | ((impossivel.to_square >> 3) << 3)
              | ((impossivel.from_square & 7) << 6) | ((impossivel.from_square >> 3) << 9))] = 9999
    caminho = tmp_path / "x.bin"
    gerar_book.escrever_book(entradas, str(caminho))
    for semente in range(50):
        assert book.lance_do_book(board, str(caminho), random.Random(semente)) == chess.Move.from_uci("e2e4")


def test_lance_raro_abaixo_da_fracao_minima_nao_e_sorteado(tmp_path):
    board = chess.Board()
    chave = chess.polyglot.zobrist_hash(board)
    e4 = gerar_book.codificar_lance(board, chess.Move.from_uci("e2e4"))
    a4 = gerar_book.codificar_lance(board, chess.Move.from_uci("a2a4"))
    caminho = tmp_path / "x.bin"
    gerar_book.escrever_book({(chave, e4): 1000, (chave, a4): 5}, str(caminho))   # 0,5% do peso: abaixo de 2%
    assert {book.lance_do_book(board, str(caminho), random.Random(s)).uci() for s in range(200)} == {"e2e4"}


# ---------------- gerador ----------------

def test_codificacao_do_roque_e_rei_para_torre():
    board = chess.Board("r3k2r/8/8/8/8/8/8/R3K2R w KQkq - 0 1")
    # e1g1 -> destino h1 (coluna 7, linha 0), origem e1 (coluna 4, linha 0)
    assert gerar_book.codificar_lance(board, chess.Move.from_uci("e1g1")) == (7 | 0 << 3 | 4 << 6 | 0 << 9)
    assert gerar_book.codificar_lance(board, chess.Move.from_uci("e1c1")) == (0 | 0 << 3 | 4 << 6 | 0 << 9)
    pretas = chess.Board("r3k2r/8/8/8/8/8/8/R3K2R b KQkq - 0 1")
    assert gerar_book.codificar_lance(pretas, chess.Move.from_uci("e8g8")) == (7 | 7 << 3 | 4 << 6 | 7 << 9)
    assert gerar_book.codificar_lance(pretas, chess.Move.from_uci("e8c8")) == (0 | 7 << 3 | 4 << 6 | 7 << 9)


def test_codificacao_de_promocao_roundtrip_pelo_leitor(tmp_path):
    board = chess.Board("8/4P2k/8/8/8/8/8/K7 w - - 0 1")
    chave = chess.polyglot.zobrist_hash(board)
    lances = [chess.Move.from_uci(m) for m in ("e7e8q", "e7e8r", "e7e8b", "e7e8n")]
    caminho = tmp_path / "promo.bin"
    gerar_book.escrever_book({(chave, gerar_book.codificar_lance(board, m)): 1 + i for i, m in enumerate(lances)}, str(caminho))
    with chess.polyglot.open_reader(str(caminho)) as leitor:
        lidos = {e.move for e in leitor.find_all(board)}
    assert lidos == set(lances)


def test_arquivo_gerado_esta_ordenado_pela_chave(tmp_path):
    caminho = tmp_path / "x.bin"
    gerar_book.gerar(saida=str(caminho))
    dados = caminho.read_bytes()
    assert len(dados) % 16 == 0
    chaves = [int.from_bytes(dados[i:i + 8], "big") for i in range(0, len(dados), 16)]
    assert chaves == sorted(chaves)


def test_gerador_e_deterministico(tmp_path):
    a, b = tmp_path / "a.bin", tmp_path / "b.bin"
    gerar_book.gerar(saida=str(a))
    gerar_book.gerar(saida=str(b))
    assert a.read_bytes() == b.read_bytes()


@precisa_book
def test_book_do_git_e_exatamente_o_que_o_gerador_produz(tmp_path):
    """Garante que book/book.bin é reproduzível a partir dos dados CC0 que estão no repositório."""
    novo = tmp_path / "novo.bin"
    gerar_book.gerar(saida=str(novo))
    assert novo.read_bytes() == open(BOOK, "rb").read()


def test_pesos_contam_em_quantas_aberturas_cada_lance_aparece(tmp_path):
    pasta = tmp_path / "tsv"
    pasta.mkdir()
    (pasta / "a.tsv").write_text(
        "eco\tname\tpgn\n"
        "A00\tUma\t1. e4\n"
        "A00\tDuas\t1. e4 e5\n"
        "A00\tTres\t1. d4\n", encoding="utf-8")
    saida = tmp_path / "x.bin"
    gerar_book.gerar(str(pasta), str(saida))
    with chess.polyglot.open_reader(str(saida)) as leitor:
        pesos = {e.move.uci(): e.weight for e in leitor.find_all(chess.Board())}
    assert pesos == {"e2e4": 2, "d2d4": 1}


def test_linha_com_pgn_invalido_e_ignorada(tmp_path, capsys):
    pasta = tmp_path / "tsv"
    pasta.mkdir()
    (pasta / "a.tsv").write_text("eco\tname\tpgn\nA00\tBoa\t1. e4\nA00\tRuim\t1. e4 e4\n", encoding="utf-8")
    aberturas = gerar_book.ler_aberturas(str(pasta))
    assert len(aberturas) == 1 and aberturas[0][1] == "Boa"
    assert "ignoradas" in capsys.readouterr().err


def test_sem_arquivos_tsv_da_erro_claro(tmp_path):
    with pytest.raises(FileNotFoundError, match="--baixar"):
        gerar_book.ler_aberturas(str(tmp_path))


def test_gerador_so_grava_lances_ate_o_ply_9():
    """Posição de ply 10 em diante não recebe entrada nova de uma linha longa."""
    linha = [chess.Move.from_uci(m) for m in
             "e2e4 e7e5 g1f3 b8c6 f1b5 a7a6 b5a4 g8f6 e1g1 f8e7 f1e1 b7b5".split()]
    entradas = gerar_book.montar_entradas([("C00", "longa", linha)])
    assert len(entradas) == 10     # só os 10 primeiros meios-lances
