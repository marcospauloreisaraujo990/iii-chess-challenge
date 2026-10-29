"""Programa que fica aberto na mesa. Dono: Junio.

Liga tudo: lê o lance adversário (UCI), valida, consulta book.py, usa tempo.py,
chama o Stockfish (chess.engine) e grava o log. Robustez acima de tudo:
nenhum erro pode fechar o programa e o estado deve ficar igual ao tabuleiro físico.
"""
import glob
import math
import os
import sys
import threading
import time

import chess
import chess.engine
import chess.pgn

import book
import log
import tempo


# Regra do torneio: tablebases só até 5 peças. Duas travas: o motor nunca sonda mais que
# isso (SyzygyProbeLimit) e avisamos se aparecer arquivo de 6+ peças na pasta.
MAX_PECAS_TABLEBASE = 5

# Regra do torneio: book só até o meio-lance 10 (board.ply() < 10).
PLY_MAXIMO_BOOK = 10

# PROVISÓRIO: quanto a avaliação precisa cair (em centésimos de peão) entre duas
# profundidades para contar como "caiu". 0 = qualquer queda. O número final sai dos
# testes do Léo e é combinado com o Marcos, não é chute nosso.
LIMIAR_QUEDA_CP = 0


def _pecas_no_arquivo_syzygy(nome):
    """'KQRvKR.rtbw' -> 5 (K+D+T contra K+T). Conta as letras das peças, sem o 'v' e a extensão."""
    base = nome.split(".")[0]
    return len(base.replace("v", ""))


def abrir_motor(caminho_stockfish, threads, hash_mb, syzygy_path=None):
    """Abre o Stockfish por UCI e configura Threads, Hash e as tablebases.

    - Threads e Hash: quem chama escolhe (os valores finais saem dos testes).
    - SyzygyPath: aceita uma ou várias pastas (separadas por ":" no Linux, ";" no Windows).
      Pastas que não existem são avisadas na tela e ignoradas.
    - SyzygyProbeLimit fica SEMPRE em 5, então o motor nunca usa tablebase de 6 ou 7
      peças, mesmo que o arquivo esteja na pasta (e avisamos se estiver).
    - Se algo falhar depois de abrir o processo, fechamos o processo antes de levantar o
      erro: assim não sobra Stockfish órfão, nem ao reiniciar o motor no meio da partida.
    - Se der erro (caminho errado, motor não abre), a exceção sobe: quem chama (main)
      decide se tenta de novo.
    """
    motor = chess.engine.SimpleEngine.popen_uci(caminho_stockfish)
    try:
        # O limite de 5 peças vai SEMPRE, com ou sem pasta de tablebases (regra do torneio).
        opcoes = {"Threads": threads, "Hash": hash_mb, "SyzygyProbeLimit": MAX_PECAS_TABLEBASE}
        if syzygy_path:
            pastas = [p for p in syzygy_path.split(os.pathsep) if p]
            existentes = [p for p in pastas if os.path.isdir(p)]
            for ausente in set(pastas) - set(existentes):
                print(f"[motor] AVISO: pasta de tablebases não existe: {ausente}", file=sys.stderr)
            if existentes:
                opcoes["SyzygyPath"] = os.pathsep.join(existentes)
                grandes = [f for pasta in existentes for f in os.listdir(pasta)
                           if f.endswith((".rtbw", ".rtbz")) and _pecas_no_arquivo_syzygy(f) > MAX_PECAS_TABLEBASE]
                if grandes:
                    print(f"[motor] AVISO: as pastas de tablebases têm arquivos de mais de "
                          f"{MAX_PECAS_TABLEBASE} peças ({len(grandes)}). O motor não vai usá-los, "
                          f"mas o ideal é tirá-los.", file=sys.stderr)
        motor.configure(opcoes)
    except Exception:
        motor.quit()
        raise
    return motor


def interpretar_entrada(texto, board):
    """Transforma o que o operador digitou em (tipo, valor). Não mexe no tabuleiro.

    Tipos: "lance" (valor = chess.Move), "desfazer", "tab", "go", "fen" (valor = texto do FEN),
    "tempo" (valor = "mm:ss" como digitado), "vazio" e "erro" (valor = mensagem para a tela).
    """
    texto = texto.strip()
    if not texto:
        return "vazio", None
    palavras = texto.split()
    comando = palavras[0].lower()

    if comando == "desfazer":
        return "desfazer", None
    if comando == "tab":
        return "tab", None
    if comando == "go" and len(palavras) == 1:
        return "go", None
    if comando == "fen":
        if len(palavras) < 2:
            return "erro", "Uso: fen <posição FEN completa>"
        return "fen", " ".join(palavras[1:])
    if comando == "t":
        if len(palavras) != 2:
            return "erro", "Uso: t mm:ss (exemplo: t 12:34)"
        return "tempo", palavras[1]

    # Qualquer outra coisa é tentativa de lance em UCI (e2e4, e1g1, e7e8q).
    # Texto digitado pode ser enorme: na tela só mostramos o começo.
    mostrado = texto if len(texto) <= 40 else texto[:40] + "..."
    if len(palavras) != 1:
        return "erro", f"Digite um lance por vez: '{mostrado}'. Exemplos: e2e4, roque e1g1, promoção e7e8q."
    try:
        lance = chess.Move.from_uci(comando)
    except ValueError:
        return "erro", f"'{mostrado}' não é UCI. Exemplos: e2e4, roque e1g1, promoção e7e8q."
    if lance not in board.legal_moves:
        dica = " (promoção precisa da letra: e7e8q)" if _falta_promocao(lance, board) else ""
        return "erro", f"Lance ilegal nesta posição: {comando}{dica}"
    return "lance", lance


