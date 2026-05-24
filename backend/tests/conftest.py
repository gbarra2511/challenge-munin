"""Fixtures de teste de API contra Postgres real.

Padrão de isolamento: cada teste abre uma transação externa numa conexão
e liga TODAS as sessões (de setup e as de request do app) a ela com
`join_transaction_mode="create_savepoint"`. O `commit()` dos handlers cai
num savepoint; no fim do teste o rollback da transação externa desfaz tudo.
Banco rápido, isolado, sem recriar schema por teste.

Pré-requisito: `munin_test` migrado (ver README/Makefile). URL sobrescrita
por TEST_DATABASE_URL.
"""
from __future__ import annotations

import os

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app import create_app
from app.infra.config import Settings
from app.infra.hashing import hash_password
from app.models import Account, Doctor, Hospital

TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql+psycopg://munin:munin@localhost:5432/munin_test",
)
JWT_SECRET = "test-secret-with-at-least-32-bytes-do-not-use-in-prod"


@pytest.fixture(scope="session")
def engine():
    eng = create_engine(TEST_DATABASE_URL, future=True)
    yield eng
    eng.dispose()


@pytest.fixture()
def db_connection(engine):
    conn = engine.connect()
    trans = conn.begin()
    yield conn
    trans.rollback()
    conn.close()


@pytest.fixture()
def session_factory(db_connection):
    return sessionmaker(
        bind=db_connection,
        future=True,
        expire_on_commit=False,
        join_transaction_mode="create_savepoint",
    )


@pytest.fixture()
def session(session_factory):
    s = session_factory()
    yield s
    s.close()


@pytest.fixture()
def app(session_factory):
    settings = Settings(
        database_url=TEST_DATABASE_URL,
        jwt_secret=JWT_SECRET,
        jwt_expires_minutes=720,
        cors_origins="http://localhost:3000",
    )
    return create_app(settings, session_factory=session_factory)


@pytest.fixture()
def client(app):
    return app.test_client()


# --- helpers de seed -------------------------------------------------------


@pytest.fixture()
def hospital(session) -> Hospital:
    h = Hospital(name="Hospital Central")
    session.add(h)
    session.commit()
    return h


@pytest.fixture()
def coordinator(session, hospital):
    account = Account(
        email="coord@central.test",
        password_hash=hash_password("senha-coord"),
        role="coordenador",
        hospital_id=hospital.id,
    )
    session.add(account)
    session.commit()
    return account


@pytest.fixture()
def doctor_account(session):
    account = Account(
        email="medico@central.test",
        password_hash=hash_password("senha-medico"),
        role="medico",
        hospital_id=None,
    )
    session.add(account)
    session.flush()
    doctor = Doctor(account_id=account.id, name="Dr. House")
    session.add(doctor)
    session.commit()
    return account


def login(client, email: str, password: str) -> str:
    resp = client.post("/auth/login", json={"email": email, "password": password})
    assert resp.status_code == 200, resp.get_json()
    return resp.get_json()["token"]


def auth_header(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}
