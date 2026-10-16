"""Testes de partida.py (leitura de lances e comandos de emergência). Dono: Junio."""
import chess

import partida


def _ler(board, *digitado, ao_sincronizar=None):
    """Roda ler_lance com entradas falsas. Devolve (resultado, mensagens_na_tela)."""
    fila = iter(digitado)
    tela = []
    resultado = partida.ler_lance(board, ao_sincronizar=ao_sincronizar,
                                  entrada=lambda _: next(fila), saida=tela.append)
    return resultado, tela


def test_lance_uci_valido():
    lance, _ = _ler(chess.Board(), "e2e4")
    assert lance == chess.Move.from_uci("e2e4")


def test_maiusculas_e_espacos_sao_aceitos():
    lance, _ = _ler(chess.Board(), "  E2E4  ")
    assert lance == chess.Move.from_uci("e2e4")


def test_entrada_ruim_so_pede_de_novo():
    lance, tela = _ler(chess.Board(), "banana", "e2e5", "", "e2e4")
    assert lance == chess.Move.from_uci("e2e4")
    assert len(tela) == 2  # uma mensagem para "banana", outra para o lance ilegal


def test_roque_em_uci():
    board = chess.Board("r3k2r/8/8/8/8/8/8/R3K2R w KQkq - 0 1")
    lance, _ = _ler(board, "e1g1")
    assert lance == chess.Move.from_uci("e1g1")


def test_promocao_precisa_da_letra():
    board = chess.Board("8/4P2k/8/8/8/8/8/K7 w - - 0 1")
    lance, tela = _ler(board, "e7e8", "e7e8q")
    assert lance == chess.Move.from_uci("e7e8q")
    assert "promoção" in tela[0]


def test_tab_mostra_tabuleiro_e_continua_pedindo():
    lance, tela = _ler(chess.Board(), "tab", "e2e4")
    assert lance == chess.Move.from_uci("e2e4")
    assert any("FEN:" in linha for linha in tela)


def test_desfazer_volta_um_lance_e_devolve_none():
    board = chess.Board()
    board.push_uci("e2e4")
    resultado, _ = _ler(board, "desfazer")
    assert resultado is None
    assert board.fen() == chess.Board().fen()


def test_desfazer_sem_lances_nao_quebra():
    board = chess.Board()
    lance, tela = _ler(board, "desfazer", "d2d4")
    assert lance == chess.Move.from_uci("d2d4")
    assert "Nada para desfazer." in tela


def test_fen_valido_carrega_a_posicao():
    board = chess.Board()
    fen = "8/8/8/8/8/8/k7/4K2R w K - 0 1"
    resultado, _ = _ler(board, "fen " + fen)
    assert resultado is None
    assert board.board_fen() == chess.Board(fen).board_fen()


def test_fen_invalido_nao_altera_o_tabuleiro():
    board = chess.Board()
    antes = board.fen()
    lance, tela = _ler(board, "fen isso-nao-e-fen", "e2e4")
    assert board.fen() == antes
    assert any("FEN inválido" in linha for linha in tela)


def test_comando_t_nao_derruba_quando_tempo_nao_esta_pronto():
    """Enquanto tempo.sincronizar for esqueleto, a partida segue normalmente."""
    lance, tela = _ler(chess.Board(), "t 12:34", "e2e4")
    assert lance == chess.Move.from_uci("e2e4")
    assert len(tela) == 1


def test_comando_t_chama_tempo_sincronizar(monkeypatch):
    import tempo
    monkeypatch.setattr(tempo, "sincronizar", lambda texto: 754)
    recebido = []
    lance, _ = _ler(chess.Board(), "t 12:34", "e2e4", ao_sincronizar=recebido.append)
    assert recebido == [754]


def test_comando_t_com_erro_de_valor_nao_derruba(monkeypatch):
    import tempo

    def falha(texto):
        raise ValueError("formato")
    monkeypatch.setattr(tempo, "sincronizar", falha)
    lance, tela = _ler(chess.Board(), "t 99", "e2e4")
    assert lance == chess.Move.from_uci("e2e4")
    assert any("inválido" in linha for linha in tela)


# ---- casos de borda levantados pelos agentes (rodada de revisão) ----

def test_en_passant():
    board = chess.Board("rnbqkbnr/ppp1p1pp/8/3pPp2/8/8/PPPP1PPP/RNBQKBNR w KQkq f6 0 3")
    lance, _ = _ler(board, "e5f6")
    assert lance == chess.Move.from_uci("e5f6")


def test_en_passant_sem_direito_e_ilegal():
    board = chess.Board("rnbqkbnr/ppp1p1pp/8/3pPp2/8/8/PPPP1PPP/RNBQKBNR w KQkq - 0 3")
    lance, tela = _ler(board, "e5f6", "d2d4")
    assert lance == chess.Move.from_uci("d2d4")
    assert "ilegal" in tela[0]


def test_san_e_formatos_estranhos_sao_recusados():
    lance, tela = _ler(chess.Board(), "Nf3", "e2-e4", "e2e4;", "e2", "e2e4e5", "0000", "e2e4")
    assert lance == chess.Move.from_uci("e2e4")
    assert len(tela) == 6


def test_lance_com_texto_depois_e_recusado():
    lance, tela = _ler(chess.Board(), "e2e4 lixo", "e2e4")
    assert lance == chess.Move.from_uci("e2e4")
    assert "um lance por vez" in tela[0]


