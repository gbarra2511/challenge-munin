"""Testes da state machine pura do Shift.

Sem banco, sem clock — só lógica de transição. Espelha PLANO §5.
"""

from __future__ import annotations

import pytest

from app.domain.shift import (
    TERMINAL_STATES,
    InvalidShiftTransition,
    ShiftStatus,
    assert_transition,
    can_transition,
    is_terminal,
)

VALID = [
    (ShiftStatus.OPEN, ShiftStatus.OFFERING),
    (ShiftStatus.OFFERING, ShiftStatus.OFFERING),
    (ShiftStatus.OFFERING, ShiftStatus.ACCEPTED),
    (ShiftStatus.OFFERING, ShiftStatus.NEEDS_ATTENTION),
    (ShiftStatus.NEEDS_ATTENTION, ShiftStatus.OFFERING),
    (ShiftStatus.NEEDS_ATTENTION, ShiftStatus.CANCELLED),
    (ShiftStatus.ACCEPTED, ShiftStatus.CONFIRMED),
    (ShiftStatus.ACCEPTED, ShiftStatus.CANCELLED),
]


# Casos representativos do que NÃO pode acontecer (não cobre todos os 36 pares
# inválidos — pra isso ver test_terminals_have_no_outgoing).
INVALID = [
    (ShiftStatus.OPEN, ShiftStatus.ACCEPTED),  # pula offering
    (ShiftStatus.OPEN, ShiftStatus.CANCELLED),  # §5 não permite
    (ShiftStatus.OFFERING, ShiftStatus.OPEN),  # não volta
    (ShiftStatus.OFFERING, ShiftStatus.CONFIRMED),  # confirmed só vem de accepted
    (ShiftStatus.NEEDS_ATTENTION, ShiftStatus.ACCEPTED),  # §5 não permite
    (ShiftStatus.ACCEPTED, ShiftStatus.OFFERING),  # não volta
]


class TestShiftStateMachine:
    @pytest.mark.parametrize("current,target", VALID)
    def test_valid_transitions_pass(self, current: ShiftStatus, target: ShiftStatus) -> None:
        assert can_transition(current, target)
        assert_transition(current, target)  # não levanta

    @pytest.mark.parametrize("current,target", INVALID)
    def test_invalid_transitions_blocked(self, current: ShiftStatus, target: ShiftStatus) -> None:
        assert not can_transition(current, target)
        with pytest.raises(InvalidShiftTransition) as exc_info:
            assert_transition(current, target)
        assert exc_info.value.current is current
        assert exc_info.value.target is target

    @pytest.mark.parametrize(
        "status,terminal",
        [
            (ShiftStatus.CANCELLED, True),
            (ShiftStatus.CONFIRMED, True),
            (ShiftStatus.OPEN, False),
            (ShiftStatus.OFFERING, False),
            (ShiftStatus.ACCEPTED, False),
            (ShiftStatus.NEEDS_ATTENTION, False),
        ],
    )
    def test_is_terminal(self, status: ShiftStatus, terminal: bool) -> None:
        assert is_terminal(status) is terminal

    def test_terminals_have_no_outgoing(self) -> None:
        # Defesa contra adicionar acidentalmente saída de terminal.
        for terminal in TERMINAL_STATES:
            for target in ShiftStatus:
                assert not can_transition(terminal, target), (
                    f"Terminal {terminal} não deveria transicionar para {target}"
                )

    def test_self_loop_only_for_offering(self) -> None:
        # offering → offering é a única auto-transição (tick avança batch).
        for status in ShiftStatus:
            expected = status is ShiftStatus.OFFERING
            assert can_transition(status, status) is expected
