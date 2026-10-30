# Capablanca — III Chess Challenge (ICEV 2026)

Equipe: Marcos Paulo, Junio, Léo.

Programa de linha de comando para jogar o torneio: o **Stockfish** calcula os lances e o nosso
código cuida do resto (relógio, book, tablebases, log, comandos de emergência) e, principalmente,
da **gestão de tempo própria** (`tempo.py`), que é a nossa modificação significativa.

## Projeto-base declarado
- Motor: Stockfish 19 (local, via UCI). Release `sf_19` (05/09/2026), arquivo
  `stockfish-linux-x86-64-universal.tar.gz` do GitHub oficial (official-stockfish/Stockfish).
  SHA-256: `9defc0d4e55d49c65a6d042f3e571a39fcea499ade6dbe741b53b8c65e03611f`.
  Fica em `stockfish/`, fora do Git. O código-fonte vem junto no mesmo arquivo (pasta `src/`).
- Licença: GPLv3 (ver LICENSE). Código-fonte publicado neste repositório.
- Biblioteca: python-chess 1.11.2 (regras do jogo, leitura de book e tablebases). Não escolhe lances.

## Quem é responsável por quê (cada um defende o seu na arguição)
| Módulo | Responsável | O que faz |
|---|---|---|
| `tempo.py` | Marcos Paulo | **Modificação significativa.** Gestão de tempo escrita do zero: alvo e máximo por lance, desconto do atraso humano, parada em tempo real, atalho de tempo zero, modo economia, sincronização do relógio (`t mm:ss`), perfis de relógio. |
| `partida.py`, `log.py` | Junio | Laço da partida, leitura e validação dos lances em UCI, comandos de emergência, relógio interno, motor com reinício automático e vigia (watchdog), log e PGN. |
| `book.py`, `ferramentas/`, `testes/torneio.py` | Léo | Book de aberturas, gerador do book, download das tablebases, simulador de partidas. |

Parte do código de `partida.py`, `log.py`, `book.py`, das ferramentas e dos testes foi desenvolvida com
apoio do Claude Code (assistente de IA), sob revisão do responsável de cada módulo.

