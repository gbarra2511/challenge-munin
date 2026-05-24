"""Blueprint de plantões (CRUD básico — coordenador, escopado ao hospital)."""
from __future__ import annotations

from flask import Blueprint, current_app, jsonify, request
from sqlalchemy import select

from app.api.errors import NotFound
from app.api.schemas import OfferCreateIn, ShiftCreateIn
from app.api.security import current_hospital_id, require_role
from app.infra.db import get_session
from app.models import AuditEvent, Shift
from app.services.offers import open_offers
from app.services.shifts import create_shift, list_shifts, shift_view

bp = Blueprint("shifts", __name__, url_prefix="/shifts")


def _load_own_shift(session, shift_id):  # type: ignore[no-untyped-def]
    shift = session.get(Shift, shift_id)
    # 404 (não 403) se for de outro hospital: não vaza existência.
    if shift is None or shift.hospital_id != current_hospital_id():
        raise NotFound("shift not found")
    return shift


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
    shift = _load_own_shift(session, shift_id)
    return jsonify({"shift": shift_view(shift)})


@bp.post("/<uuid:shift_id>/offer")
@require_role("coordenador")
def offer(shift_id):  # type: ignore[no-untyped-def]
    body = OfferCreateIn.model_validate(request.get_json(force=True, silent=True) or {})
    session = get_session()
    shift = _load_own_shift(session, shift_id)
    shift = open_offers(session, shift, doctor_ids=body.doctor_ids or None)
    return jsonify({"shift": shift_view(shift)})


@bp.get("/<uuid:shift_id>/audit")
@require_role("coordenador")
def audit(shift_id):  # type: ignore[no-untyped-def]
    session = get_session()
    shift = _load_own_shift(session, shift_id)
    events = session.scalars(
        select(AuditEvent)
        .where(AuditEvent.shift_id == shift.id)
        .order_by(AuditEvent.created_at, AuditEvent.id)
    )
    return jsonify(
        {
            "events": [
                {
                    "id": e.id,
                    "event_type": e.event_type,
                    "actor_type": e.actor_type,
                    "actor_id": str(e.actor_id) if e.actor_id else None,
                    "payload": e.payload,
                    "created_at": e.created_at.isoformat() if e.created_at else None,
                }
                for e in events
            ]
        }
    )
