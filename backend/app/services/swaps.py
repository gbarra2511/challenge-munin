"""Troca de plantão (swap) — handoff aprovado pela coordenação.

Modelo: o médico A, que já tem uma assignment ATIVA, pede para passar o plantão
a um colega elegível B. A coordenação aprova (transferência atômica A→B) ou
recusa (com motivo). A pode desistir enquanto o pedido está pendente.

Peça crítica — `approve_swap`: espelha a disciplina de lock de
`offers.accept_offer`. O **shift é o ponto único de serialização**: travamos o
shift `FOR UPDATE` antes de tocar em assignment/swap, re-validamos tudo sob o
lock, e fazemos a transferência respeitando o índice único parcial
`one_active_assignment_per_shift WHERE status='active'`.

⚠️ Ordem da transferência: primeiro `UPDATE` da assignment de A → 'swapped_out'
(statement Core, executa imediatamente), **depois** `INSERT` da de B como
'active'. Inverter viola o índice parcial — e o unit-of-work do SQLAlchemy
ordena INSERTs antes de UPDATEs, então não dá pra confiar no flush implícito.
"""

from __future__ import annotations

from collections.abc import Iterable
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import aliased

from app.api.errors import Conflict, NotFound, UnprocessableEntity
from app.domain import swap as swap_sm
from app.domain.shift import ShiftStatus
from app.domain.swap import SwapStatus
from app.models import Doctor, Hospital, Shift, ShiftAssignment, SwapRequest
from app.services.audit import record_event
from app.services.notifications import notify_doctor, notify_hospital_coords
from app.services.ranking import eligible_doctors, ranked_doctors

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


def _now(now: datetime | None) -> datetime:
    return now or datetime.now(UTC)


def _eligible_ids(session: Session, shift: Shift, *, exclude: Iterable[UUID] = ()) -> set[UUID]:
    """IDs elegíveis para o plantão (mesma regra das ofertas: especialista OU
    fallback fora da especialidade, afiliado ativo, sem indisponibilidade
    sobreposta). Não checa assignment sobreposta em OUTRO plantão — paridade com
    o pipeline de ofertas; fica como refinamento futuro."""
    specialists = eligible_doctors(session, shift, specialty_match=True)
    fallback = eligible_doctors(session, shift, specialty_match=False)
    ids = {d.id for d in specialists} | {d.id for d in fallback}
    return ids - set(exclude)


# --- leitura / listagens ---------------------------------------------------


def swap_candidates(
    session: Session, *, assignment_id: UUID, doctor_id: UUID
) -> list[dict[str, Any]]:
    """Colegas elegíveis para assumir o plantão desta assignment, ranqueados
    (especialista primeiro, depois score). Exclui o próprio dono A."""
    assignment = session.get(ShiftAssignment, assignment_id)
    if assignment is None or assignment.doctor_id != doctor_id:
        raise NotFound("assignment not found")
    if assignment.status != "active":
        raise Conflict("assignment is not active", code="assignment_not_active")

    shift = session.get(Shift, assignment.shift_id)
    ranked = ranked_doctors(session, shift, exclude_doctor_ids=[doctor_id])
    return [
        {
            "doctor": {"id": str(r.doctor.id), "name": r.doctor.name},
            "score": r.score,
            "is_specialist": r.is_specialist,
        }
        for r in ranked
    ]


def _serialize_swap(
    swap: SwapRequest, shift: Shift, from_doctor: Doctor, to_doctor: Doctor, hospital: Hospital
) -> dict[str, Any]:
    return {
        "id": str(swap.id),
        "status": swap.status,
        "reason": swap.reason,
        "created_at": swap.created_at.isoformat() if swap.created_at else None,
        "decided_at": swap.decided_at.isoformat() if swap.decided_at else None,
        "from_doctor": {"id": str(from_doctor.id), "name": from_doctor.name},
        "to_doctor": {"id": str(to_doctor.id), "name": to_doctor.name},
        "shift": {
            "id": str(shift.id),
            "hospital_id": str(shift.hospital_id),
            "hospital_name": hospital.name,
            "specialty_id": shift.specialty_id,
            "starts_at": shift.starts_at.isoformat(),
            "ends_at": shift.ends_at.isoformat(),
            "rate_cents": shift.rate_cents,
            "status": shift.status,
        },
    }


