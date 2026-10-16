# III Chess Challenge — Equipe ICEV

**Marcos Paulo · Junio · Léo**

Motor de xadrez em Python escrito pela equipe: uma **função de avaliação heurística**, uma **busca
Negamax com poda Alfa-Beta** e uma **gestão de tempo própria**. A biblioteca python-chess cuida só
das regras do jogo: tabuleiro, lances legais e leitura dos arquivos de book e de tablebase. Quem
escolhe o lance é o nosso código.

> **Status: Sprint 0, estrutura pronta.** Cada arquivo traz o card, o responsável, o checklist e
> as funções que os outros módulos esperam (o contrato). As funções ainda levantam
> `NotImplementedError`, e cada um implementa as suas no próprio card.

---

## Estrutura

```
iii-chess-challenge/
├── main.py                  Programa da mesa: loop de jogo, entrada UCI, comandos     Junio  · S1 e S3
├── engine/
│   ├── evaluation.py        Avaliação heurística: material + tabelas de casas (AUTORAL)  Marcos · S1
│   ├── search.py            Negamax + Alfa-Beta + aprofundamento iterativo (AUTORAL)      Marcos · S2
│   ├── book.py              Opening book Polyglot, só até o meio-lance 10               Léo    · S1
│   ├── syzygy.py            Tablebases de finais, até 5 peças                           Léo    · S2
│   ├── time_manager.py      Gestão de tempo: orçamento por lance e relógio virtual      Junio  · S2
│   └── logger.py            Log da banca com os 8 campos                                Junio  · S1
├── tests/
│   ├── test_estrutura.py    Estrutura e regras fixas (já passam)
│   ├── test_<módulo>.py     Testes de cada card (pendentes até o card ser implementado)
│   └── simulate_match.py    Nosso bot × Stockfish limitado                              Léo    · S3
├── assets/
│   ├── book/                book.bin (Polyglot)
│   ├── syzygy/              tablebases de 3, 4 e 5 peças (fora do Git)
│   └── stockfish/           só para os testes (fora do Git)
├── logs/                    logs das partidas (fora do Git)
├── .vscode/                 configuração do VS Code (F5, testes, tarefas)
└── requirements.txt         só python-chess
```

## Como as peças se conectam

Na **nossa vez**, o `main.py` segue esta ordem:

1. `book.get_book_move(board)`: devolve um lance do book ou `None`. Só funciona até o meio-lance 10.
2. `syzygy.best_move(board)`: devolve o lance da tablebase ou `None`. Só funciona com 5 peças ou menos.
3. `time_manager.compute_time_budget(restante, incremento, lance)` devolve quantos segundos pensar.
   Esse valor vai para `search.search(board, segundos)`, que devolve um `SearchResult`.
4. `logger.log_move(...)` grava a linha com os 8 campos.
5. O lance aparece na tela em destaque, em UCI, para ser anunciado.

`search.search()` chama `evaluation.evaluate()` nas folhas da árvore e pode consultar
`syzygy.probe_wdl()` quando restam 5 peças ou menos.

Na **vez do adversário**, o programa lê o lance em UCI, valida contra `board.legal_moves` e só então
aplica. Uma entrada errada nunca derruba o programa.

**Convenção de avaliação:** os valores são em centipawns (100 = um peão). `evaluate()` dá a nota do
ponto de vista de **quem joga agora** (convenção Negamax). No `SearchResult` e no log, a nota é do
**nosso** ponto de vista.

---

## 1. Preparar o ambiente (com internet, uma vez por computador)

1. Instale o **Python 3.11 ou mais novo** (python.org). No Windows, marque **"Add python.exe to PATH"**.
2. Instale o **VS Code** e abra a pasta do projeto em **Arquivo → Abrir Pasta**. Abra a pasta onde
   está o `main.py`. O VS Code vai sugerir as extensões recomendadas (Python): aceite.
