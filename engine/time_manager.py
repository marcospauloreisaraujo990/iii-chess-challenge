"""
Gestão de tempo própria (Clock Budget).

Responsável: Junio
Sprint 2 · Card "Gestão de Tempo Própria (Clock Budget)" · Epic 2 (Controle) · 4 pontos
Sprint 3 · parte do card "Ligar comandos de emergência na mesa" (comando  t mm:ss)

O que este módulo entrega (CONTRATO)
------------------------------------
    compute_time_budget(remaining_s, increment_s, move_number) -> float
        Tempo MÁXIMO, em segundos, para pensar neste lance. O main.py passa esse
        valor para search.search(board, time_limit_s=...).

    Clock
        Relógio virtual da equipe: desconta o que gastamos, soma o incremento e
        aceita sincronizar com o relógio físico (comando  t mm:ss  na mesa).

    parse_clock("12:34") -> 754.0      format_clock(754) -> "12:34"

Pontos de atenção
-----------------
    - O relógio físico continua correndo enquanto anunciamos o lance, o adversário
      repete, a peça é movida e o relógio é apertado. Esse atraso humano
      (HUMAN_DELAY_S) precisa sair do orçamento. Medir nos treinos.
    - Nunca planejar gastar o relógio inteiro: deixar uma reserva (SAFETY_RESERVE_S).

Checklist dos cards
-------------------
    [ ] Receber do CLI o tempo restante (ex.: 900 s) e o incremento (ex.: 10 s).
    [ ] compute_time_budget(): calcular o tempo máximo deste lance.
    [ ] Passar esse tempo para search() (a busca para quando o limite chega).
    [ ] (Sprint 3) Clock.sync() + parse_clock() para o comando  t mm:ss.
    [ ] Testes em tests/test_time_manager.py.
"""

from dataclasses import dataclass

# Controle de tempo do torneio: 15 min + 10 s por lance.
DEFAULT_INITIAL_S = 15 * 60
DEFAULT_INCREMENT_S = 10

# Valores iniciais: AJUSTAR com o que for medido nos treinos.
HUMAN_DELAY_S = 4.0       # anunciar + adversário repetir + mover + apertar o relógio
SAFETY_RESERVE_S = 10.0   # parte do relógio que nunca planejamos gastar


def compute_time_budget(remaining_s: float, increment_s: float, move_number: int) -> float:
    """Tempo máximo (s) para pensar neste lance."""
    raise NotImplementedError("time_manager.compute_time_budget() — Sprint 2, card do Junio")


@dataclass
class Clock:
    """Relógio virtual da equipe (o físico é a referência; sincronize com sync())."""
    remaining_s: float = DEFAULT_INITIAL_S
    increment_s: float = DEFAULT_INCREMENT_S

    def spend(self, elapsed_s: float) -> None:
        """Desconta o tempo gasto no lance (+ atraso humano) e soma o incremento."""
        raise NotImplementedError("Clock.spend() — Sprint 2, card do Junio")

    def sync(self, remaining_s: float) -> None:
        """Acerta o relógio pelo físico (comando  t mm:ss)."""
        raise NotImplementedError("Clock.sync() — Sprint 3, card do Junio")


def parse_clock(text: str) -> float:
    """'12:34' -> 754.0. Levanta ValueError se o texto for inválido."""
    raise NotImplementedError("time_manager.parse_clock() — Sprint 3, card do Junio")


def format_clock(seconds: float) -> str:
    """754 -> '12:34'."""
    raise NotImplementedError("time_manager.format_clock() — Sprint 3, card do Junio")
