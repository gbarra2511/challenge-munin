"""Ações do médico sobre uma oferta: aceitar e recusar."""
from __future__ import annotations

from flask import Blueprint, jsonify

from app.api.security import current_account_id, require_role
from app.infra.db import get_session
from app.services.doctors import resolve_doctor
from app.services.offers import accept_offer, decline_offer

bp = Blueprint("offers", __name__, url_prefix="/offers")


@bp.post("/<uuid:offer_id>/accept")
@require_role("medico")
def accept(offer_id):  # type: ignore[no-untyped-def]
    session = get_session()
    doctor = resolve_doctor(session, current_account_id())
    result = accept_offer(session, offer_id=offer_id, doctor_id=doctor.id)
    return jsonify(result)


@bp.post("/<uuid:offer_id>/decline")
@require_role("medico")
def decline(offer_id):  # type: ignore[no-untyped-def]
    session = get_session()
    doctor = resolve_doctor(session, current_account_id())
    result = decline_offer(session, offer_id=offer_id, doctor_id=doctor.id)
    return jsonify(result)