def _falta_promocao(lance, board):
    """True se o peão chega na última fila sem a letra da peça (e7e8 em vez de e7e8q)."""
    peca = board.piece_at(lance.from_square)
    if lance.promotion or peca is None or peca.piece_type != chess.PAWN:
        return False
    return chess.square_rank(lance.to_square) in (0, 7)


GO = "go"  # o que ler_lance devolve quando o operador manda o motor pensar


def ler_lance(board, ao_sincronizar=None, entrada=input, saida=print, pode_go=False):
    """Lê texto, valida com chess.Move.from_uci e board.legal_moves; entrada ruim só pede de novo.

    Comandos: desfazer | tab | fen <posição> | t mm:ss | go

    Devolve:
      - um chess.Move legal, quando o operador digitou um lance;
      - None, quando o tabuleiro mudou por comando (desfazer ou fen): quem chamou
        precisa reler de quem é a vez antes de continuar;
      - GO, só se `pode_go=True` e o operador digitou `go` (liberar o motor para pensar).
    `tab` e `t mm:ss` não encerram a leitura: mostram/atualizam e pedem de novo.
    `ao_sincronizar(segundos)` é chamado com o tempo restante que o `t mm:ss` informou.
    `entrada` e `saida` existem só para os testes (padrão: teclado e tela).
    """
    while True:
        try:
            texto = entrada("lance> ")
        except KeyboardInterrupt:
            # Ctrl+C por engano não pode encerrar a partida (travar = derrota).
            saida("Ctrl+C ignorado. Para sair de verdade, feche a janela.")
            continue
        # EOFError (teclado/stdin fechado) não é tratado aqui de propósito: não há como
        # continuar sem entrada, então sobe para o main salvar o PGN e sair limpo.
        tipo, valor = interpretar_entrada(texto, board)

        if tipo == "lance":
            return valor
        if tipo == "vazio":
            continue
        if tipo == "erro":
            saida(valor)
        elif tipo == "go":
            if pode_go:
                return GO
            saida("'go' só vale quando o programa está esperando para pensar.")
        elif tipo == "tab":
            saida(str(board))
            saida(f"FEN: {board.fen()}")
            saida("Vez das " + ("brancas" if board.turn == chess.WHITE else "pretas"))
        elif tipo == "desfazer":
            if board.move_stack:
                desfeito = board.pop()
                saida(f"Desfeito: {desfeito.uci()}")
                return None
            saida("Nada para desfazer.")
        elif tipo == "fen":
            try:
                novo = chess.Board(valor)
            except ValueError:
                saida("FEN inválido. Nada foi alterado.")
                continue
            if not novo.is_valid():
                # Sintaxe certa, mas posição impossível (sem rei, peão na 1ª fila...).
                saida("FEN ilegal (posição impossível). Nada foi alterado.")
                continue
            board.set_fen(novo.fen())
            saida("Posição carregada (desfazer não volta antes daqui).")
            return None
        elif tipo == "tempo":
            _tratar_comando_tempo(valor, ao_sincronizar, saida)


def _tratar_comando_tempo(texto_mmss, ao_sincronizar, saida):
    """Passa 't mm:ss' para tempo.sincronizar (código do Marcos). Nunca derruba a partida.

    Comando de emergência digitado sob pressão: qualquer erro vira mensagem na tela,
    e um valor estranho nunca chega ao relógio. Aceita int ou float (754 ou 754.0).
    `ao_sincronizar` pode devolver False para recusar o valor (ex.: operador não confirmou).
    """
    try:
        segundos = tempo.sincronizar("t " + texto_mmss)
    except NotImplementedError:
        saida("Comando t ainda não disponível (tempo.sincronizar não foi implementado).")
        return
    except ValueError as erro:
        saida(f"Tempo inválido: {erro}")
        return
    except Exception as erro:  # erro inesperado no código de tempo: avisa e segue jogando
        saida(f"Erro no comando t ({type(erro).__name__}). O relógio não foi alterado.")
        return
    if not _numero_positivo(segundos):
        saida("Tempo inválido. Use t mm:ss (exemplo: t 12:34). O relógio não foi alterado.")
        return
    if ao_sincronizar is None:
        saida(f"Tempo lido ({segundos} s), mas nenhum relógio está ligado: nada foi ajustado.")
        return
    try:
        aceito = ao_sincronizar(float(segundos))
    except EOFError:
        raise  # teclado fechado: sobe para a partida salvar e sair
    except Exception as erro:
        saida(f"Erro ao ajustar o relógio ({type(erro).__name__}). O relógio não foi alterado.")
        return
    if aceito is False:
        return  # quem chamou já explicou na tela
    saida(f"Relógio ajustado para {segundos} s.")


