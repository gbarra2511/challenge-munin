"""Endpoints de máquina: o tick do pipeline. Protegido por TICK_SECRET.

Além de avançar o pipeline de ofertas, o tick drena o outbox de notificação
(`dispatch_pending`) — reusa o mesmo cron, sem worker novo.
"""

from __future__ import annotations

from flask import Blueprint, current_app, jsonify

from app.api.security import require_secret
from app.infra.db import get_session
from app.infra.notifier import get_notifier
from app.services.notifications import dispatch_pending
from app.services.offers import run_tick

bp = Blueprint("jobs", __name__, url_prefix="/jobs")


@bp.post("/tick")
@require_secret("TICK_SECRET")
def tick():  # type: ignore[no-untyped-def]
    session = get_session()
    tick_stats = run_tick(session)
    dispatch_stats = dispatch_pending(
        session,
        notifier=get_notifier(current_app.config),
        link_base=current_app.config.get("FRONTEND_URL", ""),
    )
    return jsonify({"tick": tick_stats, "dispatch": dispatch_stats})
