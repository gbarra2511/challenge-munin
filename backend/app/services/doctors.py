"""Serviço de médicos: criação (conta + médico + vínculos) e listagem.

Criar um médico cria também a conta de login (role='medico', sem hospital
— o vínculo com hospitais vive em doctor_hospital_affiliations, N:M).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.api.errors import Conflict, NotFound, UnprocessableEntity
from app.infra.hashing import hash_password
from app.models import (
    Account,
    Doctor,
    DoctorHospitalAffiliation,
    DoctorSpecialty,
    Specialty,
)

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


def _validate_specialties(session: Session, specialty_ids: list[int]) -> None:
    found = set(session.scalars(select(Specialty.id).where(Specialty.id.in_(specialty_ids))))
    missing = set(specialty_ids) - found
    if missing:
        raise UnprocessableEntity("unknown specialty_ids", details={"missing": sorted(missing)})


def create_doctor(
    session: Session,
    *,
    name: str,
    email: str,
    password: str,
    phone: str | None,
    specialty_ids: list[int],
    hospital_ids: list[UUID],
) -> Doctor:
    _validate_specialties(session, specialty_ids)

    account = Account(
        email=email,
        password_hash=hash_password(password),
        role="medico",
        hospital_id=None,
    )
    session.add(account)
    try:
        # O e-mail é UNIQUE; o conflito estoura aqui no flush (não no commit).
        session.flush()  # garante account.id
    except IntegrityError as exc:
        session.rollback()
        raise Conflict("email already registered") from exc

    doctor = Doctor(account_id=account.id, name=name, phone=phone)
    session.add(doctor)
    session.flush()

    for sid in set(specialty_ids):
        session.add(DoctorSpecialty(doctor_id=doctor.id, specialty_id=sid))
    for hid in set(hospital_ids):
        session.add(
            DoctorHospitalAffiliation(doctor_id=doctor.id, hospital_id=hid, status="active")
        )

    session.commit()
    session.refresh(doctor)
    return doctor


def doctor_view(session: Session, doctor: Doctor) -> dict[str, Any]:
    """Visão de um médico individual (usado no GET /doctors/:id)."""
    specialty_ids = sorted(
        session.scalars(
            select(DoctorSpecialty.specialty_id).where(DoctorSpecialty.doctor_id == doctor.id)
        )
    )
    hospital_ids = [
        str(h)
        for h in session.scalars(
            select(DoctorHospitalAffiliation.hospital_id).where(
                DoctorHospitalAffiliation.doctor_id == doctor.id,
                DoctorHospitalAffiliation.status == "active",
            )
        )
    ]
    return {
        "id": str(doctor.id),
        "name": doctor.name,
        "phone": doctor.phone,
        "account_id": str(doctor.account_id) if doctor.account_id else None,
        "specialty_ids": specialty_ids,
        "hospital_ids": hospital_ids,
    }


def doctors_view_batch(session: Session, doctors: list[Doctor]) -> list[dict[str, Any]]:
    """Visão em lote — 2 queries no total em vez de 2×N. Fix do N+1."""
    if not doctors:
        return []
    ids = [d.id for d in doctors]

    # Bulk load specialties
    spec_rows = session.execute(
        select(DoctorSpecialty.doctor_id, DoctorSpecialty.specialty_id).where(
            DoctorSpecialty.doctor_id.in_(ids)
        )
    ).all()
    specs_by_doctor: dict[UUID, list[int]] = {}
    for doctor_id, spec_id in spec_rows:
        specs_by_doctor.setdefault(doctor_id, []).append(spec_id)

    # Bulk load affiliations
    aff_rows = session.execute(
        select(DoctorHospitalAffiliation.doctor_id, DoctorHospitalAffiliation.hospital_id).where(
            DoctorHospitalAffiliation.doctor_id.in_(ids),
            DoctorHospitalAffiliation.status == "active",
        )
    ).all()
    affs_by_doctor: dict[UUID, list[str]] = {}
    for doctor_id, hosp_id in aff_rows:
        affs_by_doctor.setdefault(doctor_id, []).append(str(hosp_id))

    return [
        {
            "id": str(d.id),
            "name": d.name,
            "phone": d.phone,
            "account_id": str(d.account_id) if d.account_id else None,
            "specialty_ids": sorted(specs_by_doctor.get(d.id, [])),
            "hospital_ids": affs_by_doctor.get(d.id, []),
        }
        for d in doctors
    ]


def resolve_doctor(session: Session, account_id: UUID) -> Doctor:
    doctor = session.scalar(select(Doctor).where(Doctor.account_id == account_id))
    if doctor is None:
        raise NotFound("no doctor profile for this account")
    return doctor


def list_doctors(session: Session, *, specialty_id: int | None = None) -> list[Doctor]:
    stmt = select(Doctor)
    if specialty_id is not None:
        stmt = stmt.join(DoctorSpecialty, DoctorSpecialty.doctor_id == Doctor.id).where(
            DoctorSpecialty.specialty_id == specialty_id
        )
    stmt = stmt.order_by(Doctor.name)
    return list(session.scalars(stmt))


# Sentinel para distinguir phone=None (limpar) de phone não enviado.
_UNSET = object()


def update_doctor(
    session: Session,
    doctor: Doctor,
    *,
    name: str | None = None,
    phone: str | None = _UNSET,
    specialty_ids: list[int] | None = None,
) -> Doctor:
    """Atualiza dados editáveis de um médico. specialty_ids = None → não muda."""
    if name is not None:
        doctor.name = name
    if phone is not _UNSET:
        doctor.phone = phone

    if specialty_ids is not None:
        _validate_specialties(session, specialty_ids)
        # Remove existentes e recria
        session.execute(select(DoctorSpecialty).where(DoctorSpecialty.doctor_id == doctor.id))
        from sqlalchemy import delete

        session.execute(delete(DoctorSpecialty).where(DoctorSpecialty.doctor_id == doctor.id))
        for sid in set(specialty_ids):
            session.add(DoctorSpecialty(doctor_id=doctor.id, specialty_id=sid))

    session.commit()
    session.refresh(doctor)
    return doctor


def toggle_affiliation(
    session: Session,
    doctor_id: UUID,
    hospital_id: UUID,
    *,
    active: bool,
) -> None:
    """Ativa ou desativa a afiliação de um médico com um hospital."""
    aff = session.scalar(
        select(DoctorHospitalAffiliation).where(
            DoctorHospitalAffiliation.doctor_id == doctor_id,
            DoctorHospitalAffiliation.hospital_id == hospital_id,
        )
    )
    if aff is None:
        raise NotFound("affiliation not found")
    aff.status = "active" if active else "inactive"
    session.commit()


def doctor_stats(
    session: Session,
    doctor_id: UUID,
) -> dict[str, Any]:
    """Calcula métricas de performance de um médico."""
    from sqlalchemy import case, extract, func

    from app.models import ShiftAssignment, ShiftOffer

    # Offer stats
    offer_row = session.execute(
        select(
            func.count().filter(ShiftOffer.status == "accepted").label("accepted"),
            func.count().filter(ShiftOffer.status == "declined").label("declined"),
            func.count().filter(ShiftOffer.status == "expired").label("expired"),
            func.count().label("total_offers"),
            func.avg(
                extract(
                    "epoch",
                    case(
                        (
                            ShiftOffer.responded_at.isnot(None),
                            ShiftOffer.responded_at - ShiftOffer.sent_at,
                        ),
                        else_=None,
                    ),
                )
            ).label("avg_response_seconds"),
        ).where(ShiftOffer.doctor_id == doctor_id)
    ).one()

    accepted = offer_row.accepted or 0
    declined = offer_row.declined or 0
    expired = offer_row.expired or 0
    respondidas = accepted + declined + expired

    acceptance_rate = None
    if respondidas > 0:
        acceptance_rate = round(accepted / respondidas, 3)

    avg_response_min = None
    if offer_row.avg_response_seconds is not None:
        avg_response_min = round(offer_row.avg_response_seconds / 60, 1)

    # Assignment stats
    assign_row = session.execute(
        select(
            func.count().label("total_assignments"),
        ).where(
            ShiftAssignment.doctor_id == doctor_id,
            ShiftAssignment.status == "active",
        )
    ).one()

    return {
        "total_offers": offer_row.total_offers or 0,
        "accepted": accepted,
        "declined": declined,
        "expired": expired,
        "acceptance_rate": acceptance_rate,
        "avg_response_min": avg_response_min,
        "total_assignments": assign_row.total_assignments or 0,
    }
