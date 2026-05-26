"""Outbox de notificação: enqueue idempotente, feed in-app, dispatch (WhatsApp
via NullNotifier), resolução de telefone e wiring na oferta de plantão.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select

from app.infra.notifier import NullNotifier
from app.models import Account, Hospital, Notification
from app.services.notifications import (
    dispatch_pending,
    enqueue,
    feed,
    mark_read,
    notify_event,
)
from app.services.offers import open_offers
from tests.conftest import seed_doctor, seed_shift


def _coord(session, hospital_id, *, phone=None):
    from app.infra.hashing import hash_password

    acct = Account(
        email=f"coord-{uuid.uuid4().hex[:8]}@central.test",
        password_hash=hash_password("x"),
        role="coordenador",
        hospital_id=hospital_id,
        phone=phone,
    )
    session.add(acct)
    session.commit()
    return acct


# --- enqueue / feed ---------------------------------------------------------


def test_enqueue_is_idempotent(session) -> None:
    h = Hospital(name="H")
    session.add(h)
    session.flush()
    coord = _coord(session, h.id)
    # mesmo ref → mesmo dedupe_key por canal: re-enqueue é no-op.
    notify_event(session, recipient_account_id=coord.id, template="swap.requested",
                 ref_id="abc", title="t", body="b", path="/trocas")
    notify_event(session, recipient_account_id=coord.id, template="swap.requested",
                 ref_id="abc", title="t", body="b", path="/trocas")
    session.commit()
    total = session.scalar(
        select(func.count()).select_from(Notification).where(
            Notification.recipient_account_id == coord.id
        )
    )
    assert total == 2  # 1 in_app + 1 whatsapp, não 4


def test_in_app_feed_and_mark_read(session) -> None:
    h = Hospital(name="H")
    session.add(h)
    session.flush()
    coord = _coord(session, h.id)
    notify_event(session, recipient_account_id=coord.id, template="swap.requested",
                 ref_id="r1", title="Pedido", body="corpo", path="/trocas",
                 channels=("in_app",))
    session.commit()

    f = feed(session, account_id=coord.id)
    assert f["unread"] == 1
    assert f["notifications"][0]["title"] == "Pedido"
    assert f["notifications"][0]["read"] is False

    mark_read(session, account_id=coord.id)
    assert feed(session, account_id=coord.id)["unread"] == 0


# --- dispatch ---------------------------------------------------------------


def test_dispatch_sends_whatsapp_via_null_notifier(session) -> None:
    h = Hospital(name="H")
    session.add(h)
    session.flush()
    doctor = seed_doctor(session, name="Dr", email="d@central.test", specialty_ids=[1],
                         hospital_ids=[h.id])
    doctor.phone = "+55 11 90000-0000"
    session.commit()

    enqueue(session, recipient_account_id=doctor.account_id, channel="whatsapp",
            template="offer.created", payload={"title": "t", "body": "b", "path": "/ofertas"},
            dedupe_key="k1")
    session.commit()

    stats = dispatch_pending(session, notifier=NullNotifier())
    assert stats["sent"] == 1
    n = session.scalar(select(Notification).where(Notification.dedupe_key == "k1"))
    assert n.status == "sent"
    assert n.provider_message_id is not None
    assert n.sent_at is not None


def test_dispatch_skips_recipient_without_phone(session) -> None:
    h = Hospital(name="H")
    session.add(h)
    session.flush()
    coord = _coord(session, h.id, phone=None)  # sem telefone
    enqueue(session, recipient_account_id=coord.id, channel="whatsapp",
            template="swap.requested", payload={"title": "t", "body": "b"}, dedupe_key="k2")
    session.commit()

    stats = dispatch_pending(session, notifier=NullNotifier())
    assert stats["skipped"] == 1
    n = session.scalar(select(Notification).where(Notification.dedupe_key == "k2"))
    assert n.status == "skipped"


def test_dispatch_is_idempotent_no_double_send(session) -> None:
    h = Hospital(name="H")
    session.add(h)
    session.flush()
    coord = _coord(session, h.id, phone="+55 11 91111-1111")
    enqueue(session, recipient_account_id=coord.id, channel="whatsapp",
            template="swap.requested", payload={"title": "t", "body": "b"}, dedupe_key="k3")
    session.commit()

    first = dispatch_pending(session, notifier=NullNotifier())
    second = dispatch_pending(session, notifier=NullNotifier())
    assert first["sent"] == 1
    assert second["claimed"] == 0  # nada mais pendente


def test_in_app_notification_is_not_dispatched(session) -> None:
    """Canal in_app nasce 'sent' e nunca é reclamado pelo dispatch."""
    h = Hospital(name="H")
    session.add(h)
    session.flush()
    coord = _coord(session, h.id, phone="+55 11 92222-2222")
    enqueue(session, recipient_account_id=coord.id, channel="in_app",
            template="swap.requested", payload={"title": "t", "body": "b"}, dedupe_key="k4")
    session.commit()
    stats = dispatch_pending(session, notifier=NullNotifier())
    assert stats["claimed"] == 0
    n = session.scalar(select(Notification).where(Notification.dedupe_key == "k4"))
    assert n.status == "sent"  # entregue na hora ao feed


# --- wiring na oferta -------------------------------------------------------


def test_send_batch_enqueues_offer_notification(session) -> None:
    h = Hospital(name="H")
    session.add(h)
    session.flush()
    doctor = seed_doctor(session, name="Dra", email="dra@central.test", specialty_ids=[1],
                         hospital_ids=[h.id])
    now = datetime.now(UTC)
    shift = seed_shift(session, hospital_id=h.id, starts_at=now + timedelta(days=3),
                       ends_at=now + timedelta(days=3, hours=6), specialty_id=1, status="open")

    open_offers(session, shift, doctor_ids=[doctor.id])

    notifs = session.scalars(
        select(Notification).where(
            Notification.recipient_account_id == doctor.account_id,
            Notification.template == "offer.created",
        )
    ).all()
    # in_app + whatsapp para a oferta criada
    assert len(notifs) == 2
    assert {n.channel for n in notifs} == {"in_app", "whatsapp"}
