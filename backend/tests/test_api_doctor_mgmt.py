"""Gestão de médicos pela coordenadora: editar, ativar/desativar (soft-delete
via afiliação) e métricas. CRUD básico de criação fica em test_api_doctors.py.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID

from app.models import ShiftOffer
from tests.conftest import auth_header, login, seed_shift


def _coord(client) -> str:
    return login(client, "coord@central.test", "senha-coord")


def _create_doctor(client, token, hospital, *, email="m@t.test", specialties=(1,)):
    return client.post(
        "/doctors",
        headers=auth_header(token),
        json={
            "name": "Dr. Inicial",
            "email": email,
            "password": "segredo123",
            "specialty_ids": list(specialties),
            "hospital_ids": [str(hospital.id)],
        },
    ).get_json()["doctor"]


def test_patch_doctor_updates_name_and_specialties(client, coordinator, hospital) -> None:
    token = _coord(client)
    created = _create_doctor(client, token, hospital, specialties=[1])

    resp = client.patch(
        f"/doctors/{created['id']}",
        headers=auth_header(token),
        json={"name": "Dr. Novo", "specialty_ids": [2, 3]},
    )
    assert resp.status_code == 200, resp.get_json()
    doctor = resp.get_json()["doctor"]
    assert doctor["name"] == "Dr. Novo"
    assert doctor["specialty_ids"] == [2, 3]


def test_deactivate_then_activate_toggles_affiliation(client, coordinator, hospital) -> None:
    token = _coord(client)
    created = _create_doctor(client, token, hospital)

    client.post(f"/doctors/{created['id']}/deactivate", headers=auth_header(token))
    after = client.get(f"/doctors/{created['id']}", headers=auth_header(token)).get_json()["doctor"]
    assert after["hospital_ids"] == []  # afiliação inativa some do view

    client.post(f"/doctors/{created['id']}/activate", headers=auth_header(token))
    back = client.get(f"/doctors/{created['id']}", headers=auth_header(token)).get_json()["doctor"]
    assert back["hospital_ids"] == [str(hospital.id)]


def test_doctor_stats_shape_for_doctor_without_history(client, coordinator, hospital) -> None:
    token = _coord(client)
    created = _create_doctor(client, token, hospital)

    resp = client.get(f"/doctors/{created['id']}/stats", headers=auth_header(token))
    assert resp.status_code == 200
    stats = resp.get_json()["stats"]
    for key in (
        "total_offers",
        "accepted",
        "declined",
        "expired",
        "acceptance_rate",
        "avg_response_min",
        "total_assignments",
    ):
        assert key in stats
    assert stats["total_offers"] == 0
    assert stats["acceptance_rate"] is None  # sem ofertas respondidas


def test_doctor_stats_serializes_response_time(client, session, coordinator, hospital) -> None:
    """Regressão: func.avg do Postgres devolve Decimal, que o jsonify do Flask
    não serializa. Médico com oferta respondida quebrava /stats com 500."""
    token = _coord(client)
    created = _create_doctor(client, token, hospital)
    doctor_id = UUID(created["id"])

    start = datetime(2026, 9, 1, 8, 0, tzinfo=UTC)
    shift = seed_shift(
        session, hospital_id=hospital.id, starts_at=start, ends_at=start + timedelta(hours=12)
    )
    sent = start - timedelta(days=10)
    session.add(
        ShiftOffer(
            shift_id=shift.id,
            doctor_id=doctor_id,
            batch_number=1,
            status="accepted",
            sent_at=sent,
            expires_at=sent + timedelta(minutes=30),
            responded_at=sent + timedelta(minutes=8),
        )
    )
    session.commit()

    resp = client.get(f"/doctors/{created['id']}/stats", headers=auth_header(token))
    assert resp.status_code == 200, resp.get_json()
    stats = resp.get_json()["stats"]
    assert stats["accepted"] == 1
    assert stats["avg_response_min"] == 8.0


def test_doctor_management_requires_coordinator(client, doctor_account) -> None:
    token = login(client, "medico@central.test", "senha-medico")
    assert client.get("/doctors", headers=auth_header(token)).status_code == 403
