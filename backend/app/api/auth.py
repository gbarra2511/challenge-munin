"""Blueprint de autenticação: login e perfil do ator autenticado."""

from __future__ import annotations

from flask import Blueprint, current_app, jsonify, request
from sqlalchemy import select

from app.api.errors import NotFound
from app.api.schemas import LoginIn
from app.api.security import current_account_id, require_role
from app.infra.db import get_session
from app.models import Account
from app.services.auth import authenticate

bp = Blueprint("auth", __name__, url_prefix="/auth")


def _account_view(account: Account) -> dict:
    return {
        "id": str(account.id),
        "email": account.email,
        "role": account.role,
        "hospital_id": str(account.hospital_id) if account.hospital_id else None,
    }


@bp.post("/login")
def login():  # type: ignore[no-untyped-def]
    body = LoginIn.model_validate(request.get_json(force=True, silent=True) or {})
    session = get_session()
    account, token = authenticate(
        session,
        email=body.email,
        password=body.password,
        jwt_secret=current_app.config["JWT_SECRET"],
        expires_minutes=current_app.config["JWT_EXPIRES_MINUTES"],
    )
    return jsonify({"token": token, "account": _account_view(account)})


@bp.get("/me")
@require_role()
def me():  # type: ignore[no-untyped-def]
    session = get_session()
    account = session.scalar(select(Account).where(Account.id == current_account_id()))
    if account is None:
        raise NotFound("account no longer exists")
    return jsonify({"account": _account_view(account)})
