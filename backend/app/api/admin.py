"""Endpoints administrativos: seed de demo. Protegido por ADMIN_SECRET."""

from __future__ import annotations

from flask import Blueprint, current_app, jsonify

from app.api.security import require_secret
from app.infra.db import get_session
from app.services.seed import run_seed

bp = Blueprint("admin", __name__, url_prefix="/admin")


@bp.post("/seed")
@require_secret("ADMIN_SECRET")
def seed():  # type: ignore[no-untyped-def]
    result = run_seed(
        get_session(),
        defaults={
            "batch_size": current_app.config["DEFAULT_BATCH_SIZE"],
            "batch_window_minutes": current_app.config["DEFAULT_BATCH_WINDOW_MINUTES"],
            "escalate_hours_before": current_app.config["DEFAULT_ESCALATE_HOURS_BEFORE"],
        },
    )
    return jsonify(result)
