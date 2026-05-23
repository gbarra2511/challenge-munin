"""Testes do bcrypt wrapper. rounds=4 pra rodar rápido (não usar em prod)."""
from __future__ import annotations

from app.infra.hashing import hash_password, verify_password

ROUNDS = 4  # mínimo aceito pelo bcrypt; rápido pra teste.


def test_hash_differs_from_plaintext() -> None:
    hashed = hash_password("super-secret", rounds=ROUNDS)
    assert hashed != "super-secret"
    assert hashed.startswith("$2b$")


def test_verify_correct_password() -> None:
    hashed = hash_password("super-secret", rounds=ROUNDS)
    assert verify_password("super-secret", hashed) is True


def test_verify_wrong_password() -> None:
    hashed = hash_password("super-secret", rounds=ROUNDS)
    assert verify_password("wrong-password", hashed) is False


def test_same_password_produces_different_hashes() -> None:
    # Salt aleatório a cada chamada → mesmo plaintext, hashes distintos.
    h1 = hash_password("same", rounds=ROUNDS)
    h2 = hash_password("same", rounds=ROUNDS)
    assert h1 != h2
    assert verify_password("same", h1)
    assert verify_password("same", h2)


def test_unicode_password() -> None:
    pwd = "señ@-ção-密码-🔑"
    hashed = hash_password(pwd, rounds=ROUNDS)
    assert verify_password(pwd, hashed) is True
    assert verify_password(pwd + "x", hashed) is False
