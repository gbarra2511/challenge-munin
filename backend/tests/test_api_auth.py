"""Testes de /health, /auth/login e /auth/me + guards de papel."""

from __future__ import annotations

from tests.conftest import auth_header, login


def test_health(client) -> None:
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.get_json() == {"status": "ok"}


def test_login_success_returns_token_and_account(client, coordinator) -> None:
    resp = client.post(
        "/auth/login", json={"email": "coord@central.test", "password": "senha-coord"}
    )
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["token"].count(".") == 2
    assert body["account"]["role"] == "coordenador"
    assert body["account"]["hospital_id"] == str(coordinator.hospital_id)


def test_login_wrong_password_is_401(client, coordinator) -> None:
    resp = client.post("/auth/login", json={"email": "coord@central.test", "password": "errada"})
    assert resp.status_code == 401
    assert resp.get_json()["error"]["code"] == "unauthorized"


def test_login_unknown_email_is_401(client, coordinator) -> None:
    # Mesma resposta que senha errada → não vaza existência da conta.
    resp = client.post("/auth/login", json={"email": "ninguem@x.test", "password": "qualquer"})
    assert resp.status_code == 401


def test_login_invalid_body_is_422(client) -> None:
    resp = client.post("/auth/login", json={"email": "x"})
    assert resp.status_code == 422
    assert resp.get_json()["error"]["code"] == "validation_error"


def test_me_without_token_is_401(client) -> None:
    resp = client.get("/auth/me")
    assert resp.status_code == 401


def test_me_with_garbage_token_is_401(client) -> None:
    resp = client.get("/auth/me", headers=auth_header("not-a-jwt"))
    assert resp.status_code == 401


def test_me_returns_account(client, coordinator) -> None:
    token = login(client, "coord@central.test", "senha-coord")
    resp = client.get("/auth/me", headers=auth_header(token))
    assert resp.status_code == 200
    assert resp.get_json()["account"]["email"] == "coord@central.test"


def test_medico_forbidden_on_coordinator_route(client, doctor_account) -> None:
    token = login(client, "medico@central.test", "senha-medico")
    resp = client.get("/doctors", headers=auth_header(token))
    assert resp.status_code == 403
    assert resp.get_json()["error"]["code"] == "forbidden"
