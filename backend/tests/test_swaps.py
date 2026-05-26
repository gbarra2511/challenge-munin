"""Serviço de swap: pedido, aprovação (transferência atômica), recusa, cancelamento.

Usa o fixture `session` (isolamento por savepoint). A concorrência real de duas
aprovações vive em test_swap_concurrency.py.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import func, select, update

from app.api.errors import Conflict, NotFound, UnprocessableEntity
from app.infra.hashing import hash_password
from app.models import (
    Account,
    DoctorUnavailability,
    Hospital,
    ShiftAssignment,
    SwapRequest,
)
from app.services.swaps import (
    approve_swap,
    cancel_swap,
    reject_swap,
    request_swap,
    swap_candidates,
)
from tests.conftest import seed_doctor, seed_shift


def _setup(session):
    """Hospital + coordenação + médico A (assignment ATIVA num shift accepted)
    + colega B elegível. Retorna (hospital, A, B, shift, assignment, coord)."""
    h = Hospital(name="Hospital Central")
    session.add(h)
    session.flush()
    coord = Account(
        email="coord@central.test",
        password_hash=hash_password("x"),
        role="coordenador",
        hospital_id=h.id,
    )
    session.add(coord)
    a = seed_doctor(session, name="Dra. A", email="a@central.test", specialty_ids=[1],
                    hospital_ids=[h.id])
    b = seed_doctor(session, name="Dr. B", email="b@central.test", specialty_ids=[1],
                    hospital_ids=[h.id])
    now = datetime.now(UTC)
    shift = seed_shift(session, hospital_id=h.id, starts_at=now + timedelta(days=5),
                       ends_at=now + timedelta(days=5, hours=8), specialty_id=1,
                       status="accepted", current_batch=1)
    assignment = ShiftAssignment(shift_id=shift.id, doctor_id=a.id, status="active",
                                 accepted_at=now)
    session.add(assignment)
    session.commit()
    return h, a, b, shift, assignment, coord


# --- pedido ----------------------------------------------------------------


def test_request_swap_happy(session) -> None:
    _h, a, b, _shift, assignment, _c = _setup(session)
    res = request_swap(session, doctor_id=a.id, assignment_id=assignment.id, to_doctor_id=b.id)
    assert res["status"] == "pending"
    swap = session.scalar(select(SwapRequest).where(SwapRequest.id == uuid.UUID(res["id"])))
    assert swap.to_doctor_id == b.id


def test_request_swap_to_self_is_422(session) -> None:
    _h, a, _b, _shift, assignment, _c = _setup(session)
    with pytest.raises(UnprocessableEntity):
        request_swap(session, doctor_id=a.id, assignment_id=assignment.id, to_doctor_id=a.id)


def test_request_swap_not_owner_is_404(session) -> None:
    _h, a, b, _shift, assignment, _c = _setup(session)
    # B tenta pedir troca de uma assignment que é de A (alvo distinto p/ não cair no self-swap).
    with pytest.raises(NotFound):
        request_swap(session, doctor_id=b.id, assignment_id=assignment.id, to_doctor_id=a.id)


def test_request_swap_assignment_not_active_is_409(session) -> None:
    _h, a, b, _shift, assignment, _c = _setup(session)
    session.execute(
        update(ShiftAssignment)
        .where(ShiftAssignment.id == assignment.id)
        .values(status="cancelled")
    )
    session.commit()
    with pytest.raises(Conflict):
        request_swap(session, doctor_id=a.id, assignment_id=assignment.id, to_doctor_id=b.id)


def test_request_swap_target_ineligible_is_422(session) -> None:
    _h, a, _b, _shift, assignment, _c = _setup(session)
    # médico desconhecido (não afiliado) como alvo
    with pytest.raises(UnprocessableEntity):
        request_swap(
            session, doctor_id=a.id, assignment_id=assignment.id, to_doctor_id=uuid.uuid4()
        )


def test_request_swap_duplicate_pending_is_409(session) -> None:
    _h, a, b, _shift, assignment, _c = _setup(session)
    request_swap(session, doctor_id=a.id, assignment_id=assignment.id, to_doctor_id=b.id)
    with pytest.raises(Conflict):
        request_swap(session, doctor_id=a.id, assignment_id=assignment.id, to_doctor_id=b.id)


# --- candidatos -------------------------------------------------------------


def test_swap_candidates_lists_eligible_excluding_self(session) -> None:
    _h, a, b, _shift, assignment, _c = _setup(session)
    cands = swap_candidates(session, assignment_id=assignment.id, doctor_id=a.id)
    ids = {c["doctor"]["id"] for c in cands}
    assert str(b.id) in ids
    assert str(a.id) not in ids


# --- aprovação (transferência atômica) -------------------------------------


def test_approve_swap_transfers_assignment(session) -> None:
    h, a, b, shift, assignment, coord = _setup(session)
    res = request_swap(session, doctor_id=a.id, assignment_id=assignment.id, to_doctor_id=b.id)
    approve_swap(session, swap_id=uuid.UUID(res["id"]), hospital_id=h.id, actor_id=coord.id)

    # A saiu (swapped_out), B entrou (active), exatamente 1 ativa no shift.
    a_status = session.scalar(
        select(ShiftAssignment.status).where(ShiftAssignment.id == assignment.id)
    )
    assert a_status == "swapped_out"
    active = session.scalar(
        select(func.count()).select_from(ShiftAssignment).where(
            ShiftAssignment.shift_id == shift.id, ShiftAssignment.status == "active"
        )
    )
    assert active == 1
    b_active = session.scalar(
        select(ShiftAssignment.doctor_id).where(
            ShiftAssignment.shift_id == shift.id, ShiftAssignment.status == "active"
        )
    )
    assert b_active == b.id
    # shift continua accepted; swap aprovado.
    swap_status = session.scalar(
        select(SwapRequest.status).where(SwapRequest.id == uuid.UUID(res["id"]))
    )
    assert swap_status == "approved"


def test_approve_swap_twice_is_409(session) -> None:
    h, a, b, _shift, assignment, coord = _setup(session)
    res = request_swap(session, doctor_id=a.id, assignment_id=assignment.id, to_doctor_id=b.id)
    swap_id = uuid.UUID(res["id"])
    approve_swap(session, swap_id=swap_id, hospital_id=h.id, actor_id=coord.id)
    with pytest.raises(Conflict):
        approve_swap(session, swap_id=swap_id, hospital_id=h.id, actor_id=coord.id)


def test_approve_swap_wrong_hospital_is_404(session) -> None:
    _h, a, b, _shift, assignment, coord = _setup(session)
    res = request_swap(session, doctor_id=a.id, assignment_id=assignment.id, to_doctor_id=b.id)
    other_hospital = Hospital(name="Outro")
    session.add(other_hospital)
    session.commit()
    with pytest.raises(NotFound):
        approve_swap(session, swap_id=uuid.UUID(res["id"]), hospital_id=other_hospital.id,
                     actor_id=coord.id)


def test_approve_swap_target_became_ineligible_is_422(session) -> None:
    h, a, b, shift, assignment, coord = _setup(session)
    res = request_swap(session, doctor_id=a.id, assignment_id=assignment.id, to_doctor_id=b.id)
    # B fica indisponível na janela do plantão depois do pedido.
    session.add(
        DoctorUnavailability(doctor_id=b.id, starts_at=shift.starts_at - timedelta(hours=1),
                             ends_at=shift.ends_at + timedelta(hours=1), reason="folga")
    )
    session.commit()
    with pytest.raises(UnprocessableEntity):
        approve_swap(session, swap_id=uuid.UUID(res["id"]), hospital_id=h.id, actor_id=coord.id)


def test_approve_swap_origin_assignment_cancelled_is_409(session) -> None:
    h, a, b, _shift, assignment, coord = _setup(session)
    res = request_swap(session, doctor_id=a.id, assignment_id=assignment.id, to_doctor_id=b.id)
    # plantão cancelado por baixo → assignment de A deixa de ser ativa.
    session.execute(
        update(ShiftAssignment)
        .where(ShiftAssignment.id == assignment.id)
        .values(status="cancelled")
    )
    session.commit()
    with pytest.raises(Conflict):
        approve_swap(session, swap_id=uuid.UUID(res["id"]), hospital_id=h.id, actor_id=coord.id)


# --- recusa / cancelamento --------------------------------------------------


def test_reject_swap_with_reason(session) -> None:
    h, a, b, _shift, assignment, coord = _setup(session)
    res = request_swap(session, doctor_id=a.id, assignment_id=assignment.id, to_doctor_id=b.id)
    reject_swap(session, swap_id=uuid.UUID(res["id"]), hospital_id=h.id, actor_id=coord.id,
                reason="cobertura insuficiente")
    swap = session.scalar(select(SwapRequest).where(SwapRequest.id == uuid.UUID(res["id"])))
    assert swap.status == "rejected"
    assert swap.reason == "cobertura insuficiente"


def test_cancel_swap_by_owner(session) -> None:
    _h, a, b, _shift, assignment, _c = _setup(session)
    res = request_swap(session, doctor_id=a.id, assignment_id=assignment.id, to_doctor_id=b.id)
    cancel_swap(session, swap_id=uuid.UUID(res["id"]), doctor_id=a.id)
    assert session.scalar(
        select(SwapRequest.status).where(SwapRequest.id == uuid.UUID(res["id"]))
    ) == "cancelled"


def test_cancel_swap_by_non_owner_is_404(session) -> None:
    _h, a, b, _shift, assignment, _c = _setup(session)
    res = request_swap(session, doctor_id=a.id, assignment_id=assignment.id, to_doctor_id=b.id)
    with pytest.raises(NotFound):
        cancel_swap(session, swap_id=uuid.UUID(res["id"]), doctor_id=b.id)