def _avaliacao_para_log(score):
    """Placar do motor -> +0.35 (peões) ou "#3" (mate), do ponto de vista de quem joga."""
    mate = score.mate()
    if mate is not None:
        return f"#{mate}"
    return score.score() / 100


def _numero_finito(valor):
    return isinstance(valor, (int, float)) and not isinstance(valor, bool) and math.isfinite(valor)


def _numero_positivo(valor):
    return (isinstance(valor, (int, float)) and not isinstance(valor, bool)
            and math.isfinite(valor) and valor > 0)


def _alvo_e_maximo(board, relogio, tempo_provisorio_s):
    """Pede (alvo, máximo) ao tempo.py e protege quem chama de resposta ruim.

    Devolve (alvo_s, maximo_s), ou None se o tempo.py falhou ou devolveu lixo: nesse caso
    escolher_lance entra em modo de emergência (lance mais rápido possível).
    Aqui NÃO há regra de quanto pensar: só conferimos que a resposta faz sentido.
    """
    try:
        alvo, maximo = tempo.calcular_tempo(relogio["restante_s"], relogio["incremento_s"],
                                            board.fullmove_number, relogio["atraso_humano_s"])
        restante = relogio["restante_s"]
        atraso = relogio["atraso_humano_s"]
    except NotImplementedError:
        if tempo_provisorio_s is None:
            raise RuntimeError("tempo.calcular_tempo ainda não existe: informe tempo_provisorio_s (só para testes).")
        return tempo_provisorio_s, tempo_provisorio_s
    except Exception as erro:
        print(f"[tempo] calcular_tempo falhou ({type(erro).__name__}: {erro}). Modo de emergência.", file=sys.stderr)
        return None
    if not (_numero_positivo(alvo) and _numero_positivo(maximo) and _numero_positivo(restante)):
        print(f"[tempo] calcular_tempo devolveu valores inválidos ({alvo!r}, {maximo!r}) "
              f"com restante {restante!r}. Modo de emergência.", file=sys.stderr)
        return None
    try:
        # Nunca pensar mais do que sobra DEPOIS de anunciar, mover e apertar o relógio.
        disponivel = restante - atraso
    except TypeError:
        disponivel = None
    if not _numero_positivo(disponivel):
        print(f"[tempo] não sobra tempo depois do atraso humano (restante {restante!r}, atraso {atraso!r}). "
              f"Modo de emergência.", file=sys.stderr)
        return None
    maximo = min(maximo, disponivel)
    return min(alvo, maximo), maximo