3. Crie o ambiente virtual e instale a dependência. Escolha **uma** destas opções:
   - **Terminal → Executar Tarefa → "1. Criar ambiente virtual (.venv) e instalar dependências"**; ou
   - `Ctrl+Shift+P` → **Python: Create Environment** → **Venv** → marque `requirements.txt`; ou
   - no terminal:
     ```
     python -m venv .venv
     .venv\Scripts\activate            (Windows)
     source .venv/bin/activate         (Mac/Linux)
     pip install -r requirements.txt
     ```
4. `Ctrl+Shift+P` → **Python: Select Interpreter** → escolha o `.venv`.
5. Confira se está tudo certo:
   ```
   python main.py
   python -m unittest discover -s tests -t . -v
   ```
   O `main.py` deve mostrar o tabuleiro e o próximo passo. Nos testes, `test_estrutura` precisa
   passar e os demais aparecem como *skipped* (pendentes).

Se o PowerShell disser que "a execução de scripts foi desabilitada", rode uma vez
`Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` ou use o terminal **Command Prompt**.

## 2. Rodar sem internet

Depois do passo 1, **o programa não usa internet para nada**. Ele roda inteiro no notebook, com o
Wi-Fi e os dados móveis desligados.

Para instalar num notebook que **não tem internet** (por exemplo, o da mesa):

1. Num computador com internet e com o `.venv` ativo:
   **Executar Tarefa → "3. Baixar pacotes para instalar sem internet"**, ou
   `pip wheel -r requirements.txt -w wheels`.
   Isso cria a pasta `wheels/` com o python-chess pronto para instalar.
2. Copie o projeto inteiro (com `wheels/`, `assets/book/` e `assets/syzygy/`) para o pendrive.
3. No notebook sem internet:
   ```
   python -m venv .venv
   .venv\Scripts\activate
   pip install --no-index --find-links wheels -r requirements.txt
   ```
   Ou use a tarefa **"4. Instalar sem internet"**.
4. Desligue o Wi-Fi e rode `python main.py`.

### No dia do torneio

- [ ] Wi-Fi e dados móveis **desligados**
- [ ] `python -m unittest discover -s tests -t .` passando no notebook da mesa
- [ ] `assets/book/book.bin` presente; `assets/syzygy/` só com tabelas de até 5 peças
- [ ] Notebook no carregador, sem suspensão de tela
- [ ] Rodar `python main.py` pelo terminal, não pelo depurador

## 3. No VS Code

| Atalho | O que faz |
| --- | --- |
| **F5** (aba Executar e Depurar) | `Jogar (main.py)`, `Jogar de brancas, 15+10`, `Testes (todos)`, `Simular partidas contra o Stockfish` |
| Ícone do **frasco** (Testes) | Roda e mostra cada teste, por card |
| **Terminal → Executar Tarefa** | Criar ambiente, rodar testes, baixar e instalar sem internet |

---

## 4. Regras do torneio que o código precisa respeitar

| Regra | Onde é garantida |
| --- | --- |
| O book só decide os **10 primeiros meios-lances**; com `board.ply() >= 10`, devolve `None` (FAQ 3) | `engine/book.py` (`MAX_BOOK_PLY = 10`) |
| Tablebases de **até 5 peças**, nunca 6 ou 7 (FAQ 4) | `engine/syzygy.py` (`MAX_PIECES = 5`) e `assets/syzygy/` |
| Log com os **8 campos** a cada lance nosso: número do lance, cor, lance, depth, nós, avaliação, PV e tempo | `engine/logger.py` |
| Lances do adversário e os nossos em **UCI** (ex.: `e2e4`, `e7e8q`); entrada errada não derruba o programa | `main.py` |
| Controle de tempo **15 min + 10 s** | `engine/time_manager.py` |
| Dependências: **somente python-chess** | `requirements.txt` |
| Jogar **sem internet** | seção 2 |
| Entrega: repositório Git para **icev@somosicev.com** até **04/11/2026** | seção 7 |

O `tests/test_estrutura.py` confere os limites fixos (10 meios-lances, 5 peças, 8 campos, 15+10 e
requirements). Se alguém mudar um desses valores por engano, o teste falha.

