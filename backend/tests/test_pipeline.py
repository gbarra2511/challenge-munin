"""Testes do pipeline de ofertas (tick): avanço de batch, escalação,
idempotência. Rodam direto nos serviços com `now` congelado — sem clock real.
"""
from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select

from app.models import AuditEvent, ShiftOffer
from app.services.offers import open_offers, run_tick
from tests.conftest import seed_doctor, seed_shift

# Plantão sempre bem no futuro pra escalação não interferir nos testes de batch.
FAR_START = datetime(2026, 9, 1, 8, 0, tzinfo=UTC)
FAR_END = FAR_START + timedelta(hours=12)
T0 = datetime(2026, 6, 1, 8, 0, tzinfo=UTC)


def _offers(session, shift_id, batch):
    return list(
        session.scalars(
            select(ShiftOffer).where(
                ShiftOffer.shift_id == shift_id, ShiftOffer.batch_number == batch
            )
        )
    )


def test_pipeline_advances_to_next_batch_after_window(session, hospital) -> None:
    shift = seed_shift(
        session, hospital_id=hospital.id, starts_at=FAR_START, ends_at=FAR_END
    )
    for i in range(6):
        seed_doctor(
            session,
            name=f"Dr {i:02d}",
            email=f"d{i}@med.test",
            specialty_ids=[1],
            hospital_ids=[hospital.id],
        )

    open_offers(session, shift, now=T0)
    batch1 = _offers(session, shift.id, 1)
    assert len(batch1) == 3
    assert all(o.status == "pending" for o in batch1)

    # 31 min depois: janela de 30 min venceu → tick expira batch1 e abre batch2.
    run_tick(session, now=T0 + timedelta(minutes=31))

    batch1 = _offers(session, shift.id, 1)
    batch2 = _offers(session, shift.id, 2)
    assert all(o.status == "expired" for o in batch1)
    assert len(batch2) == 3
    assert {o.doctor_id for o in batch2}.isdisjoint({o.doctor_id for o in batch1})
    session.refresh(shift)
    assert shift.current_batch == 2
    assert shift.status == "offering"


def test_escalation_to_needs_attention(session, hospital) -> None:
    now = datetime(2026, 6, 1, 12, 0, tzinfo=UTC)
    starts = now + timedelta(hours=5)  # dentro da janela de escalação (6h)
    shift = seed_shift(
        session,
        hospital_id=hospital.id,
        starts_at=starts,
        ends_at=starts + timedelta(hours=12),
        status="offering",
        current_batch=1,
        escalate_hours_before=6,
    )
    doc = seed_doctor(
        session, name="Dr A", email="a@med.test", specialty_ids=[1], hospital_ids=[hospital.id]
    )
    session.add(
        ShiftOffer(
            shift_id=shift.id,
            doctor_id=doc.id,
            batch_number=1,
            status="pending",
            sent_at=now,
            expires_at=now + timedelta(minutes=20),  # ainda viva
        )
    )
    session.commit()

    run_tick(session, now=now)

    session.refresh(shift)
    assert shift.status == "needs_attention"
    escalated = session.scalars(
        select(AuditEvent).where(
            AuditEvent.shift_id == shift.id,
            AuditEvent.event_type == "shift.escalated",
        )
    ).all()
    assert len(escalated) == 1


def test_tick_is_idempotent(session, hospital) -> None:
    shift = seed_shift(
        session, hospital_id=hospital.id, starts_at=FAR_START, ends_at=FAR_END
    )
    for i in range(3):
        seed_doctor(
            session,
            name=f"Dr {i:02d}",
            email=f"d{i}@med.test",
            specialty_ids=[1],
            hospital_ids=[hospital.id],
        )

    # Agora o tick não auto-oferta OPEN. A coordenadora dispara manualmente.
    open_offers(session, shift, now=T0)
    count_after_first = session.scalar(
        select(func.count()).select_from(ShiftOffer).where(ShiftOffer.shift_id == shift.id)
    )
    assert count_after_first == 3  # batch_size=3

    # Tick no mesmo instante: ofertas ainda estão vivas, nada muda.
    first = run_tick(session, now=T0)
    assert first["processed"] == 1
    assert first["advanced"] == 0

    # Rodar de novo no mesmo instante não muda nada.
    second = run_tick(session, now=T0)
    count_after_second = session.scalar(
        select(func.count()).select_from(ShiftOffer).where(ShiftOffer.shift_id == shift.id)
    )
    assert second["advanced"] == 0
    assert count_after_second == count_after_first
