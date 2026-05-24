"""Serviço de plantões: criação e listagem, sempre escopados ao hospital
da coordenadora autenticada.

A criação não dispara ofertas — o plantão nasce 'open'. O pipeline de
ofertas (Dia 2-3) é quem move 'open' → 'offering'.
"""
from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any
from uuid import UUID

from sqlalchemy import select

from app.api.errors import UnprocessableEntity
from app.models import Shift, Specialty

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


def create_shift(
    session: Session,
    *,
    hospital_id: UUID,
    specialty_id: int,
    starts_at: datetime,
    ends_at: datetime,
    rate_cents: int,
    batch_size: int | None,
    batch_window_minutes: int | None,
    escalate_hours_before: int | None,
    defaults: dict[str, int],
) -> Shift:
    if session.get(Specialty, specialty_id) is None:
        raise UnprocessableEntity(
            "unknown specialty_id", details={"specialty_id": specialty_id}
        )

    shift = Shift(
        hospital_id=hospital_id,
        specialty_id=specialty_id,
        starts_at=starts_at,
        ends_at=ends_at,
        rate_cents=rate_cents,
        status="open",
        current_batch=0,
        batch_size=batch_size or defaults["batch_size"],
        batch_window_minutes=batch_window_minutes or defaults["batch_window_minutes"],
        escalate_hours_before=(
            escalate_hours_before
            if escalate_hours_before is not None
            else defaults["escalate_hours_before"]
        ),
        version=0,
    )
    session.add(shift)
    session.commit()
    session.refresh(shift)
    return shift


def list_shifts(
    session: Session, *, hospital_id: UUID, status: str | None = None
) -> list[Shift]:
    stmt = select(Shift).where(Shift.hospital_id == hospital_id)
    if status is not None:
        stmt = stmt.where(Shift.status == status)
    stmt = stmt.order_by(Shift.starts_at)
    return list(session.scalars(stmt))


def shift_view(shift: Shift) -> dict[str, Any]:
    return {
        "id": str(shift.id),
        "hospital_id": str(shift.hospital_id),
        "specialty_id": shift.specialty_id,
        "starts_at": shift.starts_at.isoformat(),
        "ends_at": shift.ends_at.isoformat(),
        "rate_cents": shift.rate_cents,
        "status": shift.status,
        "current_batch": shift.current_batch,
        "batch_size": shift.batch_size,
        "batch_window_minutes": shift.batch_window_minutes,
        "escalate_hours_before": shift.escalate_hours_before,
        "version": shift.version,
        "created_at": shift.created_at.isoformat() if shift.created_at else None,
    }
