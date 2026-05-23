"""Testes do wrapper JWT. now injetado → sem freezegun."""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from app.infra.jwt import InvalidToken, sign, verify

SECRET = "test-secret-with-at-least-32-bytes-do-not-use-in-prod"


def test_sign_returns_jwt_string() -> None:
    token = sign(
        account_id=uuid4(),
        role="medico",
        hospital_id=None,
        secret=SECRET,
        expires_minutes=60,
    )
    # JWTs HS256 têm 3 segmentos separados por ponto.
    assert token.count(".") == 2


def test_verify_returns_claims() -> None:
    account_id = uuid4()
    hospital_id = uuid4()
    token = sign(
        account_id=account_id,
        role="coordenador",
        hospital_id=hospital_id,
        secret=SECRET,
        expires_minutes=60,
    )
    claims = verify(token, secret=SECRET)
    assert claims["sub"] == str(account_id)
    assert claims["role"] == "coordenador"
    assert claims["hospital_id"] == str(hospital_id)
    assert "iat" in claims
    assert "exp" in claims


def test_verify_medico_has_null_hospital() -> None:
    token = sign(
        account_id=uuid4(),
        role="medico",
        hospital_id=None,
        secret=SECRET,
        expires_minutes=60,
    )
    claims = verify(token, secret=SECRET)
    assert claims["hospital_id"] is None


def test_verify_expired_token_raises() -> None:
    # Emite no passado com janela curta → já está expirado quando verifica.
    past = datetime.now(UTC) - timedelta(hours=2)
    token = sign(
        account_id=uuid4(),
        role="medico",
        hospital_id=None,
        secret=SECRET,
        expires_minutes=60,
        now=past,
    )
    with pytest.raises(InvalidToken):
        verify(token, secret=SECRET)


def test_verify_wrong_secret_raises() -> None:
    token = sign(
        account_id=uuid4(),
        role="medico",
        hospital_id=None,
        secret=SECRET,
        expires_minutes=60,
    )
    with pytest.raises(InvalidToken):
        verify(token, secret="wrong-secret")


def test_verify_malformed_raises() -> None:
    with pytest.raises(InvalidToken):
        verify("not-a-real-token", secret=SECRET)


def test_exp_is_iat_plus_window() -> None:
    issued = datetime(2026, 5, 23, 12, 0, 0, tzinfo=UTC)
    token = sign(
        account_id=uuid4(),
        role="medico",
        hospital_id=None,
        secret=SECRET,
        expires_minutes=30,
        now=issued,
    )
    claims = verify(token, secret=SECRET)
    assert claims["exp"] - claims["iat"] == 30 * 60