def escolher_lance(board, motor, perfil, relogio, caminho_book=None, tempo_provisorio_s=None,
                   folga_watchdog_s=None, economia=False):
    """book -> tempo -> Stockfish (analysis, parada em tempo real) -> devolve (lance, info).

    `relogio` é um dicionário: {"restante_s": ..., "incremento_s": ..., "atraso_humano_s": ...}.
    `perfil` ("15+10", "25+0", ...) fica para o log e para o tempo.py evoluir.
    `info` tem as chaves que o log.registrar_lance espera (book, profundidade, nos,
    avaliacao, pv, tempo_s) mais `motor_caiu` (True = o Stockfish travou ou morreu e o
    main precisa reiniciá-lo; o lance devolvido é o melhor que deu para obter).

    Ordem das decisões (as mesmas do CLAUDE.md):
    1. Book, só se a partida começou da posição inicial E board.ply() < 10. Conferimos
       aqui E dentro de book.py (duas travas). Depois do comando `fen` a posição inicial
       muda e o contador de lances zera, então o book fica desligado.
    2. Atalho de tempo zero (tempo.atalho_tempo_zero, do Marcos), se existir.
    3. Tempo do lance (tempo.calcular_tempo, do Marcos) -> (alvo, máximo). Se o tempo.py
       falhar ou devolver lixo: modo de emergência = lance mais rápido possível
       (Limit(depth=1)), sem inventar nenhum número de tempo.
    4. Stockfish pensa. O máximo vai para o motor como limite DURO (Limit(time=...)).
    5. A cada profundidade nova perguntamos a tempo.deve_parar se já pode parar.
    6. Watchdog (opcional): se `folga_watchdog_s` for informado e o motor passar de
       máximo + folga sem responder, fechamos o processo à força em vez de esperar para
       sempre. A folga é decisão do grupo (não tem valor padrão: regra 4).

    `economia=True` (quem chama decide com tempo.modo_economia, do Marcos) corta o ALVO por
    tempo.FATOR_ECONOMIA, nunca abaixo de tempo.TEMPO_MINIMO_S e nunca acima do máximo. O
    máximo, o limite duro do motor, não muda.

    Enquanto tempo.py for esqueleto, é preciso informar `tempo_provisorio_s` (só para
    testar). Não existe valor padrão de propósito: não inventamos tempo (regra 4).
    """
    if not any(True for _ in board.legal_moves):
        raise ValueError("Não há lances legais: a partida terminou.")
    inicio = time.monotonic()

    def resposta(lance, **extra):
        info = {"book": False, "profundidade": 0, "nos": 0, "avaliacao": 0.0, "pv": [lance],
                "tempo_s": time.monotonic() - inicio, "motor_caiu": False}
        info.update(extra)
        return lance, info

    # 1) Book
    partida_do_inicio = board.root().fen() == chess.STARTING_FEN
    if caminho_book and partida_do_inicio and board.ply() < PLY_MAXIMO_BOOK:
        try:
            lance_book = book.lance_do_book(board, caminho_book)
        except Exception as erro:  # book quebrado não pode derrubar a partida
            print(f"[book] ignorado: {type(erro).__name__}: {erro}", file=sys.stderr)
            lance_book = None
        if lance_book is not None and lance_book in board.legal_moves:
            return resposta(lance_book, book=True)

    # 2) Atalho de tempo zero (único lance, tablebase...). Lógica do Marcos.
    em_tablebase = len(board.piece_map()) <= MAX_PECAS_TABLEBASE
    try:
        atalho = tempo.atalho_tempo_zero(board, None, em_tablebase)
    except NotImplementedError:
        atalho = None
    except Exception as erro:
        print(f"[tempo] atalho_tempo_zero falhou ({type(erro).__name__}: {erro}). Ignorado.", file=sys.stderr)
        atalho = None
    if atalho is not None and atalho in board.legal_moves:
        return resposta(atalho)

    # 3) Quanto tempo pensar
    limites = _alvo_e_maximo(board, relogio, tempo_provisorio_s)
    if limites is None:
        alvo_s = maximo_s = None
        limite_motor = chess.engine.Limit(depth=1)  # emergência: o mais rápido possível
    else:
        alvo_s, maximo_s = limites
        if economia:
            alvo_s = min(max(alvo_s * tempo.FATOR_ECONOMIA, tempo.TEMPO_MINIMO_S), maximo_s)
        limite_motor = chess.engine.Limit(time=maximo_s)

    # 4 e 5) Stockfish pensa
    ultimo_info = None
    profundidade_vista = 0
    melhor_anterior = None
    estaveis = 0
    aval_anterior = None
    lance = None
    motor_caiu = False
    vigia = None
    if folga_watchdog_s is not None and maximo_s is not None:
        vigia = threading.Timer(maximo_s + folga_watchdog_s, motor.close)  # mata o processo
        vigia.daemon = True
        vigia.start()
    try:
        with motor.analysis(board, limite_motor) as analise:
            for info in analise:
                if "pv" not in info or "score" not in info or "depth" not in info:
                    continue
                if info.get("lowerbound") or info.get("upperbound"):
                    continue  # placar parcial (janela de busca): não serve para decidir
                ultimo_info = info
                if info["depth"] <= profundidade_vista:
                    continue  # só decidimos quando uma profundidade NOVA termina
                profundidade_vista = info["depth"]

                melhor = info["pv"][0]
                mudou = melhor_anterior is not None and melhor != melhor_anterior
                estaveis = estaveis + 1 if (melhor_anterior is not None and not mudou) else 0
                melhor_anterior = melhor
                aval = info["score"].relative.score(mate_score=100_000)
                caiu = aval_anterior is not None and aval < aval_anterior - LIMIAR_QUEDA_CP
                aval_anterior = aval

                if limites is None:
                    continue  # emergência: o Limit(depth=1) já encerra sozinho
                decorrido = time.monotonic() - inicio
                try:
                    parar = tempo.deve_parar(decorrido, alvo_s, maximo_s, estaveis, mudou, caiu)
                except Exception:
                    # Sem a decisão do tempo.py (esqueleto ou bug): para no alvo.
                    parar = decorrido >= alvo_s
                if parar:
                    break
            analise.stop()
            lance = analise.wait().move
    except KeyboardInterrupt:
        # Ctrl+C por engano não pode custar a partida: para a busca e usa o melhor lance visto.
        print("[motor] Ctrl+C durante a busca: usando o melhor lance visto até agora.", file=sys.stderr)
    except Exception as erro:
        # Stockfish morreu, travou e o vigia o fechou, ou o protocolo falhou.
        motor_caiu = True
        print(f"[motor] falhou durante a busca ({type(erro).__name__}: {erro}). Precisa reiniciar.", file=sys.stderr)
    finally:
        if vigia is not None:
            vigia.cancel()

    # O lance final é o que o motor devolveu; se não houver (caso extremo), o melhor visto,
    # e em último caso qualquer lance legal. Nunca devolvemos None.
    if lance is None or lance not in board.legal_moves:
        lance = melhor_anterior if melhor_anterior in board.legal_moves else next(iter(board.legal_moves))
    extra = {"motor_caiu": motor_caiu}
    if ultimo_info is not None:
        pv = list(ultimo_info["pv"])
        extra.update(profundidade=ultimo_info["depth"], nos=ultimo_info.get("nodes", 0),
                     avaliacao=_avaliacao_para_log(ultimo_info["score"].relative),
                     pv=pv if pv and pv[0] == lance else [lance])
    return resposta(lance, **extra)


