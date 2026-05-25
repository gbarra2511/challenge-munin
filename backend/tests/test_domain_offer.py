"""Testes da state machine pura do ShiftOffer.

Sem banco, sem clock — só lógica de transição. Espelha PLANO §5.
"""

from __future__ import annotations

import pytest

from app.domain.offer import (
    TERMINAL_STATES,
    InvalidOfferTransition,
    OfferStatus,
    assert_transition,
    can_transition,
    is_terminal,
)

VALID = [
    (OfferStatus.PENDING, OfferStatus.ACCEPTED),
    (OfferStatus.PENDING, OfferStatus.DECLINED),
    (OfferStatus.PENDING, OfferStatus.EXPIRED),
    (OfferStatus.PENDING, OfferStatus.SUPERSEDED),
]


INVALID = [
    (OfferStatus.ACCEPTED, OfferStatus.DECLINED),  # terminal
    (OfferStatus.DECLINED, OfferStatus.PENDING),  # não volta
    (OfferStatus.EXPIRED, OfferStatus.ACCEPTED),  # terminal
    (OfferStatus.SUPERSEDED, OfferStatus.PENDING),  # terminal
    (OfferStatus.PENDING, OfferStatus.PENDING),  # sem self-loop
]


class TestOfferStateMachine:
    @pytest.mark.parametrize("current,target", VALID)
    def test_valid_transitions_pass(self, current: OfferStatus, target: OfferStatus) -> None:
        assert can_transition(current, target)
        assert_transition(current, target)  # não levanta

    @pytest.mark.parametrize("current,target", INVALID)
    def test_invalid_transitions_blocked(self, current: OfferStatus, target: OfferStatus) -> None:
        assert not can_transition(current, target)
        with pytest.raises(InvalidOfferTransition) as exc_info:
            assert_transition(current, target)
        assert exc_info.value.current is current
        assert exc_info.value.target is target

    @pytest.mark.parametrize(
        "status,terminal",
        [
            (OfferStatus.ACCEPTED, True),
            (OfferStatus.DECLINED, True),
            (OfferStatus.EXPIRED, True),
            (OfferStatus.SUPERSEDED, True),
            (OfferStatus.PENDING, False),
        ],
    )
    def test_is_terminal(self, status: OfferStatus, terminal: bool) -> None:
        assert is_terminal(status) is terminal

    def test_terminals_have_no_outgoing(self) -> None:
        for terminal in TERMINAL_STATES:
            for target in OfferStatus:
                assert not can_transition(terminal, target), (
                    f"Terminal {terminal} não deveria transicionar para {target}"
                )

    def test_only_pending_has_outgoing(self) -> None:
        # Toda transição válida parte de PENDING — não há grafo cíclico.
        for status in OfferStatus:
            has_outgoing = any(can_transition(status, t) for t in OfferStatus)
            assert has_outgoing == (status is OfferStatus.PENDING)
