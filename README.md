# Capablanca — III Chess Challenge (ICEV 2026)

Equipe: Marcos Paulo, Junio, Léo.

## Projeto-base declarado
- Motor: Stockfish 19 (local, via UCI). Release `sf_19` (05/09/2026), arquivo
  `stockfish-linux-x86-64-universal.tar.gz` do GitHub oficial (official-stockfish/Stockfish).
  SHA-256: `9defc0d4e55d49c65a6d042f3e571a39fcea499ade6dbe741b53b8c65e03611f`.
  Fica em `stockfish/`, fora do Git. O código-fonte vem junto no mesmo arquivo (pasta `src/`).
- Licença: GPLv3 (ver LICENSE). Código-fonte publicado neste repositório.

## O que é autoria nossa
- tempo.py: gestão de tempo escrita do zero (Marcos Paulo): alvo e máximo por lance,
  desconto do atraso humano, parada em tempo real, modo economia, perfis de relógio.
- partida.py e log.py: laço da partida, validação, comandos de emergência, ponderação, log (Junio).
- book.py e testes/: integração do book e simulador de partidas (Léo).

## O que NÃO é autoria nossa
- Stockfish (motor de busca e avaliação).
- Opening book Polyglot: origem PREENCHER (Léo).
- Tablebases Syzygy 3-5 peças: origem PREENCHER (Léo). Entregues em mídia física, fora do Git.

## Como instalar e rodar
1. Python 3, ambiente virtual e `pip install -r requirements.txt`.
2. Baixar o Stockfish compatível com o processador e apontar o caminho em partida.py.
3. Colocar book (.bin) e tablebases (até 5 peças) nas pastas indicadas.
4. Rodar: `python partida.py`.

## Testes
- `pytest` (testes unitários de tempo.py)
- `python testes/torneio.py` (partidas automáticas entre versões, relógio simulado)

## Resultados dos testes (para a arguição)
PREENCHER com a tabela: nossa gestão x tempo fixo por lance x gestão padrão do Stockfish.
