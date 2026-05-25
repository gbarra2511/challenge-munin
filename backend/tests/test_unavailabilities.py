"""Indisponibilidades do médico: criação (incl. repetição semanal),
validação de janela e posse na exclusão. Ver §4.7 dec. 4 do PLANO.

A repetição gera instâncias reais no banco (decisão consciente em
IMPLEMENTACAO.md: evita query GIST/RRULE no ranking).
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from app.api.errors import NotFound, UnprocessableEntity
from app.services.unavailabilities import (
    create_unavailability,
    delete_unavailability,
    list_unavailabilities,
)
from tests.conftest import seed_doctor

FUTURE = datetime(2030, 1, 10, 8, 0, tzinfo=UTC)


def _doc(session, hospital, email="u@t.test", name="Dr. U"):
    return seed_doctor(
        session, name=name, email=email, specialty_ids=[1], hospital_ids=[hospital.id]
    )


def test_create_unavailability_single(session, hospital) -> None:
    doc = _doc(session, hospital)
    created = create_unavailability(
        session, doc.id, starts_at=FUTURE, ends_at=FUTURE + timedelta(hours=8)
    )
    assert len(created) == 1
    listed = list_unavailabilities(session, doc.id)
    assert [u.id for u in listed] == [created[0].id]


def test_create_unavailability_repeat_weeks_creates_instances(session, hospital) -> None:
    doc = _doc(session, hospital)
    created = create_unavailability(
        session,
        doc.id,
        starts_at=FUTURE,
        ends_at=FUTURE + timedelta(hours=8),
        repeat_weeks=3,
    )
    assert len(created) == 4  # semana base + 3 repetições

    starts = sorted(u.starts_at for u in created)
    for earlier, later in zip(starts, starts[1:], strict=False):
        assert later - earlier == timedelta(weeks=1)


def test_create_unavailability_rejects_inverted_window(session, hospital) -> None:
    doc = _doc(session, hospital)
    with pytest.raises(UnprocessableEntity):
        create_unavailability(
            session, doc.id, starts_at=FUTURE, ends_at=FUTURE - timedelta(hours=1)
        )


def test_create_unavailability_rejects_past(session, hospital) -> None:
    doc = _doc(session, hospital)
    past = datetime(2000, 1, 1, tzinfo=UTC)
    with pytest.raises(UnprocessableEntity):
        create_unavailability(session, doc.id, starts_at=past, ends_at=past + timedelta(hours=1))


def test_delete_unavailability_enforces_ownership(session, hospital) -> None:
    owner = _doc(session, hospital, email="owner@t.test", name="Owner")
    other = _doc(session, hospital, email="other@t.test", name="Other")
    u = create_unavailability(
        session, owner.id, starts_at=FUTURE, ends_at=FUTURE + timedelta(hours=8)
    )[0]

    with pytest.raises(NotFound):
        delete_unavailability(session, u.id, doctor_id=other.id)
    assert len(list_unavailabilities(session, owner.id)) == 1  # intacta

    delete_unavailability(session, u.id, doctor_id=owner.id)
    assert list_unavailabilities(session, owner.id) == []
