"""Área do médico: perfil (leitura enriquecida + edição) e gestão das
próprias indisponibilidades. Regra-chave: médico edita nome/telefone, NÃO
especialidades (credencial — só a coordenadora altera).
"""

from __future__ import annotations

from tests.conftest import auth_header, login, seed_doctor


def _doctor_token(client, session, hospital, *, specialties=(1, 2)):
    seed_doctor(
        session,
        name="Dr. Me",
        email="me@t.test",
        specialty_ids=list(specialties),
        hospital_ids=[hospital.id],
    )
    return login(client, "me@t.test", "senha-medico")


def test_get_profile_is_enriched(client, session, hospital) -> None:
    token = _doctor_token(client, session, hospital)
    resp = client.get("/me/profile", headers=auth_header(token))
    assert resp.status_code == 200
    profile = resp.get_json()["profile"]
    assert profile["name"] == "Dr. Me"
    assert profile["email"] == "me@t.test"
    assert {s["id"] for s in profile["specialties"]} == {1, 2}
    assert any(h["status"] == "active" for h in profile["hospitals"])


def test_patch_profile_changes_name_not_specialties(client, session, hospital) -> None:
    token = _doctor_token(client, session, hospital)
    resp = client.patch(
        "/me/profile",
        headers=auth_header(token),
        json={"name": "Dr. Renomeado", "specialty_ids": [5]},
    )
    assert resp.status_code == 200

    profile = client.get("/me/profile", headers=auth_header(token)).get_json()["profile"]
    assert profile["name"] == "Dr. Renomeado"
    assert {s["id"] for s in profile["specialties"]} == {1, 2}  # NÃO mudou


def test_doctor_manages_own_unavailabilities(client, session, hospital) -> None:
    token = _doctor_token(client, session, hospital)
    body = {
        "starts_at": "2030-02-01T08:00:00+00:00",
        "ends_at": "2030-02-01T20:00:00+00:00",
        "reason": "viagem",
    }
    created = client.post("/me/unavailabilities", headers=auth_header(token), json=body)
    assert created.status_code == 201
    items = created.get_json()["unavailabilities"]
    assert len(items) == 1
    uid = items[0]["id"]

    listing = client.get("/me/unavailabilities", headers=auth_header(token)).get_json()
    assert len(listing["unavailabilities"]) == 1

    assert (
        client.delete(f"/me/unavailabilities/{uid}", headers=auth_header(token)).status_code == 204
    )
    after = client.get("/me/unavailabilities", headers=auth_header(token)).get_json()
    assert after["unavailabilities"] == []


def test_doctor_unavailability_repeat_weeks(client, session, hospital) -> None:
    token = _doctor_token(client, session, hospital)
    body = {
        "starts_at": "2030-03-02T08:00:00+00:00",
        "ends_at": "2030-03-02T20:00:00+00:00",
        "repeat_weeks": 2,
    }
    created = client.post("/me/unavailabilities", headers=auth_header(token), json=body)
    assert created.status_code == 201
    assert len(created.get_json()["unavailabilities"]) == 3  # base + 2
