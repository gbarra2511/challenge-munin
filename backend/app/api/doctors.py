"""Blueprint de médicos (CRUD básico — coordenador)."""
from __future__ import annotations

from flask import Blueprint, jsonify, request

from app.api.errors import NotFound, UnprocessableEntity
from app.api.schemas import DoctorCreateIn
from app.api.security import require_role
from app.infra.db import get_session
from app.models import Doctor
from app.services.doctors import create_doctor, doctor_view, list_doctors

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
    return jsonify({"doctors": [doctor_view(session, d) for d in doctors]})


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
