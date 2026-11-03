# Guia para a arguição técnica

Para cada integrante: o que o seu código faz, **por que** foi feito assim, e as perguntas mais
prováveis. Leia o seu módulo no código com este guia ao lado.

> Ideia central do projeto: o **Stockfish** escolhe o lance; o **nosso código** decide
> *quanto tempo* ele pode pensar e *quando parar*, e cuida de tudo que pode fazer perder a
> partida (travar, estourar o relógio, digitar errado). Quem escolhe o lance é o Stockfish;
> quem evita a derrota por tempo e por falha somos nós.

---

## Marcos Paulo — `tempo.py` (modificação significativa)

**O que faz, em linguagem simples**
- `calcular_tempo`: divide o relógio que sobra pelos lances que ainda devem faltar, soma o
  incremento, desconta o tempo que a equipe perde na mesa e uma reserva de segurança. Devolve
  `(alvo, máximo)`. O **alvo** é quanto queremos pensar; o **máximo** é o limite duro que vai para o motor.
- `deve_parar`: chamado a cada profundidade que o Stockfish termina. Chegou ao máximo: para
  sempre. Antes do alvo: continua. Passou do alvo mas o melhor lance mudou ou a avaliação caiu:
  continua até o máximo. Lance firme em várias profundidades: para.
- `atalho_tempo_zero`: lance único (ou de book) sai na hora, sem pensar.
- `modo_economia`: final calmo (avaliação perto de zero por 10 lances e pouco material) pensa
  pela metade, para guardar relógio.
- `sincronizar`: entende `t 12:34` e devolve segundos, para acertar o relógio interno com o físico.

**Perguntas prováveis**
- *Por que o atraso humano aparece duas vezes na conta?* A primeira vez garante que, neste lance,
  sobra tempo para anunciar e apertar o relógio. A segunda é o custo de cada lance futuro: o
  incremento só vira tempo de pensar depois de pagar o tempo da mesa.
- *Por que sem incremento o mínimo de lances restantes é 40?* Nas simulações do Marcos, com 20 o
  25+0 estourava perto do lance 80; com 40 passa do lance 120.
- *O que impede o programa de perder por tempo?* Três barreiras: o máximo sempre fica abaixo do
  relógio menos atraso menos reserva; o máximo vai ao motor como `Limit(time=...)`; e o vigia
  fecha o motor se ele não responder (ver Junio).
- *O que é a modificação significativa?* Um componente de decisão com autoria própria, que
  funciona nas partidas. Ajustar parâmetros do Stockfish não conta; decidir o tempo, sim.
- *Como vocês sabem que funciona?* O simulador (`testes/torneio.py`) joga partidas com relógio
  simulado e compara com tempo fixo e com a gestão do próprio Stockfish. Ver a tabela do README.

**Pontos para o Marcos decidir antes do torneio**
- No armageddon as brancas precisam vencer. Cortar o tempo pela metade com a posição empatada
  (modo economia) é a pior hora para elas. Vale desligar a economia para as brancas nesse perfil?
- A economia poupa quanto tempo de verdade? O `deve_parar` continua até o máximo se o lance
  mudar. Conferir com o simulador (`--ajuste FATOR_ECONOMIA=1`) antes de defender.

---

## Junio — `partida.py` e `log.py`

**O que faz**
- `ler_lance`: lê o lance do adversário, confere em UCI contra os lances legais; entrada ruim só
  pede de novo. Comandos: `desfazer`, `tab`, `fen`, `t mm:ss`, `go`.
- `escolher_lance`: book → atalho → tempo → Stockfish. O máximo vai ao motor como limite duro; a
  cada profundidade nova pergunta ao `tempo.deve_parar`. Se o `tempo.py` falhar ou devolver lixo,
  joga o lance mais rápido possível (`Limit(depth=1)`) em vez de inventar um tempo.
- `jogar_partida`/`main`: o laço da partida, o relógio interno, log e PGN a cada lance, reinício
  do motor, modo manual.
