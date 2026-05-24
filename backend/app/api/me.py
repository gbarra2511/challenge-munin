"""Visões do médico autenticado: suas ofertas e seus plantões aceitos.

`GET /me/offers` só retorna ofertas cujo plantão é de um hospital onde o
médico tem afiliação ATIVA — defesa contra oferta "vazada" de outro
hospital (teste obrigatório nº 3).
"""
from __future__ import annotations

from flask import Blueprint, jsonify, request
from sqlalchemy import select

from app.api.security import current_account_id, require_role
from app.infra.db import get_session
from app.models import (
    DoctorHospitalAffiliation,
    Shift,
    ShiftAssignment,
    ShiftOffer,
)
from app.services.doctors import resolve_doctor

bp = Blueprint("me", __name__, url_prefix="/me")


def _offer_view(offer: ShiftOffer, shift: Shift) -> dict:
    return {
        "id": str(offer.id),
        "status": offer.status,
        "batch_number": offer.batch_number,
        "sent_at": offer.sent_at.isoformat(),
        "expires_at": offer.expires_at.isoformat(),
        "shift": {
            "id": str(shift.id),
            "hospital_id": str(shift.hospital_id),
            "specialty_id": shift.specialty_id,
            "starts_at": shift.starts_at.isoformat(),
            "ends_at": shift.ends_at.isoformat(),
            "rate_cents": shift.rate_cents,
            "status": shift.status,
        },
    }


@bp.get("/offers")
@require_role("medico")
def offers():  # type: ignore[no-untyped-def]
    session = get_session()
    doctor = resolve_doctor(session, current_account_id())

    affiliated = (
        select(DoctorHospitalAffiliation.hospital_id)
        .where(DoctorHospitalAffiliation.doctor_id == doctor.id)
        .where(DoctorHospitalAffiliation.status == "active")
    )
    stmt = (
        select(ShiftOffer, Shift)
        .join(Shift, Shift.id == ShiftOffer.shift_id)
        .where(ShiftOffer.doctor_id == doctor.id)
        .where(Shift.hospital_id.in_(affiliated))
        .order_by(ShiftOffer.sent_at.desc())
    )
    if request.args.get("status") == "pending":
        stmt = stmt.where(ShiftOffer.status == "pending")

    rows = session.execute(stmt).all()
    return jsonify({"offers": [_offer_view(offer, shift) for offer, shift in rows]})


@bp.get("/assignments")
@require_role("medico")
def assignments():  # type: ignore[no-untyped-def]
    session = get_session()
    doctor = resolve_doctor(session, current_account_id())
    rows = session.execute(
        select(ShiftAssignment, Shift)
        .join(Shift, Shift.id == ShiftAssignment.shift_id)
        .where(ShiftAssignment.doctor_id == doctor.id)
        .order_by(Shift.starts_at)
    ).all()
    return jsonify(
        {
            "assignments": [
                {
                    "id": str(a.id),
                    "status": a.status,
                    "accepted_at": a.accepted_at.isoformat(),
                    "shift": {
                        "id": str(s.id),
                        "specialty_id": s.specialty_id,
                        "starts_at": s.starts_at.isoformat(),
                        "ends_at": s.ends_at.isoformat(),
                        "rate_cents": s.rate_cents,
                        "status": s.status,
                    },
                }
                for a, s in rows
            ]
        }
    )
