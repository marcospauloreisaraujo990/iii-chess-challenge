"""Programa que fica aberto na mesa. Dono: Junio.

Liga tudo: lê o lance adversário (UCI), valida, consulta book.py, usa tempo.py,
chama o Stockfish (chess.engine) e grava o log. Robustez acima de tudo:
nenhum erro pode fechar o programa e o estado deve ficar igual ao tabuleiro físico.
"""
import math
import os
import sys
import threading
import time

import chess
import chess.engine
import chess.pgn

import book
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
    """'KQRvKR.rtbw' -> 6. Conta as letras das peças (tudo menos o 'v' e a extensão)."""
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
        opcoes = {"Threads": threads, "Hash": hash_mb}
        if syzygy_path:
            pastas = [p for p in syzygy_path.split(os.pathsep) if p]
            existentes = [p for p in pastas if os.path.isdir(p)]
            for ausente in set(pastas) - set(existentes):
                print(f"[motor] AVISO: pasta de tablebases não existe: {ausente}", file=sys.stderr)
            if existentes:
                opcoes["SyzygyPath"] = os.pathsep.join(existentes)
                opcoes["SyzygyProbeLimit"] = MAX_PECAS_TABLEBASE
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

    Tipos: "lance" (valor = chess.Move), "desfazer", "tab", "fen" (valor = texto do FEN),
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


def ler_lance(board, ao_sincronizar=None, entrada=input, saida=print):
    """Lê texto, valida com chess.Move.from_uci e board.legal_moves; entrada ruim só pede de novo.

    Comandos: desfazer | tab | fen <posição> | t mm:ss

    Devolve:
      - um chess.Move legal, quando o operador digitou um lance;
      - None, quando o tabuleiro mudou por comando (desfazer ou fen): quem chamou
        precisa reler de quem é a vez antes de continuar.
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
    e um valor estranho nunca chega ao relógio.
    """
    try:
        import tempo
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
    if isinstance(segundos, bool) or not isinstance(segundos, int) or segundos <= 0:
        saida("Tempo inválido. Use t mm:ss (exemplo: t 12:34). O relógio não foi alterado.")
        return
    if ao_sincronizar is None:
        saida(f"Tempo lido ({segundos} s), mas nenhum relógio está ligado: nada foi ajustado.")
        return
    try:
        ao_sincronizar(segundos)
    except Exception as erro:
        saida(f"Erro ao ajustar o relógio ({type(erro).__name__}). O relógio não foi alterado.")
        return
    saida(f"Relógio ajustado para {segundos} s.")


def _avaliacao_para_log(score):
    """Placar do motor -> +0.35 (peões) ou "#3" (mate), do ponto de vista de quem joga."""
    mate = score.mate()
    if mate is not None:
        return f"#{mate}"
    return score.score() / 100


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
    maximo = min(maximo, restante)  # nunca pensar mais do que o relógio tem
    return min(alvo, maximo), maximo


def escolher_lance(board, motor, perfil, relogio, caminho_book=None, tempo_provisorio_s=None,
                   folga_watchdog_s=None):
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


def main():
    """Pergunta cor e perfil de tempo; laço da partida com try/except e reinício do motor se cair."""
    raise NotImplementedError


if __name__ == "__main__":
    main()