- `log.py`: uma linha por lance nosso, com os 8 campos, gravada no disco na hora (`flush` e `fsync`).

**Perguntas prováveis**
- *Por que depois do `desfazer` o motor não pensa sozinho?* Se o operador digitou errado o lance do
  adversário, o motor já jogou em cima da posição errada. Ao desfazer, esperamos a posição ser
  corrigida e o operador digitar `go`; assim nenhum tempo é gasto pensando na posição errada.
- *O que acontece se o Stockfish travar?* Um vigia opcional fecha o processo à força depois de
  `máximo + folga`; o programa reinicia o motor; se não voltar, entra no modo manual.
- *Por que o relógio usa o tempo real e não só o que o motor diz?* O tempo do operador digitando e
  das tentativas que falharam também corre no relógio. Descontar só o do motor acumula erro.
- *Como o `t mm:ss` evita erro de digitação?* Se o valor for maior que o máximo possível do perfil,
  pergunta "confirma?" e recusa por padrão.
- *O que é o `SyzygyProbeLimit=5`?* Uma opção do motor que o proíbe de usar tablebase com mais de 5
  peças, mesmo que o arquivo estivesse na pasta.

**Pendência de decisão do grupo:** a folga do vigia (`CAPABLANCA_FOLGA_WATCHDOG_S`). Medição:
o pior estouro do motor foi 8 ms e reiniciar o Stockfish leva cerca de 0,4 s. A folga precisa ser
bem maior que 8 ms (senão o vigia mataria um motor saudável) e menor que o tempo que podemos perder.

---

## Léo — `book.py`, `ferramentas/` e `testes/torneio.py`

**O que faz**
- `book.py`: devolve um lance do book só se `board.ply() < 10` **e** a partida começou da posição
  inicial; sorteia pelo peso; arquivo ausente ou corrompido devolve `None` e o programa joga normal.
- `ferramentas/gerar_book.py`: gera `book/book.bin` (formato Polyglot) a partir das aberturas da
  Lichess (CC0). Cada lance recebe peso = em quantas aberturas aparece. É reproduzível.
- `ferramentas/baixar_tablebases.py`: baixa as tablebases de 3 a 5 peças da Lichess (HTTPS), confere
  MD5 contra a lista fixada no Git e recusa qualquer arquivo de 6 peças ou mais.
- `testes/torneio.py`: o simulador. Três versões do mesmo Stockfish (`nossa`, `fixa`, `padrao`),
  relógio simulado com atraso artificial, cores alternadas, aberturas variadas.

**Perguntas prováveis**
- *De onde vem o book e a licença?* Das aberturas do repositório lichess-org/chess-openings, licença
  CC0 (domínio público); o texto da licença está junto em `ferramentas/dados/chess-openings/`.
- *Por que o book vale só até o meio-lance 10?* Regra do torneio. Duas travas em `book.py` (ply e
  posição inicial) e uma em `partida.py`.
- *O que é a escala do simulador e por que existe?* Uma partida real de 15+10 passa de uma hora. A
  escala (padrão 0,2) reduz o relógio, o atraso e as constantes de tempo absolutas na mesma
  proporção, só dentro do simulador. Serve para comparar e calibrar, não prova o relógio real.
- *Por que o `--atraso-s` é obrigatório?* Porque é um número que só a medição na mesa pode dar;
  não inventamos.
- *As tablebases entram no Git?* Não (~1 GB): ficam em `tablebases/`, entregues em mídia física. O
  script as baixa e confere.

---

## Perguntas para os três
- *Por que Stockfish e não um motor próprio?* O regulamento permite um projeto-base declarado; o
  Stockfish é GPLv3 e declaramos versão e origem no README. A nossa contribuição é o controle de tempo.
- *Quem fez o quê?* Ver a tabela "Quem é responsável por quê" no README.
- *Houve apoio de IA?* O README declara que parte do código foi desenvolvida com apoio do Claude Code,
  sob revisão do responsável de cada módulo. Cada um deve ser capaz de explicar o seu código sem ajuda.
