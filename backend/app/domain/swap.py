"""Pure state machine for SwapRequest status transitions.

Pure means: no I/O, no DB, no clock. Espelha `domain/shift.py` e `domain/offer.py`.

Fluxo (handoff): o médico A pede para passar um plantão aceito a um colega B;
a coordenação aprova ou recusa. A pode desistir enquanto pendente.

    pending → approved   (coordenação aprova; transferência atômica A→B)
    pending → rejected   (coordenação recusa, com motivo)
    pending → cancelled  (médico A desiste)
"""

from __future__ import annotations

from enum import StrEnum


class SwapStatus(StrEnum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    CANCELLED = "cancelled"


# Toda transição de saída de pending leva a um estado terminal.
TERMINAL_STATES: frozenset[SwapStatus] = frozenset(
    {SwapStatus.APPROVED, SwapStatus.REJECTED, SwapStatus.CANCELLED}
)


_VALID_TRANSITIONS: frozenset[tuple[SwapStatus, SwapStatus]] = frozenset(
    {
        (SwapStatus.PENDING, SwapStatus.APPROVED),
        (SwapStatus.PENDING, SwapStatus.REJECTED),
        (SwapStatus.PENDING, SwapStatus.CANCELLED),
    }
)


class InvalidSwapTransition(Exception):
    def __init__(self, current: SwapStatus, target: SwapStatus) -> None:
        super().__init__(f"Transição de Swap inválida: {current.value} → {target.value}")
        self.current = current
        self.target = target


def can_transition(current: SwapStatus, target: SwapStatus) -> bool:
    return (current, target) in _VALID_TRANSITIONS


def assert_transition(current: SwapStatus, target: SwapStatus) -> None:
    if not can_transition(current, target):
        raise InvalidSwapTransition(current, target)


def is_terminal(status: SwapStatus) -> bool:
    return status in TERMINAL_STATES
