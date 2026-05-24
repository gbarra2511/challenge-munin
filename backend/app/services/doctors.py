"""Serviço de médicos: criação (conta + médico + vínculos) e listagem.

Criar um médico cria também a conta de login (role='medico', sem hospital
— o vínculo com hospitais vive em doctor_hospital_affiliations, N:M).
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.api.errors import Conflict, UnprocessableEntity
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
    found = set(
        session.scalars(
            select(Specialty.id).where(Specialty.id.in_(specialty_ids))
        )
    )
    missing = set(specialty_ids) - found
    if missing:
        raise UnprocessableEntity(
            "unknown specialty_ids", details={"missing": sorted(missing)}
        )


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
            DoctorHospitalAffiliation(
                doctor_id=doctor.id, hospital_id=hid, status="active"
            )
        )

    session.commit()
    session.refresh(doctor)
    return doctor


def doctor_view(session: Session, doctor: Doctor) -> dict[str, Any]:
    specialty_ids = sorted(
        session.scalars(
            select(DoctorSpecialty.specialty_id).where(
                DoctorSpecialty.doctor_id == doctor.id
            )
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


def list_doctors(
    session: Session, *, specialty_id: int | None = None
) -> list[Doctor]:
    stmt = select(Doctor)
    if specialty_id is not None:
        stmt = stmt.join(
            DoctorSpecialty, DoctorSpecialty.doctor_id == Doctor.id
        ).where(DoctorSpecialty.specialty_id == specialty_id)
    stmt = stmt.order_by(Doctor.name)
    return list(session.scalars(stmt))
