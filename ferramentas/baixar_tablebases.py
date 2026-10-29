"""Baixa as tablebases Syzygy de 3, 4 e 5 peças (cerca de 1 GB) para a pasta tablebases/.

Isto roda UMA vez, antes do torneio, com internet. Durante as partidas o programa não usa
rede nenhuma: o motor só lê os arquivos que já estão no disco.

De onde vem cada coisa:
  - Os arquivos (.rtbw = vitória/empate/derrota, .rtbz = distância até zerar o contador)
    vêm do servidor da Lichess, por HTTPS:
        https://tablebase.lichess.ovh/tables/standard/3-4-5-wdl/   (.rtbw, ~395 MB)
        https://tablebase.lichess.ovh/tables/standard/3-4-5-dtz/   (.rtbz, ~588 MB)
  - A lista oficial de arquivos e os MD5 vêm de uma fonte INDEPENDENTE (espelho do Sesse):
        http://tablebase.sesse.net/syzygy/3-4-5/checksum.md5
    Se o arquivo da Lichess tiver o MD5 diferente da lista, ele é descartado.
  - Essa lista está FIXADA no Git (ferramentas/dados/tablebases-3-4-5.md5), então a
    conferência não depende da rede. O espelho só atende por HTTP (sem criptografia), mas isso
    não abre brecha: os arquivos vêm da Lichess por HTTPS, e a lista só serve para detectar
    corrupção. Se alguém alterasse a lista no caminho, o resultado seria uma recusa, nunca
    um arquivo falso aceito. Para atualizar a lista fixada, use --atualizar-lista.

Regras do torneio que este script garante:
  - Só entram arquivos de até 5 peças. Qualquer nome com mais de 5 peças é recusado.
  - O download é seguro contra queda: grava em .part e só renomeia depois de conferir o MD5.
    Pode rodar de novo à vontade: arquivos já corretos são pulados.

Uso:
    python ferramentas/baixar_tablebases.py                 # baixa tudo em tablebases/
    python ferramentas/baixar_tablebases.py --pasta outra/  # outra pasta
    python ferramentas/baixar_tablebases.py --so-conferir   # só confere o que já está na pasta
"""
import argparse
import concurrent.futures
import hashlib
import os
import sys
import urllib.request

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PASTA_PADRAO = os.path.join(RAIZ, "tablebases")
URL_MD5 = "http://tablebase.sesse.net/syzygy/3-4-5/checksum.md5"
LISTA_FIXADA = os.path.join(RAIZ, "ferramentas", "dados", "tablebases-3-4-5.md5")
URL_ARQUIVOS = {
    ".rtbw": "https://tablebase.lichess.ovh/tables/standard/3-4-5-wdl/",
    ".rtbz": "https://tablebase.lichess.ovh/tables/standard/3-4-5-dtz/",
}
MAX_PECAS = 5   # regra do torneio: nunca 6 ou 7


def pecas_no_nome(nome):
    """'KQRvKR.rtbw' -> 5. Conta as letras das peças, sem o 'v' e a extensão."""
    return len(nome.split(".")[0].replace("v", ""))


def ler_md5_oficial(texto):
    """Texto do checksum.md5 ('<md5>  <nome>' por linha) -> {nome: md5}. Recusa nome com 6+ peças."""
    esperado = {}
    for linha in texto.splitlines():
        partes = linha.split()
        if len(partes) != 2:
            continue
        md5, nome = partes
        if not nome.endswith(tuple(URL_ARQUIVOS)):
            continue
        if pecas_no_nome(nome) > MAX_PECAS:
            raise ValueError(f"{nome} tem mais de {MAX_PECAS} peças: recusado (regra do torneio)")
        esperado[nome] = md5.lower()
    return esperado


def md5_do_arquivo(caminho):
    hasher = hashlib.md5()
    with open(caminho, "rb") as arquivo:
        for bloco in iter(lambda: arquivo.read(1 << 20), b""):
            hasher.update(bloco)
    return hasher.hexdigest()


