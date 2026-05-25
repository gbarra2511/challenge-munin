"""Autenticação por Bearer token e autorização por papel.

`require_role(*roles)` extrai o JWT do header `Authorization: Bearer`,
valida, e guarda os claims em `flask.g`. Sem papéis → só exige token
válido. Handlers leem o ator via `current_claims()`.
"""

from __future__ import annotations

import hmac
from collections.abc import Callable
from functools import wraps
from typing import Any
from uuid import UUID

from flask import current_app, g, request

from app.api.errors import Forbidden, Unauthorized
from app.infra import jwt


def _extract_bearer() -> str:
    header = request.headers.get("Authorization", "")
    scheme, _, token = header.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise Unauthorized("missing or malformed Authorization header")
    return token


def require_role(*roles: str) -> Callable:
    def decorator(fn: Callable) -> Callable:
        @wraps(fn)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            token = _extract_bearer()
            try:
                claims = jwt.verify(token, secret=current_app.config["JWT_SECRET"])
            except jwt.InvalidToken as exc:
                raise Unauthorized("invalid or expired token") from exc
            if roles and claims.get("role") not in roles:
                raise Forbidden("insufficient role for this action")
            g.claims = claims
            return fn(*args, **kwargs)

        return wrapper

    return decorator


def require_secret(config_key: str) -> Callable:
    """Protege endpoints de máquina (tick, seed) com um segredo compartilhado
    via Bearer — não JWT. Comparação em tempo constante."""

    def decorator(fn: Callable) -> Callable:
        @wraps(fn)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            token = _extract_bearer()
            expected = current_app.config[config_key]
            if not hmac.compare_digest(token, expected):
                raise Unauthorized("invalid secret")
            return fn(*args, **kwargs)

        return wrapper

    return decorator


def current_claims() -> dict[str, Any]:
    return g.claims


def current_account_id() -> UUID:
    return UUID(g.claims["sub"])


def current_hospital_id() -> UUID | None:
    raw = g.claims.get("hospital_id")
    return UUID(raw) if raw else None