def salvar_pgn(board, caminho, cabecalhos=None):
    """Salva a partida em PGN a cada lance. Devolve True se salvou, False se falhou.

    Como funciona, em linguagem simples:
    - O PGN é reconstruído do zero a partir dos lances do tabuleiro (board.move_stack).
      Assim ele sempre bate com o que o programa acha que é a partida, mesmo depois
      de um `desfazer`.
    - Se a posição inicial não era a padrão (comando `fen`), o python-chess grava o
      FEN no cabeçalho e o PGN continua válido.
    - A gravação é segura contra queda: escreve num arquivo temporário (.tmp), força
      a ida ao disco e só então troca pelo definitivo. Se o programa cair no meio, o
      PGN do lance anterior continua inteiro.
    - Nunca levanta erro: falha de disco vira aviso na tela e a partida segue
      (travar = derrota).

    `cabecalhos` é opcional: dicionário como {"White": "Capablanca", "Black": "Fulano"}.
    """
    temporario = caminho + ".tmp"
    try:
        jogo = chess.pgn.Game.from_board(board)
        jogo.headers["Event"] = "III Chess Challenge"
        for chave, valor in (cabecalhos or {}).items():
            jogo.headers[chave] = str(valor)
        jogo.headers["Result"] = board.result(claim_draw=False)

        pasta = os.path.dirname(caminho)
        if pasta:
            os.makedirs(pasta, exist_ok=True)
        with open(temporario, "w", encoding="utf-8") as arquivo:
            arquivo.write(str(jogo) + "\n\n")
            arquivo.flush()
            os.fsync(arquivo.fileno())
        os.replace(temporario, caminho)
        return True
    except Exception as erro:
        print(f"[pgn] não consegui salvar {caminho}: {erro}", file=sys.stderr)
        return False


# ----------------------------------------------------------------------------------
# Configuração. Nenhum valor de TEMPO tem padrão aqui (regra 4 do CLAUDE.md): atraso
# humano, tempo de teste e folga do watchdog vêm do operador ou do ambiente.
# Threads e Hash usam os padrões do próprio Stockfish (1 thread, 16 MB); os valores
# finais saem dos testes do Léo.
# ----------------------------------------------------------------------------------
# Caminhos ancorados na pasta do programa: abrir de outra pasta não muda o comportamento.
_RAIZ = os.path.dirname(os.path.abspath(__file__))
PASTA_STOCKFISH = os.path.join(_RAIZ, "stockfish")
CAMINHO_BOOK = os.path.join(_RAIZ, "book", "book.bin")
PASTA_TABLEBASES = os.path.join(_RAIZ, "tablebases")
PASTA_PARTIDAS = os.path.join(_RAIZ, "partidas")
THREADS = 1
HASH_MB = 16
TENTATIVAS_REINICIO_MOTOR = 3


def _achar_stockfish():
    """Primeiro executável stockfish-* da pasta stockfish/ (ignora .md, .txt e pastas)."""
    for caminho in sorted(glob.glob(os.path.join(PASTA_STOCKFISH, "stockfish-*"))):
        if os.path.isfile(caminho) and os.access(caminho, os.X_OK) and not caminho.endswith((".md", ".txt")):
            return caminho
    return None


def _numero_do_ambiente(nome):
    """Lê um número (segundos) de uma variável de ambiente; None se não existir ou for inválido."""
    texto = os.environ.get(nome)
    if texto is None:
        return None
    try:
        valor = float(texto)
    except ValueError:
        print(f"[config] {nome}={texto!r} não é um número. Ignorado.", file=sys.stderr)
        return None
    return valor if math.isfinite(valor) and valor >= 0 else None


def _mmss(segundos):
    segundos = max(0, int(round(segundos)))
    return f"{segundos // 60}:{segundos % 60:02d}"


def _perguntar_cor(entrada, saida):
    while True:
        resposta = entrada("Nossa cor (brancas/pretas): ").strip().lower()
        if resposta in ("b", "brancas", "branca"):
            return chess.WHITE
        if resposta in ("p", "pretas", "preta"):
            return chess.BLACK
        saida("Digite 'brancas' ou 'pretas'.")


