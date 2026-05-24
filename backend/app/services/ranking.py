"""Ranking de médicos elegíveis para um plantão (PLANO §7).

Elegível = (1) tem a especialidade do plantão, (2) é afiliado ATIVO ao
hospital do plantão, (3) não tem janela de indisponibilidade que sobrepõe
o horário do plantão. A sobreposição é checada no banco via operador de
range do Postgres (`tstzrange && tstzrange`).

Ordenação determinística (nome, id) — base estável pro avanço de batch.
A pontuação explicável é bônus do Dia 7 e entra aqui depois.
"""
from __future__ import annotations

from collections.abc import Iterable
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import exists, func, select

from app.models import (
    Doctor,
    DoctorHospitalAffiliation,
    DoctorSpecialty,
    DoctorUnavailability,
)

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

    from app.models import Shift


def eligible_doctors(
    session: Session,
    shift: Shift,
    *,
    exclude_doctor_ids: Iterable[UUID] = (),
) -> list[Doctor]:
    overlaps = func.tstzrange(
        DoctorUnavailability.starts_at, DoctorUnavailability.ends_at
    ).op("&&")(func.tstzrange(shift.starts_at, shift.ends_at))
    has_conflict = (
        exists()
        .where(DoctorUnavailability.doctor_id == Doctor.id)
        .where(overlaps)
    )

    stmt = (
        select(Doctor)
        .join(DoctorSpecialty, DoctorSpecialty.doctor_id == Doctor.id)
        .join(
            DoctorHospitalAffiliation,
            (DoctorHospitalAffiliation.doctor_id == Doctor.id)
            & (DoctorHospitalAffiliation.status == "active"),
        )
        .where(
            DoctorSpecialty.specialty_id == shift.specialty_id,
            DoctorHospitalAffiliation.hospital_id == shift.hospital_id,
            ~has_conflict,
        )
        .order_by(Doctor.name, Doctor.id)
    )

    excluded = list(exclude_doctor_ids)
    if excluded:
        stmt = stmt.where(Doctor.id.notin_(excluded))

    return list(session.scalars(stmt).unique())
