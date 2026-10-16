"""Programa que fica aberto na mesa. Dono: Junio.

Liga tudo: lê o lance adversário (UCI), valida, consulta book.py, usa tempo.py,
chama o Stockfish (chess.engine) e grava o log. Robustez acima de tudo:
nenhum erro pode fechar o programa e o estado deve ficar igual ao tabuleiro físico.
"""
import chess
import chess.engine


def abrir_motor(caminho_stockfish, threads, hash_mb, syzygy_path):
    """popen_uci + configuração de Threads, Hash e SyzygyPath."""
    raise NotImplementedError


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


def escolher_lance(board, motor, perfil, relogio):
    """book -> tempo -> Stockfish (analysis, parada em tempo real) -> devolve (lance, info)."""
    raise NotImplementedError


def salvar_pgn(board, caminho):
    """Salva a partida em PGN a cada lance."""
    raise NotImplementedError


def main():
    """Pergunta cor e perfil de tempo; laço da partida com try/except e reinício do motor se cair."""
    raise NotImplementedError


if __name__ == "__main__":
    main()
