"""
Tablebases de finais (Syzygy) — até 5 peças.

Responsável: Léo
Sprint 2 · Card "Integração de Tablebases (Finais)" · Epic 2 (Regras) · 3 pontos

REGRA (FAQ, item 4)
-------------------
Só tablebases de ATÉ 5 peças (contando os reis). Nunca coloque arquivos de 6 ou 7
peças em assets/syzygy/.

O que este módulo entrega (CONTRATO)
------------------------------------
    open_tablebase(path=DEFAULT_SYZYGY_PATH) -> bool
        Abre as tabelas uma vez, no início do programa. False se não houver tabelas.

    probe_wdl(board) -> int ou None
        Resultado teórico para quem joga: 2 vitória, 0 empate, -2 derrota
        (1 / -1: vitória ou derrota anulada pela regra dos 50 lances).
        None com mais de 5 peças, sem tabelas abertas ou em caso de erro.
        Uso: dentro da busca (search.py), para cortar a árvore na hora.

    best_move(board) -> chess.Move ou None
        Melhor lance segundo a tablebase. Uso: na raiz, pelo main.py.

    close() -> None

Checklist do card
-----------------
    [ ] Baixar Syzygy de 3, 4 e 5 peças (.rtbw e .rtbz) para assets/syzygy/.
    [ ] Conectar com chess.syzygy.open_tablebase().
    [ ] Com 5 peças ou menos, devolver o resultado na hora em vez de calcular.
    [ ] Testes em tests/test_syzygy.py.
"""

from pathlib import Path
from typing import Optional, Union

import chess

MAX_PIECES = 5   # FAQ 4

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_SYZYGY_PATH = ROOT / "assets" / "syzygy"


def open_tablebase(path: Union[str, Path] = DEFAULT_SYZYGY_PATH) -> bool:
    """Abre as tabelas da pasta. True se abriu alguma."""
    raise NotImplementedError("syzygy.open_tablebase() — Sprint 2, card do Léo")


def probe_wdl(board: chess.Board) -> Optional[int]:
    """Vitória/empate/derrota teórico para quem joga, ou None."""
    raise NotImplementedError("syzygy.probe_wdl() — Sprint 2, card do Léo")


def best_move(board: chess.Board) -> Optional[chess.Move]:
    """Melhor lance pela tablebase, ou None."""
    raise NotImplementedError("syzygy.best_move() — Sprint 2, card do Léo")


def close() -> None:
    """Fecha as tabelas abertas (se houver)."""
    raise NotImplementedError("syzygy.close() — Sprint 2, card do Léo")