---

## 5. Declaração de autoria

| Parte | Autoria |
| --- | --- |
| `engine/evaluation.py`, `engine/search.py`: avaliação e busca, o núcleo da inteligência | **Equipe** (Marcos Paulo) |
| `main.py`, `engine/logger.py`, `engine/time_manager.py`: programa da mesa, log e gestão de tempo | **Equipe** (Junio) |
| `engine/book.py`, `engine/syzygy.py`, `tests/`: integração do book e das tablebases, testes | **Equipe** (Léo) |
| **python-chess 1.11.2** (GPLv3): tabuleiro, regras, lances legais, leitura de book e de tablebases. Não escolhe lances | Terceiros |
| `assets/book/book.bin`: opening book Polyglot. Origem e licença em `assets/book/LEIA.txt`; book não conta como autoria (FAQ 3) | Terceiros |
| Tablebases Syzygy de até 5 peças. Origem em `assets/syzygy/LEIA.txt` | Terceiros |
| Stockfish: apenas adversário de treino em `tests/simulate_match.py`; **não faz parte do motor** | Terceiros |

### Modificação significativa

*(A preencher na Sprint 3: Marcos.)*

Como o projeto usa python-chess (GPLv3), a equipe deve decidir a licença do repositório antes da
entrega. A GPLv3 é a escolha compatível.

---

## 6. Sprints e cards

| Sprint | Card | Responsável | Pontos | Arquivo |
| --- | --- | --- | --- | --- |
| 0 | Estrutura inicial do projeto e configurações | Equipe | 3 | este repositório |
| 1 | Representação e função de avaliação heurística | Marcos | 4 | `engine/evaluation.py` |
| 1 | CLI principal, entradas e sistema de logs | Junio | 4 | `main.py`, `engine/logger.py` |
| 1 | Opening book local (.bin) com limite estrito | Léo | 4 | `engine/book.py` |
| 2 | Negamax com poda Alfa-Beta | Marcos | 5 | `engine/search.py` |
| 2 | Gestão de tempo própria (clock budget) | Junio | 4 | `engine/time_manager.py` |
| 2 | Integração de tablebases (finais) | Léo | 3 | `engine/syzygy.py` |
| 3 | Comandos de emergência na mesa (`desfazer`, `t mm:ss`) | Junio | 3 | `main.py`, `engine/time_manager.py` |
| 3 | Testes automatizados vs. Stockfish nível 1 | Léo | 3 | `tests/simulate_match.py` |
| 3 | Preparar repositório e entrega final | Equipe | 2 | README, `assets/` |

Os testes de cada card já estão escritos em `tests/test_<módulo>.py`, com alguns exemplos para
começar. Eles aparecem como *pendentes* até o card ser implementado e, a partir daí, passam a valer
sozinhos.

---

## 7. Git: repositório e fluxo da equipe

O repositório local já está criado, com o primeiro commit. Para publicar no GitHub:

1. No GitHub: **New repository** → nome `iii-chess-challenge`, **privado**, **sem** README.
2. Na pasta do projeto:
   ```
   git remote add origin https://github.com/SEU-USUARIO/iii-chess-challenge.git
   git push -u origin main
   ```
3. No GitHub: **Settings → Collaborators → Add people** e adicione o Junio e o Léo.
4. Junio e Léo: `git clone <url>` e depois o passo 1 deste README.

**Fluxo de trabalho:** uma branch por card. Faça o merge na `main` só com os testes passando.

```
git switch main && git pull                 # começar sempre atualizado
git switch -c sprint1/evaluation            # ex.: sprint1/book, sprint1/cli-logger
# ... trabalhar, rodar os testes ...
git add . && git commit -m "evaluation: material e tabelas de casas"
git push -u origin sprint1/evaluation       # depois: Pull Request para a main no GitHub
```

**Entrega final:** repositório para **icev@somosicev.com** até **04/11/2026**.