def _swap_rows(session: Session):  # type: ignore[no-untyped-def]
    """Query base com todos os JOINs para serializar um swap (A, B, shift, hospital)."""
    from_assignment = aliased(ShiftAssignment)
    from_doctor = aliased(Doctor)
    to_doctor = aliased(Doctor)
    stmt = (
        select(SwapRequest, Shift, from_doctor, to_doctor, Hospital)
        .join(from_assignment, from_assignment.id == SwapRequest.from_assignment_id)
        .join(Shift, Shift.id == from_assignment.shift_id)
        .join(Hospital, Hospital.id == Shift.hospital_id)
        .join(from_doctor, from_doctor.id == from_assignment.doctor_id)
        .join(to_doctor, to_doctor.id == SwapRequest.to_doctor_id)
    )
    return stmt, from_assignment


def list_my_swaps(session: Session, *, doctor_id: UUID) -> list[dict[str, Any]]:
    """Pedidos feitos pelo médico A (dono da assignment de origem)."""
    stmt, from_assignment = _swap_rows(session)
    stmt = stmt.where(from_assignment.doctor_id == doctor_id).order_by(
        SwapRequest.created_at.desc()
    )
    return [_serialize_swap(s, sh, fd, td, h) for s, sh, fd, td, h in session.execute(stmt).all()]


def list_pending_swaps(
    session: Session, *, hospital_id: UUID, status: str = "pending"
) -> list[dict[str, Any]]:
    """Pedidos de troca de um hospital (escopo da coordenação)."""
    stmt, _ = _swap_rows(session)
    stmt = stmt.where(Shift.hospital_id == hospital_id, SwapRequest.status == status).order_by(
        SwapRequest.created_at
    )
    return [_serialize_swap(s, sh, fd, td, h) for s, sh, fd, td, h in session.execute(stmt).all()]


# --- pedido (médico A) ------------------------------------------------------


def request_swap(
    session: Session,
    *,
    doctor_id: UUID,
    assignment_id: UUID,
    to_doctor_id: UUID,
    now: datetime | None = None,
) -> dict[str, Any]:
    now = _now(now)
    if to_doctor_id == doctor_id:
        raise UnprocessableEntity("cannot swap a shift to yourself", code="swap_to_self")

    assignment = session.get(ShiftAssignment, assignment_id)
    if assignment is None or assignment.doctor_id != doctor_id:
        raise NotFound("assignment not found")
    if assignment.status != "active":
        raise Conflict("assignment is not active", code="assignment_not_active")

    shift = session.get(Shift, assignment.shift_id)
    if shift.status != ShiftStatus.ACCEPTED:
        raise Conflict("shift is not in a swappable state", code="shift_not_swappable")
    if shift.starts_at <= now:
        raise Conflict("shift has already started", code="shift_already_started")

    if to_doctor_id not in _eligible_ids(session, shift, exclude=[doctor_id]):
        raise UnprocessableEntity("target doctor is not eligible", code="target_ineligible")

    # Guarda amigável; o índice parcial uq_swap_pending_per_assignment é a rede.
    existing = session.scalar(
        select(SwapRequest.id).where(
            SwapRequest.from_assignment_id == assignment_id,
            SwapRequest.status == SwapStatus.PENDING,
        )
    )
    if existing is not None:
        raise Conflict(
            "there is already a pending swap for this shift", code="swap_already_pending"
        )

    swap = SwapRequest(
        from_assignment_id=assignment_id,
        to_doctor_id=to_doctor_id,
        status=SwapStatus.PENDING,
    )
    session.add(swap)
    try:
        session.flush()
    except IntegrityError as exc:  # corrida perdida no índice parcial
        session.rollback()
        raise Conflict(
            "there is already a pending swap for this shift", code="swap_already_pending"
        ) from exc

    record_event(
        session,
        event_type="swap.requested",
        shift_id=shift.id,
        hospital_id=shift.hospital_id,
        actor_type="doctor",
        actor_id=doctor_id,
        payload={
            "swap_id": str(swap.id),
            "from_doctor_id": str(doctor_id),
            "to_doctor_id": str(to_doctor_id),
        },
    )
    from_name = session.scalar(select(Doctor.name).where(Doctor.id == doctor_id))
    to_name = session.scalar(select(Doctor.name).where(Doctor.id == to_doctor_id))
    notify_hospital_coords(
        session,
        hospital_id=shift.hospital_id,
        template="swap.requested",
        ref_id=str(swap.id),
        title="Novo pedido de troca",
        body=f"{from_name} quer passar um plantão para {to_name}. Aprovar?",
        path="/trocas",
        now=now,
    )
    session.commit()
    return {
        "id": str(swap.id),
        "status": swap.status,
        "shift_id": str(shift.id),
        "to_doctor_id": str(to_doctor_id),
    }


