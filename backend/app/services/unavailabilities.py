"""CRUD de indisponibilidades do médico.

Usado tanto pela coordenadora (via /doctors/:id/unavailabilities)
quanto pelo médico (via /me/unavailabilities).
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import select

from app.api.errors import NotFound, UnprocessableEntity
from app.models import DoctorUnavailability

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


def list_unavailabilities(
    session: Session,
    doctor_id: UUID,
) -> list[DoctorUnavailability]:
    """Lista indisponibilidades de um médico, ordenadas por data."""
    stmt = (
        select(DoctorUnavailability)
        .where(DoctorUnavailability.doctor_id == doctor_id)
        .order_by(DoctorUnavailability.starts_at.desc())
    )
    return list(session.scalars(stmt))


def create_unavailability(
    session: Session,
    doctor_id: UUID,
    *,
    starts_at: datetime,
    ends_at: datetime,
    reason: str | None = None,
    repeat_weeks: int = 0,
) -> list[DoctorUnavailability]:
    """Cria uma indisponibilidade. Valida que ends > starts e não é no passado."""
    if ends_at <= starts_at:
        raise UnprocessableEntity(
            "ends_at must be after starts_at",
            details={"ends_at": "must be after starts_at"},
        )

    now = datetime.now(UTC)
    if ends_at < now:
        raise UnprocessableEntity(
            "cannot create unavailability in the past",
            details={"ends_at": "must be in the future"},
        )

    created = []
    from datetime import timedelta

    for i in range(max(1, repeat_weeks + 1)):
        offset = timedelta(weeks=i)
        u_start = starts_at + offset
        u_end = ends_at + offset

        unavail = DoctorUnavailability(
            doctor_id=doctor_id,
            starts_at=u_start,
            ends_at=u_end,
            reason=reason,
        )
        session.add(unavail)
        created.append(unavail)

    session.commit()
    for unavail in created:
        session.refresh(unavail)

    return created


def delete_unavailability(
    session: Session,
    unavailability_id: UUID,
    *,
    doctor_id: UUID,
) -> None:
    """Remove uma indisponibilidade. Verifica que pertence ao médico."""
    unavail = session.get(DoctorUnavailability, unavailability_id)
    if unavail is None or unavail.doctor_id != doctor_id:
        raise NotFound("unavailability not found")
    session.delete(unavail)
    session.commit()
