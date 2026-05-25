"""Ações da coordenadora sobre plantões: cancelar, ampliar pool, listar
ofertas. Cobre transições, supersede, escopo por hospital e guard de papel.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import select

from app.models import AuditEvent, Hospital, ShiftOffer
from tests.conftest import auth_header, login, seed_doctor, seed_shift

FAR = datetime(2026, 9, 1, 8, 0, tzinfo=UTC)
FAR_END = FAR + timedelta(hours=12)


def _coord(client) -> str:
    return login(client, "coord@central.test", "senha-coord")


def _offering_shift(session, hospital, *, status="offering", **kw):
    return seed_shift(
        session,
        hospital_id=hospital.id,
        starts_at=FAR,
        ends_at=FAR_END,
        status=status,
        current_batch=1,
        **kw,
    )


def test_cancel_shift_supersedes_offers_and_audits(client, session, coordinator, hospital) -> None:
    token = _coord(client)
    doc = seed_doctor(
        session, name="D1", email="d1@t.test", specialty_ids=[1], hospital_ids=[hospital.id]
    )
    shift = _offering_shift(session, hospital)
    session.add(
        ShiftOffer(
            shift_id=shift.id,
            doctor_id=doc.id,
            batch_number=1,
            status="pending",
            sent_at=FAR - timedelta(days=30),
            expires_at=FAR - timedelta(days=29),
        )
    )
    session.commit()

    resp = client.post(f"/shifts/{shift.id}/cancel", headers=auth_header(token))
    assert resp.status_code == 200, resp.get_json()
    assert resp.get_json()["shift"]["status"] == "cancelled"

    session.expire_all()
    offer = session.scalars(select(ShiftOffer).where(ShiftOffer.shift_id == shift.id)).one()
    assert offer.status == "superseded"
    events = session.scalars(
        select(AuditEvent).where(
            AuditEvent.shift_id == shift.id, AuditEvent.event_type == "shift.cancelled"
        )
    ).all()
    assert len(events) == 1


def test_cancel_shift_other_hospital_is_404(client, session, coordinator, hospital) -> None:
    token = _coord(client)
    other = Hospital(name="Outro")
    session.add(other)
    session.commit()
    shift = seed_shift(
        session,
        hospital_id=other.id,
        starts_at=FAR,
        ends_at=FAR_END,
        status="offering",
        current_batch=1,
    )
    resp = client.post(f"/shifts/{shift.id}/cancel", headers=auth_header(token))
    assert resp.status_code == 404


def test_expand_pool_sends_new_batch_excluding_already_offered(
    client, session, coordinator, hospital
) -> None:
    token = _coord(client)
    offered = seed_doctor(
        session, name="Offered", email="of@t.test", specialty_ids=[1], hospital_ids=[hospital.id]
    )
    fresh = seed_doctor(
        session, name="Fresh", email="fr@t.test", specialty_ids=[1], hospital_ids=[hospital.id]
    )
    shift = _offering_shift(session, hospital, status="needs_attention")
    session.add(
        ShiftOffer(
            shift_id=shift.id,
            doctor_id=offered.id,
            batch_number=1,
            status="expired",
            sent_at=FAR - timedelta(days=30),
            expires_at=FAR - timedelta(days=29),
        )
    )
    session.commit()

    resp = client.post(f"/shifts/{shift.id}/expand-pool", headers=auth_header(token))
    assert resp.status_code == 200, resp.get_json()
    body = resp.get_json()
    assert body["shift"]["status"] == "offering"
    assert body["new_offers"] == 1

    session.expire_all()
    new = session.scalars(
        select(ShiftOffer).where(
            ShiftOffer.shift_id == shift.id, ShiftOffer.batch_number == 2
        )
    ).all()
    assert len(new) == 1
    assert new[0].doctor_id == fresh.id


def test_expand_pool_rejects_non_needs_attention(client, session, coordinator, hospital) -> None:
    token = _coord(client)
    shift = _offering_shift(session, hospital)  # status=offering, não needs_attention
    resp = client.post(f"/shifts/{shift.id}/expand-pool", headers=auth_header(token))
    assert resp.status_code == 409


def test_get_shift_offers_returns_doctor_names(client, session, coordinator, hospital) -> None:
    token = _coord(client)
    doc = seed_doctor(
        session,
        name="Dra. Lima",
        email="lima@t.test",
        specialty_ids=[1],
        hospital_ids=[hospital.id],
    )
    shift = _offering_shift(session, hospital)
    session.add(
        ShiftOffer(
            shift_id=shift.id,
            doctor_id=doc.id,
            batch_number=1,
            status="pending",
            sent_at=FAR - timedelta(days=1),
            expires_at=FAR,
        )
    )
    session.commit()

    resp = client.get(f"/shifts/{shift.id}/offers", headers=auth_header(token))
    assert resp.status_code == 200
    offers = resp.get_json()["offers"]
    assert len(offers) == 1
    assert offers[0]["doctor"]["name"] == "Dra. Lima"
    assert offers[0]["batch_number"] == 1


def test_shift_ranking_exposes_breakdown_and_offered_flag(
    client, session, coordinator, hospital
) -> None:
    token = _coord(client)
    top = seed_doctor(
        session, name="Top", email="top@t.test", specialty_ids=[1], hospital_ids=[hospital.id]
    )
    seed_doctor(
        session, name="Other", email="oth@t.test", specialty_ids=[1], hospital_ids=[hospital.id]
    )
    shift = _offering_shift(session, hospital)
    # `top` já recebeu oferta neste plantão e respondeu (gera histórico/score).
    session.add(
        ShiftOffer(
            shift_id=shift.id,
            doctor_id=top.id,
            batch_number=1,
            status="accepted",
            sent_at=FAR - timedelta(days=10),
            expires_at=FAR - timedelta(days=10) + timedelta(minutes=30),
            responded_at=FAR - timedelta(days=10) + timedelta(minutes=3),
        )
    )
    session.commit()

    resp = client.get(f"/shifts/{shift.id}/ranking", headers=auth_header(token))
    assert resp.status_code == 200, resp.get_json()
    ranking = resp.get_json()["ranking"]
    assert {r["doctor"]["name"] for r in ranking} == {"Top", "Other"}

    by_name = {r["doctor"]["name"]: r for r in ranking}
    assert by_name["Top"]["already_offered"] is True
    assert by_name["Other"]["already_offered"] is False
    # breakdown explicável presente e serializável (sem Decimal).
    bd = by_name["Top"]["breakdown"]
    assert bd["acceptance_rate"] == 1.0
    assert bd["avg_response_min"] == 3.0
    assert set(bd["scores"]) == {"acceptance", "recency", "load", "response"}


def test_shift_actions_require_coordinator(client, session, doctor_account, hospital) -> None:
    token = login(client, "medico@central.test", "senha-medico")
    shift = _offering_shift(session, hospital)
    assert (
        client.post(f"/shifts/{shift.id}/cancel", headers=auth_header(token)).status_code == 403
    )
