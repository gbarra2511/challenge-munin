"""Ações da coordenadora sobre plantões: cancelar, ampliar pool, listar ofertas.

Separado do CRUD básico (services/shifts.py) e do pipeline (services/offers.py)
porque esses são fluxos de ação explícita da coordenadora, não automação do tick.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any
from uuid import UUID

from sqlalchemy import select, update

from app.api.errors import Conflict, NotFound, UnprocessableEntity
from app.domain import shift as shift_sm
from app.domain.shift import ShiftStatus
from app.models import Doctor, Shift, ShiftAssignment, ShiftOffer
from app.services.audit import record_event
from app.services.ranking import eligible_doctors

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


def cancel_shift(
    session: Session,
    *,
    shift_id: UUID,
    hospital_id: UUID,
    actor_id: UUID,
) -> Shift:
    """Cancela um plantão. Supersede ofertas pendentes e cancela assignment ativa."""
    shift = session.scalars(
        select(Shift).where(Shift.id == shift_id).with_for_update()
    ).one_or_none()
    if shift is None or shift.hospital_id != hospital_id:
        raise NotFound("shift not found")

    previous_status = shift.status
    shift_sm.assert_transition(ShiftStatus(shift.status), ShiftStatus.CANCELLED)

    # Supersede todas as ofertas pendentes
    session.execute(
        update(ShiftOffer)
        .where(ShiftOffer.shift_id == shift.id, ShiftOffer.status == "pending")
        .values(status="superseded", responded_at=datetime.now(UTC))
    )

    # Cancela assignment ativa se existir
    session.execute(
        update(ShiftAssignment)
        .where(ShiftAssignment.shift_id == shift.id, ShiftAssignment.status == "active")
        .values(status="cancelled")
    )

    shift.status = ShiftStatus.CANCELLED
    shift.version += 1
    record_event(
        session,
        event_type="shift.cancelled",
        shift_id=shift.id,
        hospital_id=shift.hospital_id,
        actor_type="coord",
        actor_id=actor_id,
        payload={"previous_status": previous_status},
    )
    session.commit()
    session.refresh(shift)
    return shift


def expand_pool(
    session: Session,
    *,
    shift_id: UUID,
    hospital_id: UUID,
    actor_id: UUID,
) -> dict[str, Any]:
    """Amplia o pool de médicos de um plantão em needs_attention."""
    # Importa aqui para evitar circular (offers importa ranking, ranking não importa nada)
    from app.services.offers import _send_batch

    shift = session.scalars(
        select(Shift).where(Shift.id == shift_id).with_for_update()
    ).one_or_none()
    if shift is None or shift.hospital_id != hospital_id:
        raise NotFound("shift not found")

    if shift.status != ShiftStatus.NEEDS_ATTENTION:
        raise Conflict("shift must be in needs_attention status to expand pool")

    # Médicos já ofertados (todos os batches anteriores)
    already = set(
        session.scalars(select(ShiftOffer.doctor_id).where(ShiftOffer.shift_id == shift.id))
    )
    candidates = eligible_doctors(session, shift, exclude_doctor_ids=already)[: shift.batch_size]
    if not candidates:
        raise UnprocessableEntity("no more eligible doctors available")

    now = datetime.now(UTC)
    new_batch = shift.current_batch + 1

    shift_sm.assert_transition(ShiftStatus(shift.status), ShiftStatus.OFFERING)
    _send_batch(session, shift, candidates, batch_number=new_batch, now=now)
    shift.status = ShiftStatus.OFFERING
    shift.current_batch = new_batch
    shift.version += 1

    record_event(
        session,
        event_type="shift.pool_expanded",
        shift_id=shift.id,
        hospital_id=shift.hospital_id,
        actor_type="coord",
        actor_id=actor_id,
        payload={"batch": new_batch, "new_offers": len(candidates)},
    )
    session.commit()
    session.refresh(shift)
    return {"shift": shift, "new_offers": len(candidates)}


def get_shift_offers(
    session: Session,
    *,
    shift_id: UUID,
    hospital_id: UUID,
) -> list[dict[str, Any]]:
    """Lista todas as ofertas de um plantão com dados do médico, em 1 query."""
    # Valida que o shift pertence ao hospital
    shift = session.get(Shift, shift_id)
    if shift is None or shift.hospital_id != hospital_id:
        raise NotFound("shift not found")

    rows = session.execute(
        select(ShiftOffer, Doctor)
        .join(Doctor, Doctor.id == ShiftOffer.doctor_id)
        .where(ShiftOffer.shift_id == shift_id)
        .order_by(ShiftOffer.batch_number, ShiftOffer.sent_at)
    ).all()

    return [
        {
            "id": str(offer.id),
            "status": offer.status,
            "batch_number": offer.batch_number,
            "sent_at": offer.sent_at.isoformat(),
            "expires_at": offer.expires_at.isoformat(),
            "responded_at": offer.responded_at.isoformat() if offer.responded_at else None,
            "doctor": {"id": str(doctor.id), "name": doctor.name},
        }
        for offer, doctor in rows
    ]