def _perguntar_perfil(entrada, saida, cor):
    """Pergunta o perfil e devolve a chave de tempo.PERFIS. Perfil errado falha AQUI, na largada."""
    while True:
        resposta = entrada("Perfil de relógio (15+10 / 25+0 / armageddon): ").strip().lower()
        if resposta == "armageddon":
            resposta = "armageddon_brancas" if cor == chess.WHITE else "armageddon_pretas"
        if resposta in tempo.PERFIS:
            return resposta
        saida("Perfil desconhecido. Opções: 15+10, 25+0, armageddon.")


def _perguntar_atraso(entrada, saida):
    """Atraso humano por lance (anunciar, repetir, mover, apertar o relógio), em segundos."""
    atraso = _numero_do_ambiente("CAPABLANCA_ATRASO_HUMANO_S")
    if atraso is not None:
        return atraso
    while True:
        resposta = entrada("Atraso humano estimado por lance, em segundos (sai dos testes do Léo): ").strip()
        try:
            atraso = float(resposta.replace(",", "."))
        except ValueError:
            atraso = None
        if atraso is not None and math.isfinite(atraso) and atraso >= 0:
            return atraso
        saida("Digite um número, por exemplo 8 ou 6.5.")


def _reiniciar_motor(motor_antigo, reabrir_motor, saida):
    """Fecha o motor velho (se der) e tenta abrir um novo. Devolve o motor ou None."""
    if motor_antigo is not None:
        try:
            motor_antigo.quit()
        except Exception:
            try:
                motor_antigo.close()
            except Exception:
                pass
    if reabrir_motor is None:
        return None
    for tentativa in range(1, TENTATIVAS_REINICIO_MOTOR + 1):
        try:
            novo = reabrir_motor()
            saida(f"Motor reiniciado (tentativa {tentativa}).")
            return novo
        except Exception as erro:
            saida(f"Falha ao reiniciar o motor ({type(erro).__name__}: {erro}).")
    return None


