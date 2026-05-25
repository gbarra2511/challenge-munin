"""Ranking inteligente de médicos elegíveis (Bônus Tier 1 — PLANO §7).

Dois níveis:
1. `eligible_doctors` — filtro puro (specialty + affiliation + sem conflito).
2. `ranked_doctors` — score 0–100 com breakdown explicável.

Heurística de 4 fatores:
- Taxa de aceite (40%): aceites / (aceites + recusas + expirados)
- Recência (25%): dias desde último aceite (mais tempo = prioridade)
- Carga semanal (20%): assignments na semana do shift (menos = melhor)
- Tempo de resposta (15%): mediana de tempo de resposta (mais rápido = melhor)

Médico sem histórico recebe score neutro (50).
Stats calculados em 2 queries bulk (sem N+1).
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import timedelta
from typing import TYPE_CHECKING, Any
from uuid import UUID

from sqlalchemy import case, exists, extract, func, select

from app.models import (
    Doctor,
    DoctorHospitalAffiliation,
    DoctorSpecialty,
    DoctorUnavailability,
    ShiftAssignment,
    ShiftOffer,
)

if TYPE_CHECKING:
    from datetime import datetime

    from sqlalchemy.orm import Session

    from app.models import Shift


# --- tipos ---

NEUTRAL_SCORE = 50.0

WEIGHT_ACCEPTANCE = 0.40
WEIGHT_RECENCY = 0.25
WEIGHT_LOAD = 0.20
WEIGHT_RESPONSE = 0.15


@dataclass
class RankingBreakdown:
    acceptance_rate: float | None = None  # 0.0–1.0
    days_since_last: int | None = None
    weekly_load: int = 0
    avg_response_min: float | None = None
    score_acceptance: float = 0
    score_recency: float = 0
    score_load: float = 0
    score_response: float = 0


@dataclass
class RankedDoctor:
    doctor: Doctor
    score: float = NEUTRAL_SCORE
    breakdown: RankingBreakdown = field(default_factory=RankingBreakdown)


# --- filtro base (inalterado) ---


def eligible_doctors(
    session: Session,
    shift: Shift,
    *,
    exclude_doctor_ids: Iterable[UUID] = (),
) -> list[Doctor]:
    overlaps = func.tstzrange(DoctorUnavailability.starts_at, DoctorUnavailability.ends_at).op(
        "&&"
    )(func.tstzrange(shift.starts_at, shift.ends_at))
    has_conflict = exists().where(DoctorUnavailability.doctor_id == Doctor.id).where(overlaps)

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


# --- stats bulk ---


def _offer_stats_bulk(session: Session, doctor_ids: list[UUID]) -> dict[UUID, dict[str, Any]]:
    """1 query: por doctor_id → {accepted, declined, expired, total,
    avg_response_seconds, last_accepted_at}."""
    if not doctor_ids:
        return {}

    stmt = (
        select(
            ShiftOffer.doctor_id,
            func.count().filter(ShiftOffer.status == "accepted").label("accepted"),
            func.count().filter(ShiftOffer.status == "declined").label("declined"),
            func.count().filter(ShiftOffer.status == "expired").label("expired"),
            func.count().label("total"),
            # avg response time (só para ofertas respondidas)
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
        )
        .where(ShiftOffer.doctor_id.in_(doctor_ids))
        .group_by(ShiftOffer.doctor_id)
    )

    result: dict[UUID, dict[str, Any]] = {}
    for row in session.execute(stmt):
        avg = row.avg_response_seconds
        result[row.doctor_id] = {
            "accepted": row.accepted or 0,
            "declined": row.declined or 0,
            "expired": row.expired or 0,
            "total": row.total or 0,
            # func.avg devolve Decimal; coage pra float aqui senão o scoring
            # (Decimal * float) e a serialização JSON quebram.
            "avg_response_seconds": float(avg) if avg is not None else None,
        }
    return result


def _assignment_stats_bulk(
    session: Session,
    doctor_ids: list[UUID],
    shift_starts_at: datetime,
) -> dict[UUID, dict[str, Any]]:
    """1 query: por doctor_id → {weekly_load, last_accepted_at}."""
    if not doctor_ids:
        return {}

    # Semana do shift: seg–dom contendo shift_starts_at
    week_start = shift_starts_at - timedelta(days=shift_starts_at.weekday())
    week_start = week_start.replace(hour=0, minute=0, second=0, microsecond=0)
    week_end = week_start + timedelta(days=7)

    stmt = (
        select(
            ShiftAssignment.doctor_id,
            func.count()
            .filter(ShiftAssignment.accepted_at.between(week_start, week_end))
            .label("weekly_load"),
            func.max(ShiftAssignment.accepted_at).label("last_accepted_at"),
        )
        .where(
            ShiftAssignment.doctor_id.in_(doctor_ids),
            ShiftAssignment.status == "active",
        )
        .group_by(ShiftAssignment.doctor_id)
    )

    result: dict[UUID, dict[str, Any]] = {}
    for row in session.execute(stmt):
        result[row.doctor_id] = {
            "weekly_load": row.weekly_load or 0,
            "last_accepted_at": row.last_accepted_at,
        }
    return result


# --- scoring ---


def _score_acceptance(accepted: int, declined: int, expired: int) -> float:
    """0–100. Mais aceita = melhor."""
    total = accepted + declined + expired
    if total == 0:
        return 50.0  # neutro
    return (accepted / total) * 100


def _score_recency(days_since_last: int | None) -> float:
    """0–100. Mais tempo sem pegar = mais prioridade (distribuição justa).
    Cap em 30 dias = 100."""
    if days_since_last is None:
        return 50.0  # neutro — nunca pegou
    return min(100.0, (days_since_last / 30) * 100)


def _score_load(weekly_load: int) -> float:
    """0–100. Menos carga = melhor. 0 plantões = 100, 5+ = 0."""
    if weekly_load >= 5:
        return 0.0
    return ((5 - weekly_load) / 5) * 100


def _score_response(avg_response_seconds: float | None) -> float:
    """0–100. Mais rápido = melhor. <5min = 100, >30min = 0."""
    if avg_response_seconds is None:
        return 50.0  # neutro
    minutes = avg_response_seconds / 60
    if minutes <= 5:
        return 100.0
    if minutes >= 30:
        return 0.0
    return ((30 - minutes) / 25) * 100


# --- função principal ---


def ranked_doctors(
    session: Session,
    shift: Shift,
    *,
    exclude_doctor_ids: Iterable[UUID] = (),
    now: datetime | None = None,
) -> list[RankedDoctor]:
    """Retorna médicos elegíveis ordenados por score (desc) com breakdown."""
    from datetime import UTC
    from datetime import datetime as dt

    now = now or dt.now(UTC)

    doctors = eligible_doctors(session, shift, exclude_doctor_ids=exclude_doctor_ids)
    if not doctors:
        return []

    doctor_ids = [d.id for d in doctors]

    # 2 queries bulk
    offer_stats = _offer_stats_bulk(session, doctor_ids)
    assign_stats = _assignment_stats_bulk(session, doctor_ids, shift.starts_at)

    ranked: list[RankedDoctor] = []
    for doctor in doctors:
        ostats = offer_stats.get(doctor.id, {})
        astats = assign_stats.get(doctor.id, {})

        accepted = ostats.get("accepted", 0)
        declined = ostats.get("declined", 0)
        expired = ostats.get("expired", 0)
        total_offers = ostats.get("total", 0)
        avg_resp = ostats.get("avg_response_seconds")
        weekly_load = astats.get("weekly_load", 0)
        last_accepted = astats.get("last_accepted_at")

        # Dias desde último aceite
        days_since = None
        if last_accepted is not None:
            days_since = max(0, (now - last_accepted).days)

        # Scores individuais
        s_acc = _score_acceptance(accepted, declined, expired)
        s_rec = _score_recency(days_since)
        s_load = _score_load(weekly_load)
        s_resp = _score_response(avg_resp)

        # Score composto
        score = (
            s_acc * WEIGHT_ACCEPTANCE
            + s_rec * WEIGHT_RECENCY
            + s_load * WEIGHT_LOAD
            + s_resp * WEIGHT_RESPONSE
        )

        # Acceptance rate legível
        acc_rate = None
        if total_offers > 0:
            respondidas = accepted + declined + expired
            acc_rate = accepted / respondidas if respondidas > 0 else None

        avg_resp_min = None
        if avg_resp is not None:
            avg_resp_min = round(avg_resp / 60, 1)

        breakdown = RankingBreakdown(
            acceptance_rate=acc_rate,
            days_since_last=days_since,
            weekly_load=weekly_load,
            avg_response_min=avg_resp_min,
            score_acceptance=round(s_acc, 1),
            score_recency=round(s_rec, 1),
            score_load=round(s_load, 1),
            score_response=round(s_resp, 1),
        )

        ranked.append(RankedDoctor(doctor=doctor, score=round(score, 1), breakdown=breakdown))

    # Ordena: score desc, desempate por nome (determinístico)
    ranked.sort(key=lambda r: (-r.score, r.doctor.name, str(r.doctor.id)))
    return ranked
