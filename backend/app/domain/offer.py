"""Pure state machine for ShiftOffer status transitions.

Pure means: no I/O, no DB, no clock. Ver PLANO.md §5 (Oferta individual).
"""

from __future__ import annotations

from enum import StrEnum


class OfferStatus(StrEnum):
    PENDING = "pending"
    ACCEPTED = "accepted"
    DECLINED = "declined"
    EXPIRED = "expired"
    SUPERSEDED = "superseded"


# Toda transição de saída de pending leva a um estado terminal.
TERMINAL_STATES: frozenset[OfferStatus] = frozenset(
    {
        OfferStatus.ACCEPTED,
        OfferStatus.DECLINED,
        OfferStatus.EXPIRED,
        OfferStatus.SUPERSEDED,
    }
)


# PLANO §5: pending → {accepted, declined, expired, superseded}.
_VALID_TRANSITIONS: frozenset[tuple[OfferStatus, OfferStatus]] = frozenset(
    {
        (OfferStatus.PENDING, OfferStatus.ACCEPTED),
        (OfferStatus.PENDING, OfferStatus.DECLINED),
        (OfferStatus.PENDING, OfferStatus.EXPIRED),
        (OfferStatus.PENDING, OfferStatus.SUPERSEDED),
    }
)


class InvalidOfferTransition(Exception):
    def __init__(self, current: OfferStatus, target: OfferStatus) -> None:
        super().__init__(f"Transição de Offer inválida: {current.value} → {target.value}")
        self.current = current
        self.target = target


def can_transition(current: OfferStatus, target: OfferStatus) -> bool:
    return (current, target) in _VALID_TRANSITIONS


def assert_transition(current: OfferStatus, target: OfferStatus) -> None:
    if not can_transition(current, target):
        raise InvalidOfferTransition(current, target)


def is_terminal(status: OfferStatus) -> bool:
    return status in TERMINAL_STATES
