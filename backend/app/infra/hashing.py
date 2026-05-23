"""Password hashing via bcrypt.

Pure boundary: recebe/devolve strings. Sem dependência de settings.
12 rounds é o padrão razoável pra produção (~250ms no laptop).
Testes podem reduzir via parâmetro pra rodar em ms.
"""
from __future__ import annotations

import bcrypt


def hash_password(plaintext: str, *, rounds: int = 12) -> str:
    salt = bcrypt.gensalt(rounds=rounds)
    return bcrypt.hashpw(plaintext.encode("utf-8"), salt).decode("utf-8")


def verify_password(plaintext: str, hashed: str) -> bool:
    return bcrypt.checkpw(plaintext.encode("utf-8"), hashed.encode("utf-8"))
