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
from datetime import datetime
from uuid import UUID

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from app import create_app
from app.infra.config import Settings
from app.infra.hashing import hash_password
from app.models import (
    Account,
    Doctor,
    DoctorHospitalAffiliation,
    DoctorSpecialty,
    Hospital,
    Shift,
)

# Tabelas transacionais (tudo menos specialties, que vem da migração).
_TRUNCATE_TABLES = (
    "notifications, shift_assignments, shift_offers, swap_requests, audit_events, shifts, "
    "doctor_unavailabilities, doctor_hospital_affiliations, doctor_specialties, "
    "doctors, accounts, hospitals"
)

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


def seed_doctor(
    session,
    *,
    name: str,
    email: str,
    specialty_ids: list[int],
    hospital_ids: list[UUID],
    password: str = "senha-medico",
) -> Doctor:
    """Cria conta+médico+especialidades+afiliações ativas e commita."""
    account = Account(
        email=email,
        password_hash=hash_password(password),
        role="medico",
        hospital_id=None,
    )
    session.add(account)
    session.flush()
    doctor = Doctor(account_id=account.id, name=name)
    session.add(doctor)
    session.flush()
    for sid in specialty_ids:
        session.add(DoctorSpecialty(doctor_id=doctor.id, specialty_id=sid))
    for hid in hospital_ids:
        session.add(
            DoctorHospitalAffiliation(doctor_id=doctor.id, hospital_id=hid, status="active")
        )
    session.commit()
    return doctor


def seed_shift(
    session,
    *,
    hospital_id: UUID,
    starts_at: datetime,
    ends_at: datetime,
    specialty_id: int = 1,
    status: str = "open",
    rate_cents: int = 120000,
    batch_size: int = 3,
    batch_window_minutes: int = 30,
    escalate_hours_before: int = 6,
    current_batch: int = 0,
) -> Shift:
    shift = Shift(
        hospital_id=hospital_id,
        specialty_id=specialty_id,
        starts_at=starts_at,
        ends_at=ends_at,
        rate_cents=rate_cents,
        status=status,
        current_batch=current_batch,
        batch_size=batch_size,
        batch_window_minutes=batch_window_minutes,
        escalate_hours_before=escalate_hours_before,
        version=0,
    )
    session.add(shift)
    session.commit()
    return shift


def login(client, email: str, password: str) -> str:
    resp = client.post("/auth/login", json={"email": email, "password": password})
    assert resp.status_code == 200, resp.get_json()
    return resp.get_json()["token"]


def auth_header(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


# --- suporte ao teste de concorrência (conexões reais, sem savepoint) ------


def truncate_all(engine) -> None:
    with engine.begin() as conn:
        conn.execute(text(f"TRUNCATE {_TRUNCATE_TABLES} RESTART IDENTITY CASCADE"))


@pytest.fixture()
def real_engine():
    """Engine sem isolamento por savepoint — pro teste de aceite concorrente,
    onde duas transações reais precisam competir de verdade. Limpa antes e
    depois pra não interferir nos testes com savepoint."""
    eng = create_engine(TEST_DATABASE_URL, future=True)
    truncate_all(eng)
    yield eng
    truncate_all(eng)
    eng.dispose()
