# Rascunho do e-mail para a organização

> Este é um RASCUNHO. O prazo informado no CLAUDE.md era 18/10/2026 e já passou: se ninguém enviou,
> envie logo e diga que está sendo enviado com atraso. Confirme no regulamento o endereço correto
> (o único que aparece no projeto é icev@somosicev.com, citado como destino da entrega do Git) e
> **revise o que está entre colchetes** antes de enviar. Só envie depois que o grupo confirmar qual
> plano vale (Stockfish como base, ou motor próprio), porque a declaração abaixo precisa bater com o código.

**Assunto:** III Chess Challenge — Equipe [nome da equipe]: controle de tempo e modificação significativa

Prezados organizadores,

Somos a equipe [nome da equipe] (Marcos Paulo, Junio e Léo) e escrevemos para tratar de dois pontos
do regulamento.

**1. Controle de tempo**
O FAQ do torneio indica 15 minutos + 10 segundos por lance, e o regulamento indica 25 minutos sem
incremento. Como nosso programa tem perfis para os dois (além do armageddon: 5 min para as brancas,
4 min para as pretas, empate classificando as pretas), pedimos a confirmação de **qual controle de
tempo será usado** no torneio.

**2. Projeto-base e modificação significativa**
- **Projeto-base:** Stockfish 19 (GPLv3), executado localmente via protocolo UCI. A licença e a
  versão estão declaradas no README do repositório.
- **Modificação significativa:** um componente de gestão de tempo escrito pela equipe (arquivo
  `tempo.py`), que decide quanto tempo o motor pensa em cada lance e quando parar, descontando o
  tempo gasto na mesa (anunciar o lance, mover a peça, acionar o relógio) e protegendo a partida
  contra o estouro do relógio. Ele funciona nas partidas e será defendido na arguição técnica.
- Também desenvolvemos o programa da mesa (leitura de lances em UCI, comandos de emergência, log com
  os 8 campos, reinício automático do motor) e um simulador de partidas que compara a nossa gestão de
  tempo com tempo fixo por lance e com a gestão padrão do Stockfish.
- **Terceiros:** opening book gerado a partir de aberturas da Lichess (licença CC0) e tablebases
  Syzygy de até 5 peças (origem declarada no README).

Ficamos à disposição para qualquer esclarecimento.

Atenciosamente,
[Nome], pela Equipe [nome da equipe]
[contato]