## O que NÃO é autoria nossa (terceiros)
- **Stockfish 19**: motor de busca e avaliação (GPLv3).
- **python-chess 1.11.2**: regras, leitura de book e tablebases (GPLv3).
- **Opening book** `book/book.bin`: **gerado por nós** com `ferramentas/gerar_book.py` a partir das
  aberturas do repositório [lichess-org/chess-openings](https://github.com/lichess-org/chess-openings)
  (licença **CC0**, domínio público; estado do `master` em 29/10/2026, commit `712a58be746c`).
  Os arquivos `a.tsv` ... `e.tsv` e o texto da licença estão em `ferramentas/dados/chess-openings/`.
  Como funciona: cada abertura é percorrida até o meio-lance 10 e cada lance recebe um peso igual a
  quantas aberturas o usam. O book é reproduzível (um teste confere que o arquivo do Git é idêntico
  ao que o gerador produz hoje).
- **Tablebases Syzygy de 3, 4 e 5 peças** (nunca 6 ou 7): tabelas de Ronde Veldhuizen, baixadas do
  servidor da Lichess (`tablebase.lichess.ovh/tables/standard/3-4-5-wdl` e `3-4-5-dtz`, ~1 GB) com
  `ferramentas/baixar_tablebases.py`. A integridade é conferida por MD5 contra a lista oficial do
  espelho do Sesse (`tablebase.sesse.net/syzygy/3-4-5/checksum.md5`), fixada no Git em
  `ferramentas/dados/tablebases-3-4-5.md5`. Ficam em `tablebases/`, **fora do Git** (entregues em
  mídia física).

## Como instalar (com internet, uma vez, antes do torneio)
1. Python 3.11 ou mais novo, ambiente virtual e dependências:
   ```
   python -m venv .venv
   source .venv/bin/activate        # Windows: .venv\Scripts\activate
   pip install -r requirements.txt
   ```
2. **Stockfish**: baixe o build certo para o sistema na página de releases oficial
   (github.com/official-stockfish/Stockfish/releases) e coloque o executável em `stockfish/`.
   O programa o encontra sozinho (primeiro arquivo `stockfish-*` executável). Para Linux, o build
   `x86-64-universal` usado aqui funciona em qualquer processador x86-64. No Windows, use o `.exe` do
   mesmo release.
3. **Book**: já está no Git (`book/book.bin`). Para regerar: `python ferramentas/gerar_book.py`.
4. **Tablebases** (3 a 5 peças): `python ferramentas/baixar_tablebases.py` (~1 GB). Rodar de novo só
   baixa o que faltar. Para só conferir: `--so-conferir`.
5. **Verificar o PC do torneio** (obrigatório, na máquina que vai para a mesa):
   ```
   python ferramentas/verificar_maquina.py
   ```
   Confere Python, python-chess, Stockfish, book e tablebases, **mede quantas threads deixam o Stockfish
   mais rápido nessa máquina** e imprime os comandos prontos para o dia. Use o número que ele medir:
   num notebook de teste, 6 threads foram mais rápidas que 11 (o processador reduz a velocidade quando
   todas trabalham), então o padrão automático nem sempre é o melhor.

Depois disso, **o programa não usa internet**: roda inteiro no computador, com Wi-Fi e cabo de rede desligados.

### No Windows
1. Instale o Python 3.11+ (python.org), marcando **"Add python.exe to PATH"**.
2. No terminal (PowerShell), na pasta do projeto:
   ```
   python -m venv .venv
   .venv\Scripts\activate
   pip install -r requirements.txt
   ```
   Se o PowerShell disser que scripts estão desabilitados, rode uma vez
   `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`.
3. Baixe o **`stockfish-windows-x86-64-universal.zip`** do release `sf_19` (o mesmo release do Linux; o build
   universal escolhe sozinho as instruções do processador), confira o SHA-256
   `3c8bf1f9ea66a09350a40df4f632288285ac206d99f33ab5842c408fc30b48a7`
   (PowerShell: `Get-FileHash .\stockfish-windows-x86-64-universal.zip`), descompacte e coloque o `.exe`
   dentro de `stockfish/`.
4. `python ferramentas/baixar_tablebases.py` e depois `python ferramentas/verificar_maquina.py`.
5. Para o dia, defina os valores medidos e rode:
   ```
   $env:CAPABLANCA_THREADS=15; $env:CAPABLANCA_HASH_MB=2048; $env:CAPABLANCA_ATRASO_HUMANO_S=12
   python partida.py
   ```
   (troque 15 e 2048 pelo que o verificador recomendar).

## Como rodar uma partida
```
python partida.py
```
O programa pergunta a **cor** (brancas/pretas), o **perfil de relógio** (`15+10`, `25+0` ou
`armageddon`; no armageddon as brancas têm 5 min, as pretas 4 min e o empate classifica as pretas) e o
**atraso humano** por lance (segundos que a equipe gasta anunciando, movendo a peça e apertando o
relógio; sai da medição na mesa). Depois joga: na nossa vez mostra, em destaque, `>>> JOGUE: e2e4`;
na vez do adversário o operador digita o lance dele em **UCI** (`e2e4`, roque `e1g1`, promoção `e7e8q`).

### Comandos de emergência (digitados no lugar de um lance)
| Comando | O que faz |
|---|---|
| `desfazer` | Desfaz o último meio-lance (corrige lance digitado errado). Na nossa vez o motor **não** pensa sozinho depois disso: espere acertar a posição e digite `go`. |
| `go` | Libera o motor para pensar (depois de `desfazer` ou `fen` na nossa vez). |
| `tab` | Mostra o tabuleiro do programa, o FEN e de quem é a vez (para conferir com o tabuleiro físico, que é a fonte da verdade). |
| `fen <posição>` | Recarrega a posição a partir de um FEN (inclua o número do lance real no último campo). Depois disso o book fica desligado. |
| `t mm:ss` | Acerta o relógio interno com o relógio físico (ex.: `t 12:34`). Se o valor for maior que o possível no perfil, pede confirmação. |

### Se algo der errado
- Motor travou ou caiu: o programa o reinicia sozinho. Se não voltar, passa para o **modo manual**
  (o operador digita também o nosso lance).
- Ctrl+C não fecha a partida. Teclado fechado: salva log e PGN e sai.
- Fim de partida por engano de digitação (ex.: mate que não existe): no aviso final digite `desfazer`.

### Força do motor: threads, hash e ponder
- **Threads e hash:** sem configuração, o programa usa todas as threads da CPU menos 1 e 1/8 da RAM
  (até 4 GB). No PC do torneio (Ryzen 7 5800X, 16 threads, 16 GB) isso dá 15 threads e 2048 MB. Valores
  definidos por variável são limitados ao que a máquina tem (threads) e a 3/4 da RAM (hash). A largada mostra:
  `Motor: 15 threads, 2048 MB de hash (...); ponder ligado.`
- **Ponder (pensar no tempo do adversário):** enquanto o adversário pensa e o operador digita, o Stockfish
  analisa a posição em segundo plano; quando o lance chega, o cálculo já está adiantado. Medido em 12
  posições: no caso típico, um terço a menos de trabalho para a mesma profundidade (8 de 12 melhoraram).
  Não mexe no relógio. Se o motor não parar em 1 s, ele é reiniciado. Desliga com `CAPABLANCA_PONDER=0`.
- **Velocidade dos lances:** quem decide quanto tempo cada lance leva é o `tempo.py` (alvo e máximo). Mais
  threads e o ponder deixam o lance mais preciso no mesmo tempo; para responder mais rápido, o alvo do
  `tempo.py` precisa ser recalibrado com o simulador.

### Variáveis de ambiente (opcionais)
- `CAPABLANCA_THREADS`, `CAPABLANCA_HASH_MB`: threads e hash do Stockfish (use o que o verificador medir).
- `CAPABLANCA_PONDER=0`: desliga o ponder.
- `CAPABLANCA_ATRASO_HUMANO_S`: atraso humano, para não precisar digitar toda vez. No ensaio de 29/10 a
  parte humana (falar + digitar) ficou em torno de **12 s por lance**; confirmar no ensaio com tabuleiro.
- `CAPABLANCA_FOLGA_WATCHDOG_S`: folga do vigia do motor (ver abaixo). Sem ela o vigia fica desligado e o
  programa avisa na largada.
- `CAPABLANCA_TEMPO_PROVISORIO_S`: **só para testes**, usado quando o `tempo.py` não existe. Não vale no torneio.

### Onde ficam os arquivos de cada partida
Pasta `partidas/` (fora do Git): `AAAA-MM-DD_HH-MM-SS.txt` (log, uma linha por lance nosso com os 8 campos:
número, cor, lance UCI, profundidade, nós, avaliação, PV, tempo gasto; lance de book entra com profundidade 0 e
a palavra `book`) e `.pgn` (a partida inteira, salvo a cada lance).

## Assistir o bot jogando (visualizador no navegador)
```
python ferramentas/assistir.py
```
Abre `http://127.0.0.1:8765` no navegador. Tem duas abas:

**Jogar contra o bot** (padrão): você joga clicando nas peças (clique na peça e depois na casa; na promoção
aparece a escolha da peça), com **relógio de verdade** correndo como nos sites (3+2, 5+3, 10+5, 15+10 do
torneio ou 25+0). O nosso bot joga com o programa de verdade (book, `tempo.py`, ponder no seu tempo), então
responde rápido no relógio curto e pensa mais no relógio longo. Do seu lado também pode jogar **o bot de
outra máquina**: ele fala o lance e você mexe na tela. O atraso humano do bot vem em 0 s (na tela não há
mesa); dá para simular a mesa com 6 ou 12 s.

**Bot contra bot**: escolha o adversário (Stockfish com a gestão de tempo dele,
bot fraco simulando um bot de aluno, ou tempo fixo), o relógio (rápido 3+2, que é o 15+10 em escala 0,2,
ou o 15+10 real) e de que cor o nosso bot joga, e clique em **Nova partida**. A tela mostra o tabuleiro, os
dois relógios correndo, a barra de avaliação, **o que o nosso bot está pensando** (profundidade, posições,
avaliação e a linha principal), a lista de lances e o gráfico da avaliação.

- É uma ferramenta de **teste e apresentação** (boa para a arguição). Nas partidas oficiais o programa da
  mesa é o `partida.py`, no terminal.
- Roda **sem internet**: o servidor só escuta no próprio computador (127.0.0.1) e a página não carrega nada
  de fora. Pedidos vindos de outro endereço são recusados.
- A partida é jogada pelo mesmo simulador dos confrontos: o nosso lado é o programa de verdade (com o
  `tempo.py`), com atraso humano simulado de 12 s por lance (`--atraso-s` muda).

## Regras do torneio e onde o código as garante
| Regra | Onde |
|---|---|
| Tudo local, sem rede nem API durante as partidas | `partida.py`, `book.py` (só leem arquivos). Internet só nas ferramentas de preparação. |
| Book só até o meio-lance 10 | `book.py` (duas travas: `ply < 10` e partida iniciada da posição inicial) e `partida.py` |
| Tablebases só até 5 peças | `SyzygyProbeLimit=5` enviado ao motor em `partida.py`; `baixar_tablebases.py` recusa 6+ peças |
| Lances sempre em UCI | `partida.py` |
| Log com 8 campos e `flush` a cada lance | `log.py` |
| Travou ou estourou o tempo = derrota | limite duro `Limit(time=...)` no motor, vigia, reinício e modo manual |
| Dependências com versão fixa | `requirements.txt` |

## Testes
```
pytest -q                                   # todos os testes
python testes/torneio.py confronto --help   # simulador de partidas
python testes/torneio.py estouro            # mede o estouro do motor (dado para a folga do vigia)
python ferramentas/verificar_maquina.py     # confere o PC e mede as threads
```
O simulador joga partidas automáticas com **relógio simulado e atraso artificial**, com três versões do mesmo
Stockfish: `nossa` (o programa de verdade, com `tempo.py`), `fixa` (tempo fixo por lance) e `padrao` (a gestão
de tempo do próprio Stockfish). Alterna as cores e usa aberturas variadas. Mede vitórias, empates, derrotas,
**derrotas por tempo** e o tempo que sobrou. O `--atraso-s` é obrigatório: não existe valor padrão.

## Resultados dos testes (para a arguição)
<!--RESULTADOS-->

## Prazos
Congelar o código: 02/11. Envio do Git para icev@somosicev.com: 04/11/2026. Ensaio geral: 05/11. Torneio: 06/11.
