"""Testes HTTP do médico: aceitar/recusar oferta e /me/offers."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select

from app.models import Hospital, ShiftAssignment, ShiftOffer
from tests.conftest import auth_header, login, seed_doctor, seed_shift


def _pending_offer(session, shift, doctor, *, now, expires_in_min=30):
    offer = ShiftOffer(
        shift_id=shift.id,
        doctor_id=doctor.id,
        batch_number=1,
        status="pending",
        sent_at=now,
        expires_at=now + timedelta(minutes=expires_in_min),
    )
    session.add(offer)
    session.commit()
    return offer


def test_accept_expired_offer_returns_410_and_marks_expired(client, hospital, session) -> None:
    now = datetime.now(UTC)
    doc = seed_doctor(
        session, name="Dr A", email="a@med.test", specialty_ids=[1], hospital_ids=[hospital.id]
    )
    shift = seed_shift(
        session,
        hospital_id=hospital.id,
        starts_at=now + timedelta(days=10),
        ends_at=now + timedelta(days=10, hours=12),
        status="offering",
        current_batch=1,
    )
    offer = ShiftOffer(
        shift_id=shift.id,
        doctor_id=doc.id,
        batch_number=1,
        status="pending",
        sent_at=now - timedelta(hours=2),
        expires_at=now - timedelta(hours=1),  # já expirou
    )
    session.add(offer)
    session.commit()

    token = login(client, "a@med.test", "senha-medico")
    resp = client.post(f"/offers/{offer.id}/accept", headers=auth_header(token))

    assert resp.status_code == 410
    assert resp.get_json()["error"]["code"] == "offer_expired"
    session.refresh(offer)
    session.refresh(shift)
    assert offer.status == "expired"
    assert shift.status == "offering"  # plantão segue aberto pra outros


def test_accept_happy_path_supersedes_others(client, hospital, session) -> None:
    now = datetime.now(UTC)
    winner = seed_doctor(
        session, name="Dr Win", email="win@med.test", specialty_ids=[1], hospital_ids=[hospital.id]
    )
    other = seed_doctor(
        session, name="Dr Oth", email="oth@med.test", specialty_ids=[1], hospital_ids=[hospital.id]
    )
    shift = seed_shift(
        session,
        hospital_id=hospital.id,
        starts_at=now + timedelta(days=10),
        ends_at=now + timedelta(days=10, hours=12),
        status="offering",
        current_batch=1,
    )
    win_offer = _pending_offer(session, shift, winner, now=now)
    oth_offer = _pending_offer(session, shift, other, now=now)

    token = login(client, "win@med.test", "senha-medico")
    resp = client.post(f"/offers/{win_offer.id}/accept", headers=auth_header(token))
    assert resp.status_code == 200
    assert resp.get_json()["status"] == "accepted"

    session.refresh(shift)
    session.refresh(oth_offer)
    assert shift.status == "accepted"
    assert oth_offer.status == "superseded"
    active = session.scalar(
        select(func.count())
        .select_from(ShiftAssignment)
        .where(ShiftAssignment.shift_id == shift.id, ShiftAssignment.status == "active")
    )
    assert active == 1


def test_accept_when_shift_already_accepted_returns_409(client, hospital, session) -> None:
    now = datetime.now(UTC)
    a = seed_doctor(
        session, name="Dr A", email="a@med.test", specialty_ids=[1], hospital_ids=[hospital.id]
    )
    b = seed_doctor(
        session, name="Dr B", email="b@med.test", specialty_ids=[1], hospital_ids=[hospital.id]
    )
    shift = seed_shift(
        session,
        hospital_id=hospital.id,
        starts_at=now + timedelta(days=10),
        ends_at=now + timedelta(days=10, hours=12),
        status="offering",
        current_batch=1,
    )
    offer_a = _pending_offer(session, shift, a, now=now)
    offer_b = _pending_offer(session, shift, b, now=now)

    token_a = login(client, "a@med.test", "senha-medico")
    first = client.post(f"/offers/{offer_a.id}/accept", headers=auth_header(token_a))
    assert first.status_code == 200

    # B tenta aceitar depois — oferta virou superseded → 409.
    token_b = login(client, "b@med.test", "senha-medico")
    resp = client.post(f"/offers/{offer_b.id}/accept", headers=auth_header(token_b))
    assert resp.status_code == 409


def test_decline_marks_offer_declined(client, hospital, session) -> None:
    now = datetime.now(UTC)
    doc = seed_doctor(
        session, name="Dr A", email="a@med.test", specialty_ids=[1], hospital_ids=[hospital.id]
    )
    shift = seed_shift(
        session,
        hospital_id=hospital.id,
        starts_at=now + timedelta(days=10),
        ends_at=now + timedelta(days=10, hours=12),
        status="offering",
        current_batch=1,
    )
    offer = _pending_offer(session, shift, doc, now=now)

    token = login(client, "a@med.test", "senha-medico")
    resp = client.post(f"/offers/{offer.id}/decline", headers=auth_header(token))
    assert resp.status_code == 200
    session.refresh(offer)
    assert offer.status == "declined"


def test_doctor_only_sees_offers_from_affiliated_hospitals(client, session) -> None:
    now = datetime.now(UTC)
    hospital_a = Hospital(name="Hospital A")
    hospital_b = Hospital(name="Hospital B")
    session.add_all([hospital_a, hospital_b])
    session.commit()

    # Médico afiliado SÓ ao A.
    doc = seed_doctor(
        session,
        name="Dr Único",
        email="doc@med.test",
        specialty_ids=[1],
        hospital_ids=[hospital_a.id],
    )
    shift_a = seed_shift(
        session,
        hospital_id=hospital_a.id,
        starts_at=now + timedelta(days=5),
        ends_at=now + timedelta(days=5, hours=12),
        status="offering",
        current_batch=1,
    )
    shift_b = seed_shift(
        session,
        hospital_id=hospital_b.id,
        starts_at=now + timedelta(days=5),
        ends_at=now + timedelta(days=5, hours=12),
        status="offering",
        current_batch=1,
    )
    legit = _pending_offer(session, shift_a, doc, now=now)
    leaked = _pending_offer(session, shift_b, doc, now=now)  # "vazamento" do B

    token = login(client, "doc@med.test", "senha-medico")
    resp = client.get("/me/offers", headers=auth_header(token))
    assert resp.status_code == 200
    ids = {o["id"] for o in resp.get_json()["offers"]}
    assert str(legit.id) in ids
    assert str(leaked.id) not in ids  # filtrado pela afiliação ativa
