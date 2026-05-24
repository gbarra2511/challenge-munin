"""Blueprint de plantões (CRUD básico — coordenador, escopado ao hospital)."""
from __future__ import annotations

from flask import Blueprint, current_app, jsonify, request

from app.api.errors import NotFound
from app.api.schemas import ShiftCreateIn
from app.api.security import current_hospital_id, require_role
from app.infra.db import get_session
from app.models import Shift
from app.services.shifts import create_shift, list_shifts, shift_view

bp = Blueprint("shifts", __name__, url_prefix="/shifts")


@bp.get("")
@require_role("coordenador")
def index():  # type: ignore[no-untyped-def]
    session = get_session()
    shifts = list_shifts(
        session,
        hospital_id=current_hospital_id(),
        status=request.args.get("status"),
    )
    return jsonify({"shifts": [shift_view(s) for s in shifts]})


@bp.post("")
@require_role("coordenador")
def create():  # type: ignore[no-untyped-def]
    body = ShiftCreateIn.model_validate(request.get_json(force=True, silent=True) or {})
    session = get_session()
    shift = create_shift(
        session,
        hospital_id=current_hospital_id(),
        specialty_id=body.specialty_id,
        starts_at=body.starts_at,
        ends_at=body.ends_at,
        rate_cents=body.rate_cents,
        batch_size=body.batch_size,
        batch_window_minutes=body.batch_window_minutes,
        escalate_hours_before=body.escalate_hours_before,
        defaults={
            "batch_size": current_app.config["DEFAULT_BATCH_SIZE"],
            "batch_window_minutes": current_app.config["DEFAULT_BATCH_WINDOW_MINUTES"],
            "escalate_hours_before": current_app.config["DEFAULT_ESCALATE_HOURS_BEFORE"],
        },
    )
    return jsonify({"shift": shift_view(shift)}), 201


@bp.get("/<uuid:shift_id>")
@require_role("coordenador")
def show(shift_id):  # type: ignore[no-untyped-def]
    session = get_session()
    shift = session.get(Shift, shift_id)
    # 404 (não 403) se for de outro hospital: não vaza existência entre hospitais.
    if shift is None or shift.hospital_id != current_hospital_id():
        raise NotFound("shift not found")
    return jsonify({"shift": shift_view(shift)})