def jogar_partida(minha_cor, chave_perfil, relogio, motor, entrada=input, saida=print,
                  pasta_partidas=PASTA_PARTIDAS, caminho_book=None, tempo_provisorio_s=None,
                  folga_watchdog_s=None, reabrir_motor=None, agora=time.monotonic):
    """Laço da partida. Devolve o resultado ("1-0", "0-1", "1/2-1/2").

    Cada volta: se é a vez do adversário, lê o lance do operador (com os comandos de
    emergência); se é a nossa, o motor escolhe. Depois de cada lance: log, PGN e relógio.
    O tabuleiro físico é a fonte da verdade: `desfazer` e `fen` corrigem o do programa.

    Depois de um `desfazer` ou `fen` na NOSSA vez, o motor NÃO pensa sozinho: o programa
    espera o operador acertar a posição e digitar `go`. (Sem isso, ao corrigir o lance
    errado do adversário, o motor gastaria tempo pensando sobre a posição errada.)

    Relógio: guardado aqui. A cada lance nosso desconta o tempo REAL desde que o lance do
    adversário foi aceito (inclui book, cálculo, motor reiniciado, operador digitando),
    mais o atraso humano, e soma o incremento. `t mm:ss` corrige o valor.

    Robustez (travar = derrota): erro em qualquer volta é mostrado e a partida segue; se o
    motor cair, é reiniciado; se não voltar, o operador digita também o nosso lance
    ("modo manual"). EOFError (teclado fechado) sai limpo, com log e PGN já salvos.

    O log tem só os NOSSOS lances (são eles que têm profundidade, nós e avaliação). Os
    lances do adversário ficam no PGN. Um lance nosso desfeito continua no log.
    """
    board = chess.Board()
    carimbo = time.strftime("%Y-%m-%d_%H-%M-%S")
    caminho_pgn = os.path.join(pasta_partidas, carimbo + ".pgn")
    arquivo_log = log.abrir_log(os.path.join(pasta_partidas, carimbo + ".txt"))
    nome_nosso, nome_rival = "Capablanca", "Adversario"
    cabecalhos = {"White": nome_nosso if minha_cor == chess.WHITE else nome_rival,
                  "Black": nome_nosso if minha_cor == chess.BLACK else nome_rival,
                  "TimeControl": chave_perfil, "Date": time.strftime("%Y.%m.%d")}
    cor_texto = "brancas" if minha_cor == chess.WHITE else "pretas"
    inicio_perfil_s, incremento_perfil_s = tempo.PERFIS[chave_perfil]
    erros_seguidos = 0
    esperando_go = False
    inicio_da_vez = agora()   # quando o nosso relógio passou a correr nesta vez
    nossos_lances = 0
    historico_aval = []       # (posição do lance na partida, avaliação em centésimos de peão); None = não conta como calma

    def podar_historico():
        """Esquece avaliações de lances que não existem mais (depois de `desfazer` ou `fen`).

        Cada avaliação guarda em que lance da partida foi feita. Se a pilha de lances do
        tabuleiro ficou menor que isso, o lance foi desfeito (ou a posição foi recarregada
        pelo `fen`): a avaliação sai, para o modo_economia não decidir com dados falsos.
        """
        historico_aval[:] = [(indice, valor) for indice, valor in historico_aval if indice < len(board.move_stack)]

    def ao_sincronizar(segundos):
        """Aplica o `t mm:ss`. Pede confirmação se passar do máximo possível (provável erro)."""
        maximo_possivel = inicio_perfil_s + incremento_perfil_s * nossos_lances
        if segundos > maximo_possivel:
            saida(f"ATENÇÃO: {_mmss(segundos)} é MAIS do que o máximo possível agora "
                  f"({_mmss(maximo_possivel)}). Provável erro de digitação.")
            if entrada("Confirma mesmo assim? (s/N): ").strip().lower() not in ("s", "sim"):
                saida("Relógio NÃO alterado.")
                return False
        relogio["restante_s"] = segundos
        return True

    try:
        while True:
            while board.outcome() is None:
                try:
                    podar_historico()
                    if board.turn == minha_cor:
                        # --- nossa vez ---
                        pensar = True
                        if esperando_go:
                            saida("Posição corrigida? Digite 'go' para o motor pensar "
                                  "(ou desfazer / tab / fen / t mm:ss).")
                            pedido = ler_lance(board, ao_sincronizar, entrada, saida, pode_go=True)
                            if pedido == GO:
                                esperando_go = False
                            else:
                                pensar = False
                                if pedido is None:  # desfazer/fen: o tabuleiro mudou
                                    esperando_go = board.turn == minha_cor
                                else:
                                    saida("É a vez do motor: digite 'go', ou corrija com desfazer.")
                        if pensar:
                            if motor is None:
                                motor = _reiniciar_motor(None, reabrir_motor, saida)
                            lance, info, manual = None, None, False
                            if motor is not None:
                                # o tempo que já passou nesta vez (inclusive de tentativas anteriores) já foi gasto
                                relogio_vez = dict(relogio)
                                relogio_vez["restante_s"] = max(0.0, relogio["restante_s"] - (agora() - inicio_da_vez))
                                try:
                                    economia = bool(tempo.modo_economia([v for _, v in historico_aval],
                                                                         tempo.material_em_centipawns(board)))
                                except Exception:   # bug no código de tempo: sem economia, a partida segue
                                    economia = False
                                saida(f"Pensando... (relógio estimado {_mmss(relogio_vez['restante_s'])})"
                                      + (" [modo economia]" if economia else ""))
                                try:
                                    lance, info = escolher_lance(board, motor, chave_perfil, relogio_vez, caminho_book,
                                                                 tempo_provisorio_s, folga_watchdog_s, economia)
                                except Exception as erro:
                                    saida(f"Erro ao escolher o lance ({type(erro).__name__}: {erro}).")
                                    motor = _reiniciar_motor(motor, reabrir_motor, saida)
                                else:
                                    if info["motor_caiu"]:
                                        saida("O motor travou ou caiu. Reiniciando.")
                                        motor = _reiniciar_motor(motor, reabrir_motor, saida)
                            if lance is None:
                                manual = True
                                saida("MODO MANUAL: o motor não está disponível. "
                                      "Digite o lance que NÓS vamos jogar (UCI).")
                                lance = ler_lance(board, ao_sincronizar, entrada, saida)
                                if lance is not None:
                                    info = {"book": False, "profundidade": 0, "nos": 0, "avaliacao": "-",
                                            "pv": [lance], "tempo_s": 0.0}
                                else:  # desfazer/fen: o tabuleiro mudou, espera o 'go'
                                    esperando_go = board.turn == minha_cor
                            if lance is not None:
                                numero = board.fullmove_number
                                saida(f">>> JOGUE: {lance.uci()}   (lance {numero}, {cor_texto}"
                                      + ("" if manual else f", prof {info['profundidade']}, aval {info['avaliacao']}, "
                                         f"{info['tempo_s']:.1f} s{', book' if info['book'] else ''}") + ")")
                                log.registrar_lance(arquivo_log, numero, cor_texto, lance, info["profundidade"],
                                                    info["nos"], info["avaliacao"], info["pv"], info["tempo_s"],
                                                    book=info["book"])
                                board.push(lance)
                                aval = info["avaliacao"]
                                historico_aval.append((len(board.move_stack) - 1,
                                                       round(aval * 100) if (_numero_finito(aval) and not info["book"] and info["profundidade"] > 0) else None))
                                # gasto real desta vez (nunca menos do que o motor declarou) + atraso humano - incremento
                                gasto = max(info["tempo_s"], agora() - inicio_da_vez)
                                relogio["restante_s"] = max(0.0, relogio["restante_s"] - gasto
                                                            - relogio["atraso_humano_s"] + relogio["incremento_s"])
                                nossos_lances += 1
                                if relogio["restante_s"] <= 0:
                                    saida("ATENÇÃO: relógio estimado em 0:00. Peça ao conferente o tempo real "
                                          "e digite t mm:ss.")
                    else:
                        # --- vez do adversário ---
                        lance = ler_lance(board, ao_sincronizar, entrada, saida)
                        if lance is None:
                            esperando_go = board.turn == minha_cor
                        else:
                            board.push(lance)
                            esperando_go = False
                            inicio_da_vez = agora()  # agora o nosso relógio corre
                    salvar_pgn(board, caminho_pgn, cabecalhos)
                    erros_seguidos = 0
                except EOFError:
                    raise
                except Exception as erro:
                    erros_seguidos += 1
                    saida(f"Erro inesperado ({type(erro).__name__}: {erro}). A partida continua.")
                    if erros_seguidos >= 10:
                        raise  # 10 erros seguidos: algo está quebrado de verdade, não adianta girar
            resultado = board.result()
            saida(f"Fim da partida: {resultado} ({board.outcome().termination.name}). "
                  f"Se foi erro de digitação, digite 'desfazer'. Enter para encerrar.")
            try:
                resposta = entrada("fim> ").strip().lower()
            except (EOFError, KeyboardInterrupt):
                break
            if resposta == "desfazer" and board.move_stack:
                board.pop()
                esperando_go = board.turn == minha_cor
                salvar_pgn(board, caminho_pgn, cabecalhos)
                continue
            break
        return resultado
    finally:
        salvar_pgn(board, caminho_pgn, cabecalhos)
        if arquivo_log is not None:
            arquivo_log.close()
        if motor is not None:
            try:
                motor.quit()
            except Exception:
                pass


