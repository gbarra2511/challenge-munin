"""Teste obrigatório nº 1: aceite concorrente — exatamente um vence.

Dois médicos diferentes aceitam o MESMO plantão simultaneamente, cada um
em sua própria conexão/transação (por isso usa `real_engine`, não o fixture
de savepoint). Um sincronizador (Barrier) força a largada junta.

Garantias verificadas:
- exatamente 1 sucesso e 1 conflito (409) — nunca 2 sucessos, nunca deadlock;
- exatamente 1 linha ativa em shift_assignments;
- shift termina em 'accepted'.
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
    ShiftOffer,
)
from app.services.offers import accept_offer


def _seed(session) -> tuple:
    now = datetime.now(UTC)
    hospital = Hospital(name="Hospital Central")
    session.add(hospital)
    session.flush()
    shift = Shift(
        hospital_id=hospital.id,
        specialty_id=1,
        starts_at=now + timedelta(days=10),
        ends_at=now + timedelta(days=10, hours=12),
        rate_cents=120000,
        status="offering",
        current_batch=1,
        batch_size=3,
        batch_window_minutes=30,
        escalate_hours_before=6,
        version=0,
    )
    session.add(shift)
    session.flush()

    offer_ids, doctor_ids = [], []
    for i in range(2):
        account = Account(
            email=f"doc{i}@central.test",
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
        offer = ShiftOffer(
            shift_id=shift.id,
            doctor_id=doctor.id,
            batch_number=1,
            status="pending",
            sent_at=now,
            expires_at=now + timedelta(minutes=30),
        )
        session.add(offer)
        session.flush()
        offer_ids.append(offer.id)
        doctor_ids.append(doctor.id)

    session.commit()
    return shift.id, offer_ids, doctor_ids


def test_concurrent_accept_only_one_wins(real_engine) -> None:
    Session = sessionmaker(bind=real_engine, future=True, expire_on_commit=False)
    with Session() as setup:
        shift_id, offer_ids, doctor_ids = _seed(setup)

    results: dict[int, str] = {}
    start = threading.Barrier(2)

    def worker(idx: int) -> None:
        start.wait()  # largada simultânea
        with Session() as s:
            try:
                accept_offer(s, offer_id=offer_ids[idx], doctor_id=doctor_ids[idx])
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
        shift = s.get(Shift, shift_id)
        assert shift.status == "accepted"
