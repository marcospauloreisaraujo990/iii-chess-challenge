"""Testes de ferramentas/baixar_tablebases.py (sem internet: o download é de mentira). Dono: Léo."""
import hashlib
import io
import os

import pytest

from ferramentas import baixar_tablebases as tb


def test_contagem_de_pecas_pelo_nome():
    assert tb.pecas_no_nome("KQvK.rtbw") == 3
    assert tb.pecas_no_nome("KQRvKR.rtbz") == 5          # limite permitido
    assert tb.pecas_no_nome("KQRRvKR.rtbw") == 6         # proibido


def test_lista_oficial_e_lida():
    texto = "aaaa  KQvK.rtbw\nBBBB  KQvK.rtbz\nlixo\n\ncccc  checksum.md5\n"
    assert tb.ler_md5_oficial(texto) == {"KQvK.rtbw": "aaaa", "KQvK.rtbz": "bbbb"}


def test_lista_com_arquivo_de_6_pecas_e_recusada():
    with pytest.raises(ValueError, match="6 peças|mais de 5 peças"):
        tb.ler_md5_oficial("aaaa  KQRRvKR.rtbw\n")


def test_lista_fixada_no_git_e_valida_e_so_tem_ate_5_pecas():
    esperado = tb.ler_md5_oficial(open(tb.LISTA_FIXADA, encoding="ascii").read())
    assert len(esperado) > 250
    assert all(tb.pecas_no_nome(n) <= 5 for n in esperado)
    assert all(len(m) == 32 for m in esperado.values())
    assert sum(n.endswith(".rtbw") for n in esperado) > 100 and sum(n.endswith(".rtbz") for n in esperado) > 100


class RespostaFalsa(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def _md5(dados):
    return hashlib.md5(dados).hexdigest()


def test_download_correto_e_gravado_e_conferido(tmp_path, monkeypatch):
    dados = b"conteudo da tablebase"
    chamadas = []
    monkeypatch.setattr(tb.urllib.request, "urlopen", lambda url, timeout=0: chamadas.append(url) or RespostaFalsa(dados))
    nome, status = tb.baixar_um("KQvK.rtbw", _md5(dados), str(tmp_path))
    assert (nome, status) == ("KQvK.rtbw", "ok")
    assert (tmp_path / "KQvK.rtbw").read_bytes() == dados
    assert not (tmp_path / "KQvK.rtbw.part").exists()
    assert chamadas == [tb.URL_ARQUIVOS[".rtbw"] + "KQvK.rtbw"]            # .rtbw vem da pasta wdl, por HTTPS
    assert chamadas[0].startswith("https://")


def test_rtbz_vem_da_pasta_dtz(tmp_path, monkeypatch):
    chamadas = []
    monkeypatch.setattr(tb.urllib.request, "urlopen", lambda url, timeout=0: chamadas.append(url) or RespostaFalsa(b"x"))
    tb.baixar_um("KQvK.rtbz", _md5(b"x"), str(tmp_path))
    assert "3-4-5-dtz" in chamadas[0]


def test_md5_diferente_descarta_o_arquivo(tmp_path, monkeypatch):
    monkeypatch.setattr(tb.urllib.request, "urlopen", lambda url, timeout=0: RespostaFalsa(b"arquivo adulterado"))
    nome, status = tb.baixar_um("KQvK.rtbw", _md5(b"original"), str(tmp_path))
    assert status.startswith("ERRO") and "MD5" in status
    assert os.listdir(tmp_path) == []          # nem o arquivo final nem o .part ficam


def test_falha_de_rede_nao_deixa_lixo_e_devolve_erro(tmp_path, monkeypatch):
    def cai(url, timeout=0):
        raise OSError("sem rede")
    monkeypatch.setattr(tb.urllib.request, "urlopen", cai)
    nome, status = tb.baixar_um("KQvK.rtbw", "0" * 32, str(tmp_path))
    assert status.startswith("ERRO: OSError")
    assert os.listdir(tmp_path) == []


def test_arquivo_ja_correto_e_pulado_sem_baixar(tmp_path, monkeypatch):
    dados = b"ja estava"
    (tmp_path / "KQvK.rtbw").write_bytes(dados)

    def nao_deve_baixar(url, timeout=0):
        raise AssertionError("baixou de novo um arquivo que já estava correto")
    monkeypatch.setattr(tb.urllib.request, "urlopen", nao_deve_baixar)
    assert tb.baixar_um("KQvK.rtbw", _md5(dados), str(tmp_path)) == ("KQvK.rtbw", "ja-estava")


def test_arquivo_corrompido_na_pasta_e_baixado_de_novo(tmp_path, monkeypatch):
    (tmp_path / "KQvK.rtbw").write_bytes(b"corrompido")
    bom = b"o certo"
    monkeypatch.setattr(tb.urllib.request, "urlopen", lambda url, timeout=0: RespostaFalsa(bom))
    assert tb.baixar_um("KQvK.rtbw", _md5(bom), str(tmp_path))[1] == "ok"
    assert (tmp_path / "KQvK.rtbw").read_bytes() == bom


def test_conferir_pasta_acha_faltando_corrompido_e_proibido(tmp_path):
    bom = b"bom"
    (tmp_path / "KQvK.rtbw").write_bytes(bom)
    (tmp_path / "KRvK.rtbw").write_bytes(b"ruim")
    (tmp_path / "KQRRvKR.rtbw").write_bytes(b"seis pecas")
    esperado = {"KQvK.rtbw": _md5(bom), "KRvK.rtbw": _md5(b"certo"), "KPvK.rtbw": _md5(b"x")}
    ok, faltando, corrompidos, proibidos = tb.conferir_pasta(str(tmp_path), esperado)
    assert (ok, faltando, corrompidos, proibidos) == (1, ["KPvK.rtbw"], ["KRvK.rtbw"], ["KQRRvKR.rtbw"])


def test_conferir_pasta_que_nao_existe(tmp_path):
    ok, faltando, corrompidos, proibidos = tb.conferir_pasta(str(tmp_path / "nao-existe"), {"KQvK.rtbw": "a" * 32})
    assert (ok, faltando, corrompidos, proibidos) == (0, ["KQvK.rtbw"], [], [])
