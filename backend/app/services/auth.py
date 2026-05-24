"""Serviço de autenticação: troca credenciais por um JWT assinado.

Erro idêntico para conta inexistente e senha errada — evita enumeração
de e-mails. O `now` é injetável só pra facilitar teste determinístico.
"""
from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import select

from app.api.errors import Unauthorized
from app.infra import jwt
from app.infra.hashing import verify_password
from app.models import Account

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


def authenticate(
    session: Session,
    *,
    email: str,
    password: str,
    jwt_secret: str,
    expires_minutes: int,
    now: datetime | None = None,
) -> tuple[Account, str]:
    account = session.scalar(select(Account).where(Account.email == email))
    if account is None or not verify_password(password, account.password_hash):
        raise Unauthorized("invalid credentials")
    token = jwt.sign(
        account_id=account.id,
        role=account.role,
        hospital_id=account.hospital_id,
        secret=jwt_secret,
        expires_minutes=expires_minutes,
        now=now,
    )
    return account, token
