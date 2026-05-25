"""Pure state machine for Shift status transitions.

Pure means: no I/O, no DB, no clock. Só lógica de estado. Testável em
microssegundos. Ver PLANO.md §5 para o diagrama original.
"""

from __future__ import annotations

from enum import StrEnum


class ShiftStatus(StrEnum):
    OPEN = "open"
    OFFERING = "offering"
    ACCEPTED = "accepted"
    CONFIRMED = "confirmed"
    NEEDS_ATTENTION = "needs_attention"
    CANCELLED = "cancelled"


# Estados terminais: não há transição de saída.
TERMINAL_STATES: frozenset[ShiftStatus] = frozenset({ShiftStatus.CONFIRMED, ShiftStatus.CANCELLED})


# Pares (origem, destino) válidos. Tudo o que não está aqui é proibido.
# Fonte: PLANO.md §5 diagrama. Adicionar transições requer atualizar o plano.
_VALID_TRANSITIONS: frozenset[tuple[ShiftStatus, ShiftStatus]] = frozenset(
    {
        (ShiftStatus.OPEN, ShiftStatus.OFFERING),
        (ShiftStatus.OFFERING, ShiftStatus.OFFERING),  # tick avança batch
        (ShiftStatus.OFFERING, ShiftStatus.ACCEPTED),
        (ShiftStatus.OFFERING, ShiftStatus.NEEDS_ATTENTION),
        (ShiftStatus.OFFERING, ShiftStatus.CANCELLED),
        (ShiftStatus.NEEDS_ATTENTION, ShiftStatus.OFFERING),
        (ShiftStatus.NEEDS_ATTENTION, ShiftStatus.CANCELLED),
        (ShiftStatus.ACCEPTED, ShiftStatus.CONFIRMED),
        (ShiftStatus.ACCEPTED, ShiftStatus.CANCELLED),
    }
)


class InvalidShiftTransition(Exception):
    def __init__(self, current: ShiftStatus, target: ShiftStatus) -> None:
        super().__init__(f"Transição de Shift inválida: {current.value} → {target.value}")
        self.current = current
        self.target = target


def can_transition(current: ShiftStatus, target: ShiftStatus) -> bool:
    return (current, target) in _VALID_TRANSITIONS


def assert_transition(current: ShiftStatus, target: ShiftStatus) -> None:
    if not can_transition(current, target):
        raise InvalidShiftTransition(current, target)


def is_terminal(status: ShiftStatus) -> bool:
    return status in TERMINAL_STATES