def main(entrada=input, saida=print):
    """Pergunta cor e perfil de tempo; laço da partida com try/except e reinício do motor se cair.

    Devolve o código de saída: 0 = partida terminou, 1 = teclado fechado no meio, 2 = não
    dá para começar (falta Stockfish ou tempo.py). Falhar na largada é de propósito: é bem
    melhor descobrir agora do que no meio da partida.
    """
    caminho_stockfish = _achar_stockfish()
    if caminho_stockfish is None:
        saida(f"Stockfish não encontrado em {PASTA_STOCKFISH}/. Veja o README (como instalar).")
        return 2

    try:
        cor = _perguntar_cor(entrada, saida)
        chave_perfil = _perguntar_perfil(entrada, saida, cor)
        atraso = _perguntar_atraso(entrada, saida)
    except (EOFError, KeyboardInterrupt):
        saida("Entrada encerrada antes de começar a partida.")
        return 1
    inicio_s, incremento_s = tempo.PERFIS[chave_perfil]
    relogio = {"restante_s": float(inicio_s), "incremento_s": float(incremento_s), "atraso_humano_s": atraso}

    tempo_provisorio_s = _numero_do_ambiente("CAPABLANCA_TEMPO_PROVISORIO_S")
    folga_watchdog_s = _numero_do_ambiente("CAPABLANCA_FOLGA_WATCHDOG_S")
    try:
        tempo.calcular_tempo(relogio["restante_s"], relogio["incremento_s"], 1, atraso)
    except NotImplementedError:
        if tempo_provisorio_s is None:
            saida("tempo.py ainda não está implementado (Marcos). Para TESTAR, defina a variável "
                  "CAPABLANCA_TEMPO_PROVISORIO_S (segundos por lance). Isso NÃO vale para o torneio.")
            return 2
        saida(f"*** MODO TESTE: tempo provisório de {tempo_provisorio_s} s por lance. NÃO USAR NO TORNEIO. ***")
    except Exception:
        pass  # bug no tempo.py: cada lance cai no modo de emergência, mas a partida abre

    saida("Dica: se o motor travar no torneio, o programa o reinicia sozinho.")
    if folga_watchdog_s is None:
        saida("AVISO: watchdog desligado (defina CAPABLANCA_FOLGA_WATCHDOG_S quando o grupo decidir a folga).")

    book_ok = CAMINHO_BOOK if os.path.isfile(CAMINHO_BOOK) else None
    if book_ok is None:
        saida(f"Aviso: book não encontrado em {CAMINHO_BOOK}. Jogando sem book.")

    def reabrir():
        return abrir_motor(caminho_stockfish, THREADS, HASH_MB, PASTA_TABLEBASES)

    try:
        motor = reabrir()
    except Exception as erro:
        saida(f"Não consegui abrir o Stockfish ({type(erro).__name__}: {erro}).")
        return 2
    try:
        jogar_partida(cor, chave_perfil, relogio, motor, entrada, saida, PASTA_PARTIDAS, book_ok,
                      tempo_provisorio_s, folga_watchdog_s, reabrir)
    except EOFError:
        saida("Entrada encerrada. Log e PGN foram salvos em partidas/.")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
