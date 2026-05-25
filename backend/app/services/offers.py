"""Pipeline de ofertas: abrir, avançar (tick) e aceitar/recusar.

O coração do sistema. Duas peças críticas:

1. `accept_offer` — aceite atômico (PLANO §6). Lock pessimista em
   offer→shift (sempre nessa ordem, pra não dar deadlock entre dois
   aceites concorrentes) + o índice único parcial em shift_assignments
   como defesa em profundidade.
2. `run_tick` — avanço idempotente do pipeline (PLANO §7). Só faz
   transições válidas; rodar duas vezes no mesmo minuto não muda nada.

Todas as funções recebem `now` injetável (default = agora UTC) pra teste
determinístico com clock congelado.
"""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any
from uuid import UUID

from sqlalchemy import select, update

from app.api.errors import Conflict, Gone, NotFound, UnprocessableEntity
from app.domain import shift as shift_sm
from app.domain.shift import ShiftStatus
from app.models import Doctor, Shift, ShiftAssignment, ShiftOffer
from app.services.audit import record_event
from app.services.ranking import eligible_doctors, ranked_doctors

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


def _now(now: datetime | None) -> datetime:
    return now or datetime.now(UTC)


# --- abertura e envio de batch ---------------------------------------------


def _send_batch(
    session: Session, shift: Shift, doctors: list[Doctor], *, batch_number: int, now: datetime
) -> None:
    window = timedelta(minutes=shift.batch_window_minutes)
    for doctor in doctors:
        session.add(
            ShiftOffer(
                shift_id=shift.id,
                doctor_id=doctor.id,
                batch_number=batch_number,
                status="pending",
                sent_at=now,
                expires_at=now + window,
            )
        )
    record_event(
        session,
        event_type="offer.batch_sent",
        shift_id=shift.id,
        hospital_id=shift.hospital_id,
        actor_type="system",
        payload={
            "batch": batch_number,
            "doctor_ids": [str(d.id) for d in doctors],
            "count": len(doctors),
        },
    )


def _begin_offering(
    session: Session, shift: Shift, doctors: list[Doctor], *, now: datetime
) -> None:
    shift_sm.assert_transition(ShiftStatus(shift.status), ShiftStatus.OFFERING)
    _send_batch(session, shift, doctors, batch_number=1, now=now)
    shift.status = ShiftStatus.OFFERING
    shift.current_batch = 1
    shift.version += 1
    record_event(
        session,
        event_type="shift.offering_started",
        shift_id=shift.id,
        hospital_id=shift.hospital_id,
        actor_type="system",
        payload={"batch_size": shift.batch_size},
    )


def open_offers(
    session: Session,
    shift: Shift,
    *,
    doctor_ids: list[UUID] | None = None,
    now: datetime | None = None,
) -> Shift:
    """Endpoint POST /shifts/:id/offer — abre o 1º batch. doctor_ids vazio
    usa o ranking; preenchido oferta a esses médicos (override manual)."""
    now = _now(now)
    if shift.status != ShiftStatus.OPEN:
        raise Conflict("shift is not open for offering")

    if doctor_ids:
        doctors = list(session.scalars(select(Doctor).where(Doctor.id.in_(doctor_ids))))
        missing = set(doctor_ids) - {d.id for d in doctors}
        if missing:
            raise UnprocessableEntity(
                "unknown doctor_ids", details={"missing": [str(m) for m in missing]}
            )
    else:
        ranked = ranked_doctors(session, shift)
        doctors = [r.doctor for r in ranked[: shift.batch_size]]

    if not doctors:
        raise UnprocessableEntity("no eligible doctors for this shift")

    _begin_offering(session, shift, doctors, now=now)
    session.commit()
    session.refresh(shift)
    return shift


# --- tick (avanço idempotente) ---------------------------------------------


def _offered_doctor_ids(session: Session, shift_id: UUID) -> set[UUID]:
    return set(
        session.scalars(
            select(ShiftOffer.doctor_id).where(ShiftOffer.shift_id == shift_id)
        )
    )


def _within_escalation_window(shift: Shift, now: datetime) -> bool:
    return (shift.starts_at - now) <= timedelta(hours=shift.escalate_hours_before)


def _escalate(session: Session, shift: Shift) -> None:
    shift_sm.assert_transition(ShiftStatus(shift.status), ShiftStatus.NEEDS_ATTENTION)
    shift.status = ShiftStatus.NEEDS_ATTENTION
    shift.version += 1
    record_event(
        session,
        event_type="shift.escalated",
        shift_id=shift.id,
        hospital_id=shift.hospital_id,
        actor_type="system",
        payload={"reason": "no_eligible_or_too_close"},
    )


def _tick_offering(session: Session, shift: Shift, now: datetime, stats: dict[str, int]) -> None:
    pending = list(
        session.scalars(
            select(ShiftOffer).where(
                ShiftOffer.shift_id == shift.id,
                ShiftOffer.batch_number == shift.current_batch,
                ShiftOffer.status == "pending",
            )
        )
    )

    # 1. expira as vencidas
    alive = []
    for offer in pending:
        if offer.expires_at <= now:
            offer.status = "expired"
            offer.responded_at = now
            stats["expired_offers"] += 1
            record_event(
                session,
                event_type="offer.expired",
                shift_id=shift.id,
                hospital_id=shift.hospital_id,
                actor_type="system",
                payload={"offer_id": str(offer.id), "batch": offer.batch_number},
            )
        else:
            alive.append(offer)

    if alive:
        # 3. ainda há pendentes vivas — só escala se está perto demais
        if _within_escalation_window(shift, now):
            _escalate(session, shift)
            stats["escalated"] += 1
        return

    # 2. batch esgotou sem aceite → tenta próximo batch
    already = _offered_doctor_ids(session, shift.id)
    ranked = ranked_doctors(session, shift, exclude_doctor_ids=already)
    nxt = [r.doctor for r in ranked[: shift.batch_size]]
    if nxt:
        _send_batch(session, shift, nxt, batch_number=shift.current_batch + 1, now=now)
        shift.current_batch += 1
        shift.version += 1
        stats["advanced"] += 1
        record_event(
            session,
            event_type="shift.batch_advanced",
            shift_id=shift.id,
            hospital_id=shift.hospital_id,
            actor_type="system",
            payload={"batch": shift.current_batch},
        )
    elif _within_escalation_window(shift, now):
        _escalate(session, shift)
        stats["escalated"] += 1