def test_peca_cravada_nao_pode_se_mover():
    board = chess.Board("4r1k1/8/8/8/8/8/4N3/4K3 w - - 0 1")
    lance, tela = _ler(board, "e2c3", "e1d1")
    assert lance == chess.Move.from_uci("e1d1")
    assert "ilegal" in tela[0]


def test_roque_ilegal_com_rei_em_xeque():
    board = chess.Board("4r1k1/8/8/8/8/8/8/R3K2R w KQ - 0 1")
    lance, tela = _ler(board, "e1g1", "e1d1")
    assert lance == chess.Move.from_uci("e1d1")


def test_promocao_invalida_e_recusada():
    board = chess.Board("8/4P2k/8/8/8/8/8/K7 w - - 0 1")
    lance, tela = _ler(board, "e7e8k", "e7e8q")
    assert lance == chess.Move.from_uci("e7e8q")


def test_comandos_sem_argumento_mostram_uso():
    lance, tela = _ler(chess.Board(), "fen", "t", "t 1 2", "e2e4")
    assert lance == chess.Move.from_uci("e2e4")
    assert all("Uso" in linha for linha in tela)


def test_comandos_em_maiusculas():
    board = chess.Board()
    board.push_uci("e2e4")
    resultado, _ = _ler(board, "DESFAZER")
    assert resultado is None


def test_fen_sem_reis_e_recusado_e_nao_altera():
    board = chess.Board()
    antes = board.fen()
    lance, tela = _ler(board, "fen 8/8/8/8/8/8/8/8 w - - 0 1", "e2e4")
    assert board.fen() == antes
    assert any("ilegal" in linha for linha in tela)


def test_fen_com_peao_na_primeira_fila_e_recusado():
    board = chess.Board()
    antes = board.fen()
    _ler(board, "fen 4k3/8/8/8/8/8/8/P3K3 w - - 0 1", "e2e4")
    assert board.fen() == antes


def test_desfazer_depois_de_fen_nao_tem_o_que_desfazer():
    board = chess.Board()
    board.push_uci("e2e4")
    fen = "8/8/8/8/8/8/k7/4K2R w K - 0 1"
    _, _ = _ler(board, "fen " + fen)
    lance, tela = _ler(board, "desfazer", "h1h2")
    assert "Nada para desfazer." in tela
    assert lance == chess.Move.from_uci("h1h2")


def test_no_xeque_mate_o_operador_ainda_consegue_desfazer():
    """Se digitaram o lance errado e deu mate, desfazer é a saída. Lance ilegal só avisa."""
    board = chess.Board()
    for lance in ("f2f3", "e7e5", "g2g4", "d8h4"):
        board.push_uci(lance)
    assert board.is_checkmate()
    resultado, tela = _ler(board, "e2e4", "desfazer")
    assert resultado is None
    assert "ilegal" in tela[0]
    assert not board.is_checkmate()


def test_eco_de_entrada_gigante_e_truncado():
    lance, tela = _ler(chess.Board(), "x" * 1_000_000, "e2e4")
    assert len(tela[0]) < 200


def test_ctrl_c_e_ignorado():
    chamadas = iter([KeyboardInterrupt, "e2e4"])
    tela = []

    def entrada(_):
        item = next(chamadas)
        if item is KeyboardInterrupt:
            raise KeyboardInterrupt
        return item
    lance = partida.ler_lance(chess.Board(), entrada=entrada, saida=tela.append)
    assert lance == chess.Move.from_uci("e2e4")
    assert "Ctrl+C" in tela[0]


def test_eof_sobe_para_o_main_tratar():
    import pytest

    def entrada(_):
        raise EOFError
    with pytest.raises(EOFError):
        partida.ler_lance(chess.Board(), entrada=entrada, saida=lambda _: None)


def test_comando_t_erro_inesperado_nao_derruba(monkeypatch):
    import tempo

    def quebra(texto):
        raise TypeError("bug no tempo.py")
    monkeypatch.setattr(tempo, "sincronizar", quebra)
    lance, tela = _ler(chess.Board(), "t 12:34", "e2e4")
    assert lance == chess.Move.from_uci("e2e4")
    assert "não foi alterado" in tela[0]


def test_comando_t_retorno_estranho_nunca_chega_ao_relogio(monkeypatch):
    import tempo
    recebido = []
    for ruim in (0, -5, None, True, "754", 12.5):
        monkeypatch.setattr(tempo, "sincronizar", lambda texto, r=ruim: r)
        _ler(chess.Board(), "t 12:34", "e2e4", ao_sincronizar=recebido.append)
    assert recebido == []


def test_comando_t_sem_relogio_ligado_avisa(monkeypatch):
    import tempo
    monkeypatch.setattr(tempo, "sincronizar", lambda texto: 754)
    lance, tela = _ler(chess.Board(), "t 12:34", "e2e4")
    assert "nada foi ajustado" in tela[0]


def test_comando_t_erro_no_relogio_nao_derruba(monkeypatch):
    import tempo
    monkeypatch.setattr(tempo, "sincronizar", lambda texto: 754)

    def quebra(segundos):
        raise RuntimeError("relógio quebrou")
    lance, tela = _ler(chess.Board(), "t 12:34", "e2e4", ao_sincronizar=quebra)
    assert lance == chess.Move.from_uci("e2e4")
    assert "não foi alterado" in tela[0]
