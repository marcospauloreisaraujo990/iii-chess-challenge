"""Testes de log.py. Dono: Junio."""
import log


def _ler(caminho):
    with open(caminho, encoding="utf-8") as f:
        return f.read().splitlines()


def test_linha_normal_tem_os_8_campos(tmp_path):
    caminho = tmp_path / "partida.txt"
    arq = log.abrir_log(str(caminho))
    log.registrar_lance(arq, 12, "brancas", "g1f3", 26, 41203118, 0.35, ["g1f3", "d7d5", "c2c4"], 14.2)
    linha = _ler(caminho)[0]
    assert linha == "12 | brancas | g1f3 | prof 26 | nós 41203118 | aval +0.35 | pv g1f3 d7d5 c2c4 | 14.2 s"
    arq.close()


def test_grava_no_disco_sem_fechar_o_arquivo(tmp_path):
    """O flush acontece a cada lance: outra leitura já enxerga a linha, mesmo com o arquivo aberto."""
    caminho = tmp_path / "partida.txt"
    arq = log.abrir_log(str(caminho))
    log.registrar_lance(arq, 1, "brancas", "e2e4", 20, 1000, 0.1, "e2e4", 1.0)
    assert len(_ler(caminho)) == 1
    log.registrar_lance(arq, 2, "pretas", "e7e5", 20, 1000, -0.1, "e7e5", 1.0)
    assert len(_ler(caminho)) == 2
    arq.close()


def test_lance_de_book_tem_profundidade_zero_e_a_palavra_book(tmp_path):
    caminho = tmp_path / "partida.txt"
    arq = log.abrir_log(str(caminho))
    log.registrar_lance(arq, 1, "brancas", "e2e4", 99, 0, 0.0, "", 0.0, book=True)
    linha = _ler(caminho)[0]
    assert "prof 0" in linha
    assert linha.endswith("| book")
    arq.close()


def test_avaliacao_de_mate_passa_como_texto(tmp_path):
    caminho = tmp_path / "partida.txt"
    arq = log.abrir_log(str(caminho))
    log.registrar_lance(arq, 40, "pretas", "d8h4", 30, 5, "#3", "d8h4", 2.0)
    assert "aval #3" in _ler(caminho)[0]
    arq.close()


def test_reabrir_nao_apaga_o_log_antigo(tmp_path):
    caminho = tmp_path / "partida.txt"
    arq = log.abrir_log(str(caminho))
    log.registrar_lance(arq, 1, "brancas", "e2e4", 20, 1, 0.1, "e2e4", 1.0)
    arq.close()
    arq = log.abrir_log(str(caminho))
    log.registrar_lance(arq, 2, "pretas", "e7e5", 20, 1, 0.1, "e7e5", 1.0)
    arq.close()
    assert len(_ler(caminho)) == 2


def test_erro_de_disco_nao_derruba_a_partida(tmp_path):
    caminho = tmp_path / "partida.txt"
    arq = log.abrir_log(str(caminho))
    arq.close()  # escrever num arquivo fechado dá erro
    ok = log.registrar_lance(arq, 1, "brancas", "e2e4", 20, 1, 0.1, "e2e4", 1.0)
    assert ok is False


def test_abrir_log_cria_a_pasta(tmp_path):
    caminho = tmp_path / "partidas" / "jogo1.txt"
    arq = log.abrir_log(str(caminho))
    arq.close()
    assert caminho.exists()


def test_pv_e_lance_como_chess_move(tmp_path):
    """O python-chess devolve a PV como lista de chess.Move: o log precisa aceitar."""
    import chess
    caminho = tmp_path / "partida.txt"
    arq = log.abrir_log(str(caminho))
    pv = [chess.Move.from_uci("g1f3"), chess.Move.from_uci("d7d5")]
    ok = log.registrar_lance(arq, 1, "brancas", pv[0], 20, 1, 0.1, pv, 1.0)
    assert ok is True
    assert "g1f3 | prof 20" in _ler(caminho)[0]
    assert "pv g1f3 d7d5" in _ler(caminho)[0]
    arq.close()


def test_dado_estranho_nao_derruba(tmp_path):
    caminho = tmp_path / "partida.txt"
    arq = log.abrir_log(str(caminho))
    assert log.registrar_lance(arq, 1, "brancas", "e2e4", 20, 1, 0.1, "e2e4", None) is False
    arq.close()


def test_abrir_log_sem_permissao_cai_para_emergencia(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    arq = log.abrir_log("/proc/nao-pode-criar/aqui.txt")
    assert arq is not None
    assert arq.name == log.LOG_EMERGENCIA
    arq.close()
