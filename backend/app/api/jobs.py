"""Endpoints de máquina: o tick do pipeline. Protegido por TICK_SECRET."""

from __future__ import annotations

from flask import Blueprint, jsonify

from app.api.security import require_secret
from app.infra.db import get_session
from app.services.offers import run_tick

bp = Blueprint("jobs", __name__, url_prefix="/jobs")


@bp.post("/tick")
@require_secret("TICK_SECRET")
def tick():  # type: ignore[no-untyped-def]
    stats = run_tick(get_session())
    return jsonify({"tick": stats})