def run_tick(session: Session, *, now: datetime | None = None) -> dict[str, int]:
    """Avança o pipeline de todos os plantões em OFFERING. Idempotente.

    Nota: shifts OPEN não são processados pelo tick. A coordenadora deve
    disparar explicitamente via POST /shifts/:id/offer. Isso evita que
    plantões sejam ofertados antes do momento desejado."""
    now = _now(now)
    stats = {"processed": 0, "advanced": 0, "escalated": 0, "expired_offers": 0}

    shifts = list(
        session.scalars(
            select(Shift)
            .where(Shift.status == ShiftStatus.OFFERING)
            .with_for_update()
        )
    )

    for shift in shifts:
        stats["processed"] += 1
        _tick_offering(session, shift, now, stats)

    session.commit()
    return stats


# --- aceite atômico e recusa -----------------------------------------------


def accept_offer(
    session: Session, *, offer_id: UUID, doctor_id: UUID, now: datetime | None = None
) -> dict[str, Any]:
    """PLANO §6. Lock pessimista com o SHIFT como ponto único de
    serialização por plantão. Quem chega segundo bloqueia no lock do shift
    (antes de tocar em qualquer oferta), depois lê shift já 'accepted' → 409.
    Índice único parcial em shift_assignments é a rede caso a lógica falhe.

    Ordem: shift → offer (não offer → shift). Travar a oferta primeiro
    causaria deadlock: o supersede de um aceite precisa travar a oferta que
    o aceite concorrente já segura. Travar o shift antes elimina o ciclo."""
    now = _now(now)

    # Leitura sem lock só pra descobrir o shift desta oferta.
    shift_id = session.scalar(
        select(ShiftOffer.shift_id).where(ShiftOffer.id == offer_id)
    )
    if shift_id is None:
        raise NotFound("offer not found")

    # 1) trava o shift — serializa todos os aceites concorrentes do plantão.
    shift = session.scalars(
        select(Shift).where(Shift.id == shift_id).with_for_update()
    ).one()
    # 2) sob o lock do shift, trava/relê a oferta.
    offer = session.scalars(
        select(ShiftOffer).where(ShiftOffer.id == offer_id).with_for_update()
    ).one()
    if offer.doctor_id != doctor_id:
        raise NotFound("offer not found")

    if shift.status != ShiftStatus.OFFERING:
        raise Conflict("shift no longer accepting offers", code="shift_no_longer_open")
    if offer.status != "pending":
        raise Conflict("offer no longer pending", code="offer_no_longer_pending")
    if now > offer.expires_at:
        offer.status = "expired"
        offer.responded_at = now
        record_event(
            session,
            event_type="offer.expired",
            shift_id=shift.id,
            hospital_id=shift.hospital_id,
            actor_type="doctor",
            actor_id=doctor_id,
            payload={"offer_id": str(offer.id), "on": "accept_attempt"},
        )
        session.commit()
        raise Gone("offer has expired", code="offer_expired")

    # Transições: oferta aceita, demais pendentes do shift superseded.
    offer.status = "accepted"
    offer.responded_at = now
    session.add(
        ShiftAssignment(
            shift_id=shift.id, doctor_id=doctor_id, status="active", accepted_at=now
        )
    )
    session.execute(
        update(ShiftOffer)
        .where(
            ShiftOffer.shift_id == shift.id,
            ShiftOffer.status == "pending",
            ShiftOffer.id != offer.id,
        )
        .values(status="superseded", responded_at=now)
    )
    shift_sm.assert_transition(ShiftStatus(shift.status), ShiftStatus.ACCEPTED)
    shift.status = ShiftStatus.ACCEPTED
    shift.version += 1
    record_event(
        session,
        event_type="shift.accepted",
        shift_id=shift.id,
        hospital_id=shift.hospital_id,
        actor_type="doctor",
        actor_id=doctor_id,
        payload={"offer_id": str(offer.id)},
    )
    session.commit()
    return {"shift_id": str(shift.id), "offer_id": str(offer.id), "status": "accepted"}


def decline_offer(
    session: Session, *, offer_id: UUID, doctor_id: UUID, now: datetime | None = None
) -> dict[str, Any]:
    now = _now(now)
    offer = session.scalars(
        select(ShiftOffer).where(ShiftOffer.id == offer_id).with_for_update()
    ).one_or_none()
    if offer is None or offer.doctor_id != doctor_id:
        raise NotFound("offer not found")
    if offer.status != "pending":
        raise Conflict("offer no longer pending", code="offer_no_longer_pending")

    # Carrega o shift para obter hospital_id (fix: antes estava faltando)
    shift = session.get(Shift, offer.shift_id)

    offer.status = "declined"
    offer.responded_at = now
    record_event(
        session,
        event_type="offer.declined",
        shift_id=offer.shift_id,
        hospital_id=shift.hospital_id if shift else None,
        actor_type="doctor",
        actor_id=doctor_id,
        payload={"offer_id": str(offer.id)},
    )
    session.commit()
    return {"offer_id": str(offer.id), "status": "declined"}
