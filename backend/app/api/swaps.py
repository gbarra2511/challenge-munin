"""Troca de plantão (swap).

Médico A pede (`POST /swaps`) e pode desistir (`POST /swaps/:id/cancel`).
Coordenação lista pendentes (`GET /swaps`), aprova ou recusa com motivo.
A listagem dos próprios pedidos e os candidatos elegíveis ficam no blueprint
`me` (visões do médico autenticado).
"""

from __future__ import annotations

from flask import Blueprint, jsonify, request

from app.api.notify import flush_notifications
from app.api.schemas import SwapDecisionIn, SwapRequestIn
from app.api.security import current_account_id, current_hospital_id, require_role
from app.infra.db import get_session
from app.services.doctors import resolve_doctor
from app.services.swaps import (
    approve_swap,
    cancel_swap,
    list_pending_swaps,
    reject_swap,
    request_swap,
)

bp = Blueprint("swaps", __name__, url_prefix="/swaps")


@bp.post("")
@require_role("medico")
def create():  # type: ignore[no-untyped-def]
    body = SwapRequestIn.model_validate(request.get_json(force=True, silent=True) or {})
    session = get_session()
    doctor = resolve_doctor(session, current_account_id())
    result = request_swap(
        session,
        doctor_id=doctor.id,
        assignment_id=body.assignment_id,
        to_doctor_id=body.to_doctor_id,
    )
    flush_notifications(session)  # entrega o WhatsApp do pedido na hora (cron = fallback)
    return jsonify(result), 201


@bp.post("/<uuid:swap_id>/cancel")
@require_role("medico")
def cancel(swap_id):  # type: ignore[no-untyped-def]
    session = get_session()
    doctor = resolve_doctor(session, current_account_id())
    result = cancel_swap(session, swap_id=swap_id, doctor_id=doctor.id)
    return jsonify(result)


@bp.get("")
@require_role("coordenador")
def index():  # type: ignore[no-untyped-def]
    session = get_session()
    status = request.args.get("status", "pending")
    swaps = list_pending_swaps(session, hospital_id=current_hospital_id(), status=status)
    return jsonify({"swaps": swaps})


@bp.post("/<uuid:swap_id>/approve")
@require_role("coordenador")
def approve(swap_id):  # type: ignore[no-untyped-def]
    body = SwapDecisionIn.model_validate(request.get_json(force=True, silent=True) or {})
    session = get_session()
    result = approve_swap(
        session,
        swap_id=swap_id,
        hospital_id=current_hospital_id(),
        actor_id=current_account_id(),
        reason=body.reason,
    )
    flush_notifications(session)  # notifica A e B na hora
    return jsonify(result)


@bp.post("/<uuid:swap_id>/reject")
@require_role("coordenador")
def reject(swap_id):  # type: ignore[no-untyped-def]
    body = SwapDecisionIn.model_validate(request.get_json(force=True, silent=True) or {})
    session = get_session()
    result = reject_swap(
        session,
        swap_id=swap_id,
        hospital_id=current_hospital_id(),
        actor_id=current_account_id(),
        reason=body.reason,
    )
    flush_notifications(session)  # notifica A (recusa + motivo) na hora
    return jsonify(result)
