"""Blueprint de médicos (CRUD + gestão — coordenador)."""
from __future__ import annotations

from flask import Blueprint, jsonify, request

from app.api.errors import NotFound, UnprocessableEntity
from app.api.schemas import DoctorCreateIn
from app.api.security import current_hospital_id, require_role
from app.infra.db import get_session
from app.models import Doctor
from app.services.doctors import (
    create_doctor,
    doctor_stats,
    doctor_view,
    doctors_view_batch,
    list_doctors,
    toggle_affiliation,
    update_doctor,
)
from app.services.unavailabilities import (
    create_unavailability,
    delete_unavailability,
    list_unavailabilities,
)

bp = Blueprint("doctors", __name__, url_prefix="/doctors")


@bp.get("")
@require_role("coordenador")
def index():  # type: ignore[no-untyped-def]
    raw = request.args.get("specialty_id")
    try:
        specialty_id = int(raw) if raw is not None else None
    except ValueError as exc:
        raise UnprocessableEntity("specialty_id must be an integer") from exc

    session = get_session()
    doctors = list_doctors(session, specialty_id=specialty_id)
    return jsonify({"doctors": doctors_view_batch(session, doctors)})


@bp.post("")
@require_role("coordenador")
def create():  # type: ignore[no-untyped-def]
    body = DoctorCreateIn.model_validate(request.get_json(force=True, silent=True) or {})
    session = get_session()
    doctor = create_doctor(
        session,
        name=body.name,
        email=body.email,
        password=body.password,
        phone=body.phone,
        specialty_ids=body.specialty_ids,
        hospital_ids=body.hospital_ids,
    )
    return jsonify({"doctor": doctor_view(session, doctor)}), 201


@bp.get("/<uuid:doctor_id>")
@require_role("coordenador")
def show(doctor_id):  # type: ignore[no-untyped-def]
    session = get_session()
    doctor = session.get(Doctor, doctor_id)
    if doctor is None:
        raise NotFound("doctor not found")
    return jsonify({"doctor": doctor_view(session, doctor)})


@bp.patch("/<uuid:doctor_id>")
@require_role("coordenador")
def patch(doctor_id):  # type: ignore[no-untyped-def]
    session = get_session()
    doctor = session.get(Doctor, doctor_id)
    if doctor is None:
        raise NotFound("doctor not found")

    body = request.get_json(force=True, silent=True) or {}
    from app.services.doctors import _UNSET

    kwargs: dict = {}
    if "name" in body:
        kwargs["name"] = body["name"]
    if "phone" in body:
        kwargs["phone"] = body["phone"]
    else:
        kwargs["phone"] = _UNSET
    if "specialty_ids" in body:
        kwargs["specialty_ids"] = body["specialty_ids"]

    doctor = update_doctor(session, doctor, **kwargs)
    return jsonify({"doctor": doctor_view(session, doctor)})


@bp.post("/<uuid:doctor_id>/deactivate")
@require_role("coordenador")
def deactivate(doctor_id):  # type: ignore[no-untyped-def]
    session = get_session()
    doctor = session.get(Doctor, doctor_id)
    if doctor is None:
        raise NotFound("doctor not found")
    hospital_id = current_hospital_id()
    toggle_affiliation(session, doctor.id, hospital_id, active=False)
    return jsonify({"status": "deactivated"})


@bp.post("/<uuid:doctor_id>/activate")
@require_role("coordenador")
def activate(doctor_id):  # type: ignore[no-untyped-def]
    session = get_session()
    doctor = session.get(Doctor, doctor_id)
    if doctor is None:
        raise NotFound("doctor not found")
    hospital_id = current_hospital_id()
    toggle_affiliation(session, doctor.id, hospital_id, active=True)
    return jsonify({"status": "activated"})


@bp.get("/<uuid:doctor_id>/stats")
@require_role("coordenador")
def stats(doctor_id):  # type: ignore[no-untyped-def]
    session = get_session()
    doctor = session.get(Doctor, doctor_id)
    if doctor is None:
        raise NotFound("doctor not found")
    return jsonify({"stats": doctor_stats(session, doctor.id)})


@bp.get("/<uuid:doctor_id>/unavailabilities")
@require_role("coordenador")
def unavailabilities_list(doctor_id):  # type: ignore[no-untyped-def]
    session = get_session()
    doctor = session.get(Doctor, doctor_id)
    if doctor is None:
        raise NotFound("doctor not found")
    items = list_unavailabilities(session, doctor.id)
    return jsonify({
        "unavailabilities": [
            {
                "id": str(u.id),
                "starts_at": u.starts_at.isoformat(),
                "ends_at": u.ends_at.isoformat(),
                "reason": u.reason,
            }
            for u in items
        ]
    })


@bp.post("/<uuid:doctor_id>/unavailabilities")
@require_role("coordenador")
def unavailabilities_create(doctor_id):  # type: ignore[no-untyped-def]
    session = get_session()
    doctor = session.get(Doctor, doctor_id)
    if doctor is None:
        raise NotFound("doctor not found")

    body = request.get_json(force=True, silent=True) or {}
    from datetime import datetime

    try:
        starts_at = datetime.fromisoformat(body["starts_at"])
        ends_at = datetime.fromisoformat(body["ends_at"])
    except (KeyError, ValueError) as exc:
        raise UnprocessableEntity("starts_at and ends_at are required (ISO format)") from exc

    u_list = create_unavailability(
        session, doctor.id, starts_at=starts_at, ends_at=ends_at, reason=body.get("reason"), repeat_weeks=body.get("repeat_weeks", 0)
    )
    return jsonify({
        "unavailabilities": [
            {
                "id": str(u.id),
                "starts_at": u.starts_at.isoformat(),
                "ends_at": u.ends_at.isoformat(),
                "reason": u.reason,
            }
            for u in u_list
        ]
    }), 201


@bp.delete("/<uuid:doctor_id>/unavailabilities/<uuid:unavail_id>")
@require_role("coordenador")
def unavailabilities_delete(doctor_id, unavail_id):  # type: ignore[no-untyped-def]
    session = get_session()
    delete_unavailability(session, unavail_id, doctor_id=doctor_id)
    return "", 204