def baixar_um(nome, md5_esperado, pasta):
    """Baixa um arquivo e confere o MD5. Devolve (nome, status): 'ok', 'ja-estava' ou 'ERRO: ...'."""
    destino = os.path.join(pasta, nome)
    if os.path.isfile(destino) and md5_do_arquivo(destino) == md5_esperado:
        return nome, "ja-estava"
    url = URL_ARQUIVOS[os.path.splitext(nome)[1]] + nome
    parcial = destino + ".part"
    try:
        with urllib.request.urlopen(url, timeout=120) as resposta, open(parcial, "wb") as arquivo:
            for bloco in iter(lambda: resposta.read(1 << 20), b""):
                arquivo.write(bloco)
        if md5_do_arquivo(parcial) != md5_esperado:
            os.remove(parcial)
            return nome, "ERRO: MD5 diferente do oficial (arquivo descartado)"
        os.replace(parcial, destino)
        return nome, "ok"
    except Exception as erro:
        if os.path.exists(parcial):
            os.remove(parcial)
        return nome, f"ERRO: {type(erro).__name__}: {erro}"


def conferir_pasta(pasta, esperado):
    """Confere o que já está na pasta. Devolve (ok, faltando, corrompidos, proibidos)."""
    ok, corrompidos, proibidos = 0, [], []
    presentes = [f for f in os.listdir(pasta) if f.endswith(tuple(URL_ARQUIVOS))] if os.path.isdir(pasta) else []
    for nome in presentes:
        if pecas_no_nome(nome) > MAX_PECAS:
            proibidos.append(nome)
        elif nome in esperado and md5_do_arquivo(os.path.join(pasta, nome)) == esperado[nome]:
            ok += 1
        else:
            corrompidos.append(nome)
    faltando = sorted(set(esperado) - set(presentes))
    return ok, faltando, corrompidos, proibidos


def main(argv=None):
    parser = argparse.ArgumentParser(description="Baixa e confere as tablebases Syzygy de 3-4-5 peças.")
    parser.add_argument("--pasta", default=PASTA_PADRAO)
    parser.add_argument("--so-conferir", action="store_true", help="não baixa, só confere o que já está na pasta")
    parser.add_argument("--paralelo", type=int, default=4, help="downloads ao mesmo tempo (padrão 4)")
    parser.add_argument("--atualizar-lista", action="store_true",
                        help="busca a lista de MD5 de novo (HTTP) e regrava a lista fixada no Git")
    args = parser.parse_args(argv)

    if args.atualizar_lista or not os.path.isfile(LISTA_FIXADA):
        with urllib.request.urlopen(URL_MD5, timeout=60) as resposta:
            texto = resposta.read().decode("ascii")
        ler_md5_oficial(texto)   # valida (e recusa 6+ peças) antes de gravar
        with open(LISTA_FIXADA, "w", encoding="ascii") as arquivo:
            arquivo.write(texto)
        print(f"lista de MD5 gravada em {LISTA_FIXADA}")
    with open(LISTA_FIXADA, encoding="ascii") as arquivo:
        esperado = ler_md5_oficial(arquivo.read())
    print(f"lista oficial: {len(esperado)} arquivos (3 a {MAX_PECAS} peças)")
    os.makedirs(args.pasta, exist_ok=True)

    if not args.so_conferir:
        falhas = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=max(1, args.paralelo)) as pool:
            futuros = [pool.submit(baixar_um, nome, md5, args.pasta) for nome, md5 in sorted(esperado.items())]
            for i, futuro in enumerate(concurrent.futures.as_completed(futuros), 1):
                nome, status = futuro.result()
                if status.startswith("ERRO"):
                    falhas.append((nome, status))
                    print(f"[{i}/{len(esperado)}] {nome}: {status}", file=sys.stderr)
                elif i % 20 == 0 or i == len(esperado):
                    print(f"[{i}/{len(esperado)}] ... último: {nome} ({status})")
        if falhas:
            print(f"\n{len(falhas)} arquivo(s) com erro. Rode de novo para tentar outra vez.", file=sys.stderr)

    ok, faltando, corrompidos, proibidos = conferir_pasta(args.pasta, esperado)
    print(f"\nconferência: {ok} arquivos corretos, {len(faltando)} faltando, "
          f"{len(corrompidos)} corrompidos, {len(proibidos)} proibidos (6+ peças)")
    for nome in faltando[:10]:
        print("  faltando:", nome)
    return 0 if not (faltando or corrompidos or proibidos) else 1


if __name__ == "__main__":
    raise SystemExit(main())
