"""Testes do CRUD de plantões (coordenador, escopado ao hospital)."""
from __future__ import annotations

from app.infra.hashing import hash_password
from app.models import Account, Hospital
from tests.conftest import auth_header, login


def _coord_token(client) -> str:
    return login(client, "coord@central.test", "senha-coord")


def _shift_payload(**overrides) -> dict:
    payload = {
        "specialty_id": 1,
        "starts_at": "2026-06-01T08:00:00+00:00",
        "ends_at": "2026-06-01T20:00:00+00:00",
        "rate_cents": 120000,
    }
    payload.update(overrides)
    return payload


def test_create_shift_defaults(client, coordinator, hospital) -> None:
    token = _coord_token(client)
    resp = client.post("/shifts", headers=auth_header(token), json=_shift_payload())
    assert resp.status_code == 201, resp.get_json()
    shift = resp.get_json()["shift"]
    assert shift["status"] == "open"
    assert shift["hospital_id"] == str(hospital.id)
    assert shift["current_batch"] == 0
    assert shift["batch_size"] == 3  # default de settings
    assert shift["version"] == 0


def test_create_shift_custom_batch(client, coordinator) -> None:
    token = _coord_token(client)
    resp = client.post(
        "/shifts",
        headers=auth_header(token),
        json=_shift_payload(batch_size=5, batch_window_minutes=15),
    )
    shift = resp.get_json()["shift"]
    assert shift["batch_size"] == 5
    assert shift["batch_window_minutes"] == 15


def test_create_shift_ends_before_starts_is_422(client, coordinator) -> None:
    token = _coord_token(client)
    resp = client.post(
        "/shifts",
        headers=auth_header(token),
        json=_shift_payload(ends_at="2026-06-01T07:00:00+00:00"),
    )
    assert resp.status_code == 422


def test_create_shift_naive_datetime_is_422(client, coordinator) -> None:
    token = _coord_token(client)
    resp = client.post(
        "/shifts",
        headers=auth_header(token),
        json=_shift_payload(starts_at="2026-06-01T08:00:00"),
    )
    assert resp.status_code == 422


def test_create_shift_unknown_specialty_is_422(client, coordinator) -> None:
    token = _coord_token(client)
    resp = client.post(
        "/shifts", headers=auth_header(token), json=_shift_payload(specialty_id=999)
    )
    assert resp.status_code == 422


def test_list_and_get_shift(client, coordinator) -> None:
    token = _coord_token(client)
    created = client.post(
        "/shifts", headers=auth_header(token), json=_shift_payload()
    ).get_json()["shift"]

    listing = client.get("/shifts", headers=auth_header(token))
    assert listing.status_code == 200
    assert any(s["id"] == created["id"] for s in listing.get_json()["shifts"])

    one = client.get(f"/shifts/{created['id']}", headers=auth_header(token))
    assert one.status_code == 200
    assert one.get_json()["shift"]["id"] == created["id"]


def test_shift_from_other_hospital_is_404(client, coordinator, session) -> None:
    """Plantão de outro hospital → 404 (não vaza existência entre hospitais)."""
    other_hospital = Hospital(name="Hospital Sul")
    session.add(other_hospital)
    session.flush()
    other_coord = Account(
        email="sul@coord.test",
        password_hash=hash_password("senha-sul"),
        role="coordenador",
        hospital_id=other_hospital.id,
    )
    session.add(other_coord)
    session.commit()

    # Plantão criado pela coordenadora do Sul.
    sul_token = login(client, "sul@coord.test", "senha-sul")
    sul_shift = client.post(
        "/shifts", headers=auth_header(sul_token), json=_shift_payload()
    ).get_json()["shift"]

    # Coordenadora do Central não enxerga o plantão do Sul.
    central_token = _coord_token(client)
    resp = client.get(
        f"/shifts/{sul_shift['id']}", headers=auth_header(central_token)
    )
    assert resp.status_code == 404

    listing = client.get("/shifts", headers=auth_header(central_token))
    assert all(s["id"] != sul_shift["id"] for s in listing.get_json()["shifts"])
