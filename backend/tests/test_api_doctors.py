"""Testes do CRUD de médicos (coordenador)."""
from __future__ import annotations

from tests.conftest import auth_header, login


def _coord_token(client) -> str:
    return login(client, "coord@central.test", "senha-coord")


def test_create_doctor(client, coordinator, hospital) -> None:
    token = _coord_token(client)
    resp = client.post(
        "/doctors",
        headers=auth_header(token),
        json={
            "name": "Dra. Ana",
            "email": "ana@med.test",
            "password": "segredo123",
            "specialty_ids": [1, 2],
            "hospital_ids": [str(hospital.id)],
        },
    )
    assert resp.status_code == 201, resp.get_json()
    doctor = resp.get_json()["doctor"]
    assert doctor["name"] == "Dra. Ana"
    assert doctor["specialty_ids"] == [1, 2]
    assert doctor["hospital_ids"] == [str(hospital.id)]
    assert doctor["account_id"] is not None


def test_create_doctor_can_login(client, coordinator) -> None:
    token = _coord_token(client)
    client.post(
        "/doctors",
        headers=auth_header(token),
        json={
            "name": "Dr. Bob",
            "email": "bob@med.test",
            "password": "segredo123",
            "specialty_ids": [1],
        },
    )
    login_resp = client.post(
        "/auth/login", json={"email": "bob@med.test", "password": "segredo123"}
    )
    assert login_resp.status_code == 200
    assert login_resp.get_json()["account"]["role"] == "medico"


def test_create_doctor_duplicate_email_is_409(client, coordinator) -> None:
    token = _coord_token(client)
    payload = {
        "name": "Dr. Dup",
        "email": "dup@med.test",
        "password": "segredo123",
        "specialty_ids": [1],
    }
    assert client.post("/doctors", headers=auth_header(token), json=payload).status_code == 201
    resp = client.post("/doctors", headers=auth_header(token), json=payload)
    assert resp.status_code == 409
    assert resp.get_json()["error"]["code"] == "conflict"


def test_create_doctor_unknown_specialty_is_422(client, coordinator) -> None:
    token = _coord_token(client)
    resp = client.post(
        "/doctors",
        headers=auth_header(token),
        json={
            "name": "Dr. X",
            "email": "x@med.test",
            "password": "segredo123",
            "specialty_ids": [999],
        },
    )
    assert resp.status_code == 422
    assert resp.get_json()["error"]["details"]["missing"] == [999]


def test_list_and_get_doctor(client, coordinator, hospital) -> None:
    token = _coord_token(client)
    created = client.post(
        "/doctors",
        headers=auth_header(token),
        json={
            "name": "Dra. Ana",
            "email": "ana@med.test",
            "password": "segredo123",
            "specialty_ids": [3],
        },
    ).get_json()["doctor"]

    listing = client.get("/doctors", headers=auth_header(token))
    assert listing.status_code == 200
    assert any(d["id"] == created["id"] for d in listing.get_json()["doctors"])

    one = client.get(f"/doctors/{created['id']}", headers=auth_header(token))
    assert one.status_code == 200
    assert one.get_json()["doctor"]["name"] == "Dra. Ana"


def test_list_doctors_filter_by_specialty(client, coordinator) -> None:
    token = _coord_token(client)
    for email, sid in [("a@med.test", 1), ("b@med.test", 5)]:
        client.post(
            "/doctors",
            headers=auth_header(token),
            json={
                "name": email,
                "email": email,
                "password": "segredo123",
                "specialty_ids": [sid],
            },
        )
    resp = client.get("/doctors?specialty_id=5", headers=auth_header(token))
    emails = [d["name"] for d in resp.get_json()["doctors"]]
    assert "b@med.test" in emails
    assert "a@med.test" not in emails


def test_get_missing_doctor_is_404(client, coordinator) -> None:
    token = _coord_token(client)
    resp = client.get(
        "/doctors/00000000-0000-0000-0000-000000000000", headers=auth_header(token)
    )
    assert resp.status_code == 404