# --- decisão (coordenação) --------------------------------------------------


def approve_swap(
    session: Session,
    *,
    swap_id: UUID,
    hospital_id: UUID,
    actor_id: UUID,
    reason: str | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Aprova a troca: transfere a assignment de A para B atomicamente.

    Lock pessimista com o SHIFT como ponto único de serialização (igual ao
    accept). Quem chega segundo bloqueia no lock do shift, depois relê o swap
    já decidido → 409. O índice único parcial em shift_assignments é a rede."""
    now = _now(now)

    # Peek por COLUNAS (não ORM): carregar o objeto aqui o deixaria no identity
    # map com status stale; o reload FOR UPDATE devolveria o cache antigo e o
    # perdedor da corrida não veria 'approved'. Igual ao accept_offer.
    from_assignment_id = session.scalar(
        select(SwapRequest.from_assignment_id).where(SwapRequest.id == swap_id)
    )
    if from_assignment_id is None:
        raise NotFound("swap request not found")
    shift_id = session.scalar(
        select(ShiftAssignment.shift_id).where(ShiftAssignment.id == from_assignment_id)
    )

    # 1) trava o shift — serializa todo accept/cancel/swap deste plantão.
    shift = session.scalars(select(Shift).where(Shift.id == shift_id).with_for_update()).one()
    if shift.hospital_id != hospital_id:
        raise NotFound("swap request not found")  # não vaza existência

    # 2) sob o lock, relê o swap e a assignment de origem.
    swap = session.scalars(
        select(SwapRequest).where(SwapRequest.id == swap_id).with_for_update()
    ).one()
    if swap.status != SwapStatus.PENDING:
        raise Conflict("swap is no longer pending", code="swap_not_pending")

    from_assignment = session.scalars(
        select(ShiftAssignment)
        .where(ShiftAssignment.id == swap.from_assignment_id)
        .with_for_update()
    ).one()
    if from_assignment.status != "active" or from_assignment.shift_id != shift.id:
        raise Conflict("original assignment is no longer active", code="assignment_not_active")
    if shift.status != ShiftStatus.ACCEPTED:
        raise Conflict("shift is no longer in a swappable state", code="shift_not_swappable")

    # 3) re-valida B elegível DENTRO do lock (pode ter ficado indisponível).
    if swap.to_doctor_id not in _eligible_ids(session, shift, exclude=[from_assignment.doctor_id]):
        raise UnprocessableEntity(
            "target doctor is no longer eligible", code="target_ineligible"
        )

    # 4) TRANSFERÊNCIA — ordem importa para o índice parcial.
    # UPDATE Core executa imediatamente: A vira swapped_out ANTES do INSERT de B.
    session.execute(
        update(ShiftAssignment)
        .where(ShiftAssignment.id == from_assignment.id)
        .values(status="swapped_out")
    )
    session.add(
        ShiftAssignment(
            shift_id=shift.id,
            doctor_id=swap.to_doctor_id,
            status="active",
            accepted_at=now,
        )
    )

    # 5) decide o swap + recusa irmãos pendentes (defesa; o índice já bloqueia 2).
    swap_sm.assert_transition(SwapStatus(swap.status), SwapStatus.APPROVED)
    swap.status = SwapStatus.APPROVED
    swap.decided_by = actor_id
    swap.decided_at = now
    swap.reason = reason
    session.execute(
        update(SwapRequest)
        .where(
            SwapRequest.from_assignment_id == swap.from_assignment_id,
            SwapRequest.status == SwapStatus.PENDING,
            SwapRequest.id != swap.id,
        )
        .values(status=SwapStatus.REJECTED, decided_by=actor_id, decided_at=now)
    )
    shift.version += 1

    record_event(
        session,
        event_type="swap.approved",
        shift_id=shift.id,
        hospital_id=shift.hospital_id,
        actor_type="coord",
        actor_id=actor_id,
        payload={
            "swap_id": str(swap.id),
            "from_doctor_id": str(from_assignment.doctor_id),
            "to_doctor_id": str(swap.to_doctor_id),
        },
    )
    b_name = session.scalar(select(Doctor.name).where(Doctor.id == swap.to_doctor_id))
    a_name = session.scalar(select(Doctor.name).where(Doctor.id == from_assignment.doctor_id))
    notify_doctor(
        session,
        doctor_id=from_assignment.doctor_id,
        template="swap.approved",
        ref_id=str(swap.id),
        title="Troca aprovada",
        body=f"Sua troca foi aprovada — {b_name} assume o plantão.",
        path="/minhas-trocas",
        now=now,
    )
    notify_doctor(
        session,
        doctor_id=swap.to_doctor_id,
        template="swap.assigned",
        ref_id=str(swap.id),
        title="Você assumiu um plantão",
        body=f"A coordenação aprovou a troca de {a_name} — o plantão agora é seu.",
        path="/agenda",
        now=now,
    )
    session.commit()
    return {
        "id": str(swap.id),
        "status": swap.status,
        "shift_id": str(shift.id),
        "from_doctor_id": str(from_assignment.doctor_id),
        "to_doctor_id": str(swap.to_doctor_id),
    }


def reject_swap(
    session: Session,
    *,
    swap_id: UUID,
    hospital_id: UUID,
    actor_id: UUID,
    reason: str | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    now = _now(now)
    # Peek por colunas (ver approve_swap) para não cachear status stale.
    from_assignment_id = session.scalar(
        select(SwapRequest.from_assignment_id).where(SwapRequest.id == swap_id)
    )
    if from_assignment_id is None:
        raise NotFound("swap request not found")
    shift_id = session.scalar(
        select(ShiftAssignment.shift_id).where(ShiftAssignment.id == from_assignment_id)
    )

    # Trava o shift (consistência com approve) e valida escopo do hospital.
    shift = session.scalars(
        select(Shift).where(Shift.id == shift_id).with_for_update()
    ).one()
    if shift.hospital_id != hospital_id:
        raise NotFound("swap request not found")

    swap = session.scalars(
        select(SwapRequest).where(SwapRequest.id == swap_id).with_for_update()
    ).one()
    if swap.status != SwapStatus.PENDING:
        raise Conflict("swap is no longer pending", code="swap_not_pending")

    swap_sm.assert_transition(SwapStatus(swap.status), SwapStatus.REJECTED)
    swap.status = SwapStatus.REJECTED
    swap.decided_by = actor_id
    swap.decided_at = now
    swap.reason = reason
    record_event(
        session,
        event_type="swap.rejected",
        shift_id=shift.id,
        hospital_id=shift.hospital_id,
        actor_type="coord",
        actor_id=actor_id,
        payload={"swap_id": str(swap.id), "reason": reason},
    )
    a_doctor_id = session.scalar(
        select(ShiftAssignment.doctor_id).where(ShiftAssignment.id == swap.from_assignment_id)
    )
    body = "Sua troca foi recusada pela coordenação."
    if reason:
        body += f" Motivo: {reason}"
    notify_doctor(
        session,
        doctor_id=a_doctor_id,
        template="swap.rejected",
        ref_id=str(swap.id),
        title="Troca recusada",
        body=body,
        path="/minhas-trocas",
        now=now,
    )
    session.commit()
    return {"id": str(swap.id), "status": swap.status}


def cancel_swap(
    session: Session,
    *,
    swap_id: UUID,
    doctor_id: UUID,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Médico A desiste do próprio pedido enquanto pendente."""
    now = _now(now)
    swap = session.scalars(
        select(SwapRequest).where(SwapRequest.id == swap_id).with_for_update()
    ).one_or_none()
    if swap is None:
        raise NotFound("swap request not found")

    assignment = session.get(ShiftAssignment, swap.from_assignment_id)
    if assignment is None or assignment.doctor_id != doctor_id:
        raise NotFound("swap request not found")  # não é dono → não vaza
    if swap.status != SwapStatus.PENDING:
        raise Conflict("swap is no longer pending", code="swap_not_pending")

    swap_sm.assert_transition(SwapStatus(swap.status), SwapStatus.CANCELLED)
    swap.status = SwapStatus.CANCELLED
    swap.decided_at = now
    record_event(
        session,
        event_type="swap.cancelled",
        shift_id=assignment.shift_id,
        actor_type="doctor",
        actor_id=doctor_id,
        payload={"swap_id": str(swap.id)},
    )
    session.commit()
    return {"id": str(swap.id), "status": swap.status}
