"""
Log da partida para a banca.

Responsável: Junio
Sprint 1 · Card "CLI Principal, Entradas e Sistema de Logs" · Epic 1 (Interface e Regras) · 4 pontos

REGRA
-----
A cada lance NOSSO, uma linha no arquivo com os 8 campos, nesta ordem:

    número do lance | cor | lance | depth | nós | avaliação | PV | tempo

(Conferir no FAQ os nomes e o formato exatos antes do evento.)

Sugestão de linha (é o formato que tests/test_logger.py confere):
    numero_lance=12 | cor=Brancas | lance=g1f3 | depth=6 | nos=184503 | avaliacao=+35 | pv=g1f3 d7d5 c2c4 | tempo=14.23

O que este módulo entrega (CONTRATO)
------------------------------------
    start_game_log(our_color, time_control, log_dir=LOG_DIR) -> Path
        Cria logs/partida_AAAAMMDD_HHMMSS_<cor>.txt com um cabeçalho e devolve o caminho.

    log_move(move_number, color, move_uci, depth, nodes, score, pv, time_s) -> str
        Grava a linha dos 8 campos e devolve a linha gravada.

    log_event(text) -> None
        Linha extra começando com "#": lance do adversário, correção, erro tratado...

Pontos de atenção
-----------------
    - Gravar e forçar para o disco a cada lance (flush + os.fsync): se o notebook
      desligar, o log até ali fica salvo.
    - Erro ao gravar NUNCA pode derrubar a partida: avisa na tela e segue.

Checklist do card (parte do log)
--------------------------------
    [ ] start_game_log(), log_move() e log_event().
    [ ] Testes em tests/test_logger.py (8 campos, na ordem).
"""

from pathlib import Path
from typing import List, Optional, Union

import chess

# Os 8 campos obrigatórios, na ordem.
FIELDS = ("numero_lance", "cor", "lance", "depth", "nos", "avaliacao", "pv", "tempo")

ROOT = Path(__file__).resolve().parent.parent
LOG_DIR = ROOT / "logs"


def start_game_log(our_color: str, time_control: str,
                   log_dir: Union[str, Path] = LOG_DIR) -> Path:
    """Cria o arquivo de log da partida e escreve o cabeçalho."""
    raise NotImplementedError("logger.start_game_log() — Sprint 1, card do Junio")


def log_move(move_number: int, color: str, move_uci: str, depth: int, nodes: int,
             score: Optional[int], pv: List[chess.Move], time_s: float) -> str:
    """Grava a linha com os 8 campos do lance nosso. Devolve a linha gravada."""
    raise NotImplementedError("logger.log_move() — Sprint 1, card do Junio")


def log_event(text: str) -> None:
    """Grava uma linha extra de informação (começa com '#')."""
    raise NotImplementedError("logger.log_event() — Sprint 1, card do Junio")
