#!/usr/bin/env python3
"""
Partidas de teste: nosso bot × Stockfish limitado.

Responsável: Léo
Sprint 3 · Card "Testes automatizados vs Stockfish Nível 1" · Epic 3 (Validação) · 3 pontos

O Stockfish aqui é só ADVERSÁRIO DE TREINO: não faz parte do nosso motor nem da
entrega. O executável fica em assets/stockfish/ (ver LEIA.txt) e é aberto com
chess.engine.SimpleEngine.popen_uci().

Checklist do card
-----------------
    [ ] Jogar N partidas: nosso search() × Stockfish limitado
        (ex.: chess.engine.Limit(depth=1) ou opção "Skill Level" baixa).
    [ ] Simular o relógio 15+10 descontando o tempo real de cada lance.
    [ ] Métricas: o bot trava? faz lance ilegal? estoura os 15 minutos? resultado.
    [ ] Salvar o resumo em tests/resultados/.

Uso (quando estiver pronto):
    python tests/simulate_match.py --partidas 10
"""

import argparse
import os
import sys
from typing import List, Optional

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Nosso bot × Stockfish limitado.")
    parser.add_argument("--partidas", type=int, default=10)
    parser.add_argument("--stockfish", help="caminho do executável (padrão: assets/stockfish/)")
    parser.parse_args(argv)
    print("simulate_match.py: ainda não implementado (Sprint 3, card do Léo).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
