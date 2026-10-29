# Projeto Capablanca — III Chess Challenge (ICEV, 06/11/2026)

Equipe: Marcos Paulo, Junio e Léo. Programa único em Python que joga xadrez usando o
Stockfish local via UCI (biblioteca python-chess) e uma gestão de tempo escrita por nós
(o componente autoral que defendemos na arguição técnica).

## Prazos
- E-mail para a organização (relógio e modificação significativa): até 18/10/2026
- Congelar código: 02/11. A partir daí só correção de bug.
- Envio do Git para icev@somosicev.com: 04/11/2026 (sem envio ou sem validação = desclassificação)
- Ensaio geral: 05/11. Torneio: 06/11. Os três integrantes presentes o evento inteiro.

## Regras que o código DEVE respeitar
- Tudo roda local. Nenhuma rede nem API externa durante as partidas.
- Dependências declaradas em requirements.txt com versões fixas.
- Relógio ainda não confirmado: 15 min + 10 s por lance (FAQ) ou 25 min sem incremento
  (regulamento). O software tem perfis: "15+10", "25+0" e "armageddon" (brancas 5 min,
  pretas 4 min, empate classifica as pretas). Perfil escolhido no início da partida.
- Travou ou estourou o tempo = derrota. Robustez vale mais que recurso bonito.
- Book Polyglot (.bin) local, só até o meio-lance 10 (board.ply() < 10).
- Tablebases Syzygy só até 5 peças. Nunca 6 ou 7.
- Lances sempre em UCI (e2e4; roque e1g1; promoção e7e8q). O tabuleiro físico é a fonte da verdade.
- Log .txt por partida, uma linha por lance, com flush a cada lance:
  número | cor | lance UCI | profundidade | nós | avaliação | PV | tempo gasto.
  Lance de book entra com profundidade 0 e a palavra book.
- Interface só de linha de comando. Comandos de emergência: desfazer, tab, fen ..., t mm:ss.
- Stockfish é GPLv3: LICENSE GPLv3 na raiz; README declara projeto-base, versão/commit do
  Stockfish e origem do book e das tablebases.
- Modificação significativa = componente decisório com autoria própria, funcional nas partidas
  e defendido na arguição. Aqui é a gestão de tempo (tempo.py). Não conta: ajuste de
  parâmetros do Stockfish, reformatação, renomear variáveis.

## Divisão do grupo (dono de cada módulo)
- Marcos Paulo: tempo.py. Na mesa: anunciador (lê o lance, anuncia em UCI, move a peça, aciona o relógio).
- Junio: partida.py e log.py. Na mesa: operador (digita os lances, cuida do notebook).
- Léo: book.py, testes/, tablebases, README, requirements.txt e entrega. Na mesa: conferente
  (repete o lance adversário, confere tabuleiro x tela, informa o tempo restante).

## Caminho de um lance
recebe lance adversário (partida.py) -> procura no book (book.py) -> calcula o tempo do
lance (tempo.py) -> Stockfish pensa com tablebases -> a cada profundidade tempo.py decide
se para -> grava log e mostra o lance (log.py) -> anunciamos.

## Regras de trabalho para o Claude
1. AUTORIA: não escreva a lógica central de tempo.py. Nesse arquivo, explique, revise,
   aponte bugs e sugira testes; quem escreve é o Marcos Paulo. Nos outros módulos pode
   implementar, mas explique cada decisão em linguagem simples: os três precisam defender o código.
2. Use modo Plan antes de mudanças grandes. Commits pequenos, um assunto por commit.
3. Nunca adicione rede, API externa, tablebase de 6+ peças nem consulta ao book depois do ply 10.
4. Não invente valores de tempo: os números finais vêm dos testes do Léo (testes/torneio.py).
