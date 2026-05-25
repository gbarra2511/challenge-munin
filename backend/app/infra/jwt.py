"""JWT sign/verify usando PyJWT.

Camada pura: recebe `secret` e `now` como parâmetros pra ser
testável sem freezegun nem mock global. O wrapper que usa Settings
mora na camada de serviço/api.

Payload (claims):
- sub: account_id (UUID como string)
- role: "coordenador" | "medico"
- hospital_id: UUID|None (None para médicos — ver PLANO §4.7 dec. 2)
- iat: emissão (epoch seconds)
- exp: expiração (epoch seconds)
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

import jwt as _pyjwt

_ALGORITHM = "HS256"


class InvalidToken(Exception):
    """Token assinado errado, expirado, malformado ou alterado."""


def sign(
    *,
    account_id: UUID,
    role: str,
    hospital_id: UUID | None,
    secret: str,
    expires_minutes: int,
    now: datetime | None = None,
) -> str:
    issued = now or datetime.now(UTC)
    expires = issued + timedelta(minutes=expires_minutes)
    payload: dict[str, Any] = {
        "sub": str(account_id),
        "role": role,
        "hospital_id": str(hospital_id) if hospital_id else None,
        "iat": int(issued.timestamp()),
        "exp": int(expires.timestamp()),
    }
    return _pyjwt.encode(payload, secret, algorithm=_ALGORITHM)


def verify(token: str, *, secret: str, now: datetime | None = None) -> dict[str, Any]:
    # `now` injetável (simétrico com sign): PyJWT não aceita relógio externo,
    # então decodificamos sem checar exp e validamos a expiração à mão.
    try:
        claims = _pyjwt.decode(
            token,
            secret,
            algorithms=[_ALGORITHM],
            options={"verify_exp": False},
        )
    except _pyjwt.PyJWTError as exc:
        raise InvalidToken(str(exc)) from exc

    current = int((now or datetime.now(UTC)).timestamp())
    exp = claims.get("exp")
    if exp is not None and current >= exp:
        raise InvalidToken("token expired")
    return claims
