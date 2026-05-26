"""Concorrência do swap: duas aprovações simultâneas — exatamente uma vence.

Espelha o teste obrigatório do aceite (test_concurrent_accept). Dois threads
de coordenação aprovam o MESMO swap ao mesmo tempo, cada um em sua conexão real
(`real_engine`, sem savepoint), com Barrier para largada junta.

Garantias:
- exatamente 1 sucesso + 1 conflito (409) — nunca 2 transferências, nunca deadlock;
- exatamente 1 assignment ativa no shift (a de B), A vira swapped_out;
- shift continua 'accepted' e o swap fica 'approved'.
"""

from __future__ import annotations

import threading
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import sessionmaker

from app.api.errors import ApiError
from app.infra.hashing import hash_password
from app.models import (
    Account,
    Doctor,
    DoctorHospitalAffiliation,
    DoctorSpecialty,
    Hospital,
    Shift,
    ShiftAssignment,
    SwapRequest,
)
from app.services.swaps import approve_swap


def _seed(session) -> tuple:
    now = datetime.now(UTC)
    hospital = Hospital(name="Hospital Central")
    session.add(hospital)
    session.flush()
    coord = Account(
        email="swapcoord@central.test",
        password_hash=hash_password("x"),
        role="coordenador",
        hospital_id=hospital.id,
    )
    session.add(coord)
    session.flush()
    shift = Shift(
        hospital_id=hospital.id,
        specialty_id=1,
        starts_at=now + timedelta(days=10),
        ends_at=now + timedelta(days=10, hours=12),
        rate_cents=120000,
        status="accepted",
        current_batch=1,
        batch_size=3,
        batch_window_minutes=30,
        escalate_hours_before=6,
        version=0,
    )
    session.add(shift)
    session.flush()

    doctors = []
    for i in range(2):
        account = Account(
            email=f"swapdoc{i}@central.test",
            password_hash=hash_password("x"),
            role="medico",
            hospital_id=None,
        )
        session.add(account)
        session.flush()
        doctor = Doctor(account_id=account.id, name=f"Dr {i}")
        session.add(doctor)
        session.flush()
        session.add(DoctorSpecialty(doctor_id=doctor.id, specialty_id=1))
        session.add(
            DoctorHospitalAffiliation(doctor_id=doctor.id, hospital_id=hospital.id, status="active")
        )
        doctors.append(doctor)

    a, b = doctors
    assignment = ShiftAssignment(
        shift_id=shift.id, doctor_id=a.id, status="active", accepted_at=now
    )
    session.add(assignment)
    session.flush()
    swap = SwapRequest(from_assignment_id=assignment.id, to_doctor_id=b.id, status="pending")
    session.add(swap)
    session.commit()
    return shift.id, swap.id, hospital.id, b.id, assignment.id, coord.id


def test_concurrent_approve_only_one_wins(real_engine) -> None:
    Session = sessionmaker(bind=real_engine, future=True, expire_on_commit=False)
    with Session() as setup:
        shift_id, swap_id, hospital_id, b_id, a_assignment_id, coord_id = _seed(setup)

    results: dict[int, str] = {}
    start = threading.Barrier(2)

    def worker(idx: int) -> None:
        start.wait()  # largada simultânea
        with Session() as s:
            try:
                approve_swap(s, swap_id=swap_id, hospital_id=hospital_id, actor_id=coord_id)
                results[idx] = "ok"
            except ApiError as exc:
                results[idx] = f"{exc.status_code}"
            except Exception as exc:  # deadlock/erro inesperado falharia aqui
                results[idx] = f"ERR:{type(exc).__name__}"

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(2)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    outcomes = sorted(results.values())
    assert outcomes == ["409", "ok"], f"esperava 1 ok + 1 conflito, veio {results}"

    with Session() as s:
        active = s.scalar(
            select(func.count())
            .select_from(ShiftAssignment)
            .where(ShiftAssignment.shift_id == shift_id, ShiftAssignment.status == "active")
        )
        assert active == 1
        active_doctor = s.scalar(
            select(ShiftAssignment.doctor_id).where(
                ShiftAssignment.shift_id == shift_id, ShiftAssignment.status == "active"
            )
        )
        assert active_doctor == b_id
        a_status = s.scalar(
            select(ShiftAssignment.status).where(ShiftAssignment.id == a_assignment_id)
        )
        assert a_status == "swapped_out"
        assert s.get(Shift, shift_id).status == "accepted"
        assert s.get(SwapRequest, swap_id).status == "approved"
