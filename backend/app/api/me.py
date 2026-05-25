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
    Account,
    DoctorHospitalAffiliation,
    Hospital,
    Shift,
    ShiftAssignment,
    ShiftOffer,
    Specialty,
)
from app.services.doctors import resolve_doctor

bp = Blueprint("me", __name__, url_prefix="/me")


def _offer_view(offer: ShiftOffer, shift: Shift, hospital: Hospital) -> dict:
    return {
        "id": str(offer.id),
        "status": offer.status,
        "batch_number": offer.batch_number,
        "sent_at": offer.sent_at.isoformat(),
        "expires_at": offer.expires_at.isoformat(),
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
        select(ShiftOffer, Shift, Hospital)
        .join(Shift, Shift.id == ShiftOffer.shift_id)
        .join(Hospital, Hospital.id == Shift.hospital_id)
        .where(ShiftOffer.doctor_id == doctor.id)
        .where(Shift.hospital_id.in_(affiliated))
        .order_by(ShiftOffer.sent_at.desc())
    )
    if request.args.get("status") == "pending":
        stmt = stmt.where(ShiftOffer.status == "pending")

    rows = session.execute(stmt).all()
    return jsonify(
        {"offers": [_offer_view(offer, shift, hospital) for offer, shift, hospital in rows]}
    )


@bp.get("/assignments")
@require_role("medico")
def assignments():  # type: ignore[no-untyped-def]
    session = get_session()
    doctor = resolve_doctor(session, current_account_id())
    rows = session.execute(
        select(ShiftAssignment, Shift, Hospital)
        .join(Shift, Shift.id == ShiftAssignment.shift_id)
        .join(Hospital, Hospital.id == Shift.hospital_id)
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
                        "hospital_name": h.name,
                        "specialty_id": s.specialty_id,
                        "starts_at": s.starts_at.isoformat(),
                        "ends_at": s.ends_at.isoformat(),
                        "rate_cents": s.rate_cents,
                        "status": s.status,
                    },
                }
                for a, s, h in rows
            ]
        }
    )


@bp.get("/profile")
@require_role("medico")
def profile():  # type: ignore[no-untyped-def]
    session = get_session()
    doctor = resolve_doctor(session, current_account_id())
    from app.services.doctors import doctor_view

    view = doctor_view(session, doctor)
    # Enriquece com nomes de hospitais e especialidades
    spec_names = dict(session.execute(select(Specialty.id, Specialty.name)).all())
    hosp_names = dict(session.execute(select(Hospital.id, Hospital.name)).all())
    # Pega status das afiliações
    affs = session.execute(
        select(
            DoctorHospitalAffiliation.hospital_id,
            DoctorHospitalAffiliation.status,
        ).where(DoctorHospitalAffiliation.doctor_id == doctor.id)
    ).all()

    account = session.get(Account, current_account_id())

    return jsonify(
        {
            "profile": {
                **view,
                "email": account.email if account else None,
                "specialties": [
                    {"id": sid, "name": spec_names.get(sid, str(sid))}
                    for sid in view["specialty_ids"]
                ],
                "hospitals": [
                    {
                        "id": str(hid),
                        "name": hosp_names.get(hid, ""),
                        "status": status,
                    }
                    for hid, status in affs
                ],
            }
        }
    )


@bp.patch("/profile")
@require_role("medico")
def update_profile():  # type: ignore[no-untyped-def]
    session = get_session()
    doctor = resolve_doctor(session, current_account_id())
    body = request.get_json(force=True, silent=True) or {}

    from app.services.doctors import _UNSET, update_doctor

    kwargs: dict = {}
    if "name" in body:
        kwargs["name"] = body["name"]
    if "phone" in body:
        kwargs["phone"] = body["phone"]
    else:
        kwargs["phone"] = _UNSET
    # Médico NÃO edita specialty_ids — só coordenadora

    update_doctor(session, doctor, **kwargs)
    return jsonify({"status": "updated"})


@bp.get("/unavailabilities")
@require_role("medico")
def my_unavailabilities():  # type: ignore[no-untyped-def]
    session = get_session()
    doctor = resolve_doctor(session, current_account_id())
    from app.services.unavailabilities import list_unavailabilities

    items = list_unavailabilities(session, doctor.id)
    return jsonify(
        {
            "unavailabilities": [
                {
                    "id": str(u.id),
                    "starts_at": u.starts_at.isoformat(),
                    "ends_at": u.ends_at.isoformat(),
                    "reason": u.reason,
                }
                for u in items
            ]
        }
    )


@bp.post("/unavailabilities")
@require_role("medico")
def create_my_unavailability():  # type: ignore[no-untyped-def]
    session = get_session()
    doctor = resolve_doctor(session, current_account_id())
    body = request.get_json(force=True, silent=True) or {}

    from datetime import datetime as dt

    from app.api.errors import UnprocessableEntity
    from app.services.unavailabilities import create_unavailability

    try:
        starts_at = dt.fromisoformat(body["starts_at"])
        ends_at = dt.fromisoformat(body["ends_at"])
    except (KeyError, ValueError) as exc:
        raise UnprocessableEntity("starts_at and ends_at are required (ISO format)") from exc

    u_list = create_unavailability(
        session,
        doctor.id,
        starts_at=starts_at,
        ends_at=ends_at,
        reason=body.get("reason"),
        repeat_weeks=body.get("repeat_weeks", 0),
    )
    return jsonify(
        {
            "unavailabilities": [
                {
                    "id": str(u.id),
                    "starts_at": u.starts_at.isoformat(),
                    "ends_at": u.ends_at.isoformat(),
                    "reason": u.reason,
                }
                for u in u_list
            ]
        }
    ), 201


@bp.delete("/unavailabilities/<uuid:unavail_id>")
@require_role("medico")
def delete_my_unavailability(unavail_id):  # type: ignore[no-untyped-def]
    session = get_session()
    doctor = resolve_doctor(session, current_account_id())
    from app.services.unavailabilities import delete_unavailability

    delete_unavailability(session, unavail_id, doctor_id=doctor.id)
    return "", 204
