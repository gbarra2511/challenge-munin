"""State machine pura de SwapRequest — transições válidas/inválidas/terminais."""

from __future__ import annotations

import pytest

from app.domain.swap import (
    InvalidSwapTransition,
    SwapStatus,
    assert_transition,
    can_transition,
    is_terminal,
)

VALID = [
    (SwapStatus.PENDING, SwapStatus.APPROVED),
    (SwapStatus.PENDING, SwapStatus.REJECTED),
    (SwapStatus.PENDING, SwapStatus.CANCELLED),
]

INVALID = [
    (SwapStatus.APPROVED, SwapStatus.REJECTED),
    (SwapStatus.REJECTED, SwapStatus.APPROVED),
    (SwapStatus.CANCELLED, SwapStatus.PENDING),
    (SwapStatus.APPROVED, SwapStatus.APPROVED),  # re-aprovar não é transição válida
    (SwapStatus.PENDING, SwapStatus.PENDING),
]


@pytest.mark.parametrize(("src", "dst"), VALID)
def test_valid_transitions(src, dst) -> None:
    assert can_transition(src, dst)
    assert_transition(src, dst)  # não levanta


@pytest.mark.parametrize(("src", "dst"), INVALID)
def test_invalid_transitions(src, dst) -> None:
    assert not can_transition(src, dst)
    with pytest.raises(InvalidSwapTransition):
        assert_transition(src, dst)


@pytest.mark.parametrize(
    "status", [SwapStatus.APPROVED, SwapStatus.REJECTED, SwapStatus.CANCELLED]
)
def test_terminal_states_have_no_exit(status) -> None:
    assert is_terminal(status)
    for dst in SwapStatus:
        assert not can_transition(status, dst)


def test_pending_is_not_terminal() -> None:
    assert not is_terminal(SwapStatus.PENDING)
