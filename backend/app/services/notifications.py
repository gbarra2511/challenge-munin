"""Outbox de notificação.

Escrito na MESMA transação do evento de domínio (oferta enviada, swap pedido/
decidido) — nunca chamamos o provedor externo dentro da transação do banco
(evita dual-write). O canal `in_app` é entregue na hora (o feed lê direto);
`whatsapp` é drenado pelo tick via `dispatch_pending` (claim-then-send, fora da
transação). `dedupe_key` UNIQUE torna o enqueue idempotente.

Recipiente é sempre uma `accounts.id`. O telefone é resolvido só no envio
(coord → `accounts.phone`; médico → `doctors.phone`) — telefone é PII e não
entra no payload nem no audit.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.infra.notifier import NullNotifier
from app.models import Account, Doctor, Notification

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

    from app.infra.notifier import Notifier

MAX_ATTEMPTS = 5
_DISPATCH_CHANNEL = "whatsapp"
DEFAULT_CHANNELS = ("in_app", "whatsapp")

logger = logging.getLogger(__name__)


def _now(now: datetime | None) -> datetime:
    return now or datetime.now(UTC)


# --- enqueue (idempotente, dentro da transação do domínio) ------------------


def enqueue(
    session: Session,
    *,
    recipient_account_id: UUID,
    channel: str,
    template: str,
    payload: dict[str, Any],
    dedupe_key: str,
    now: datetime | None = None,
) -> None:
    """Enfileira uma notificação. `in_app` nasce 'sent' (o feed lê na hora);
    `whatsapp` nasce 'pending' (o dispatch entrega). ON CONFLICT no dedupe_key
    torna re-enqueue um no-op (idempotência sob tick repetido)."""
    now = _now(now)
    is_in_app = channel == "in_app"
    stmt = (
        pg_insert(Notification)
        .values(
            recipient_account_id=recipient_account_id,
            channel=channel,
            template=template,
            payload=payload,
            status="sent" if is_in_app else "pending",
            sent_at=now if is_in_app else None,
            dedupe_key=dedupe_key,
        )
        .on_conflict_do_nothing(index_elements=["dedupe_key"])
    )
    session.execute(stmt)


def notify_event(
    session: Session,
    *,
    recipient_account_id: UUID,
    template: str,
    ref_id: str,
    title: str,
    body: str,
    path: str = "",
    channels: tuple[str, ...] = DEFAULT_CHANNELS,
    now: datetime | None = None,
) -> None:
    """Enfileira o mesmo evento em vários canais para um destinatário. `path` é
    relativo (ex. '/ofertas') — o feed in-app e o WhatsApp prefixam a base."""
    payload = {"title": title, "body": body, "path": path}
    for channel in channels:
        enqueue(
            session,
            recipient_account_id=recipient_account_id,
            channel=channel,
            template=template,
            payload=payload,
            dedupe_key=f"{template}:{ref_id}:{recipient_account_id}:{channel}",
            now=now,
        )


def notify_doctor(
    session: Session,
    *,
    doctor_id: UUID,
    template: str,
    ref_id: str,
    title: str,
    body: str,
    path: str = "",
    now: datetime | None = None,
) -> None:
    """Notifica o médico resolvendo sua conta. Sem conta → no-op silencioso."""
    account_id = session.scalar(select(Doctor.account_id).where(Doctor.id == doctor_id))
    if account_id is None:
        return
    notify_event(
        session,
        recipient_account_id=account_id,
        template=template,
        ref_id=ref_id,
        title=title,
        body=body,
        path=path,
        now=now,
    )


def notify_hospital_coords(
    session: Session,
    *,
    hospital_id: UUID,
    template: str,
    ref_id: str,
    title: str,
    body: str,
    path: str = "",
    now: datetime | None = None,
) -> None:
    """Notifica todas as coordenações do hospital."""
    coord_ids = session.scalars(
        select(Account.id).where(Account.role == "coordenador", Account.hospital_id == hospital_id)
    ).all()
    for account_id in coord_ids:
        notify_event(
            session,
            recipient_account_id=account_id,
            template=template,
            ref_id=ref_id,
            title=title,
            body=body,
            path=path,
            now=now,
        )


# --- dispatch (drena o outbox; fora da transação do domínio) ----------------


def _resolve_phone(session: Session, account_id: UUID) -> str | None:
    row = session.execute(
        select(Account.role, Account.phone, Doctor.phone)
        .outerjoin(Doctor, Doctor.account_id == Account.id)
        .where(Account.id == account_id)
    ).first()
    if row is None:
        return None
    role, account_phone, doctor_phone = row
    return account_phone if role == "coordenador" else doctor_phone


def _render(notification: Notification, link_base: str) -> str:
    p = notification.payload or {}
    text = f"*{p.get('title', '')}*\n\n{p.get('body', '')}"
    path = p.get("path")
    if path:
        text += f"\n\n{link_base}{path}"
    return text


def dispatch_pending(
    session: Session,
    *,
    notifier: Notifier | None = None,
    link_base: str = "",
    limit: int = 50,
    now: datetime | None = None,
) -> dict[str, int]:
    """Entrega as notificações `whatsapp` pendentes. Claim-then-send: trava e
    marca 'sending' num passo curto (FOR UPDATE SKIP LOCKED → dois ticks não
    pegam a mesma linha), commita pra soltar o lock, e SÓ ENTÃO chama o provedor
    (fora de qualquer lock de banco). At-least-once: duplica só se o processo
    morrer entre enviar e marcar."""
    now = _now(now)
    notifier = notifier or NullNotifier()

    # 1) claim — passo curto sob lock.
    claimed = list(
        session.scalars(
            select(Notification)
            .where(
                Notification.channel == _DISPATCH_CHANNEL,
                Notification.status == "pending",
            )
            .order_by(Notification.created_at)
            .limit(limit)
            .with_for_update(skip_locked=True)
        )
    )
    for n in claimed:
        n.status = "sending"
        n.attempts += 1
    session.commit()  # solta os locks antes de qualquer I/O externo

    stats = {"claimed": len(claimed), "sent": 0, "failed": 0, "skipped": 0}

    # 2) send — fora da transação.
    for n in claimed:
        phone = _resolve_phone(session, n.recipient_account_id)
        if not phone:
            n.status = "skipped"
            n.last_error = "recipient has no phone"
            stats["skipped"] += 1
            session.commit()
            continue
        try:
            sid = notifier.send(phone, _render(n, link_base))
            n.status = "sent"
            n.provider_message_id = sid
            n.sent_at = now
            stats["sent"] += 1
        except Exception as exc:  # noqa: BLE001 — provedor externo, queremos resiliência
            n.last_error = str(exc)[:500]
            n.status = "failed" if n.attempts >= MAX_ATTEMPTS else "pending"
            stats["failed"] += 1
        session.commit()

    return stats


def dispatch_pending_safe(
    session: Session,
    *,
    notifier: Notifier | None = None,
    link_base: str = "",
    limit: int = 50,
    now: datetime | None = None,
) -> dict[str, int] | None:
    """Best-effort: roda `dispatch_pending` sem deixar erro vazar. Para chamar
    INLINE logo após uma ação que enfileira notificação — dá entrega quase-
    instantânea sem abrir mão do outbox: o cron do `/jobs/tick` continua sendo o
    fallback durável e idempotente (SKIP LOCKED evita envio duplo se os dois
    coincidirem). Uma falha aqui (rede/DB) nunca quebra a request: a notificação
    fica `pending` e o tick reenvia."""
    try:
        return dispatch_pending(
            session, notifier=notifier, link_base=link_base, limit=limit, now=now
        )
    except Exception:
        logger.exception("inline dispatch falhou; o tick fará o fallback")
        session.rollback()
        return None


# --- feed in-app ------------------------------------------------------------


def feed(session: Session, *, account_id: UUID, limit: int = 30) -> dict[str, Any]:
    rows = session.scalars(
        select(Notification)
        .where(
            Notification.recipient_account_id == account_id,
            Notification.channel == "in_app",
        )
        .order_by(Notification.created_at.desc())
        .limit(limit)
    ).all()
    items = [
        {
            "id": str(n.id),
            "template": n.template,
            "title": (n.payload or {}).get("title"),
            "body": (n.payload or {}).get("body"),
            "path": (n.payload or {}).get("path"),
            "read": n.read_at is not None,
            "created_at": n.created_at.isoformat() if n.created_at else None,
        }
        for n in rows
    ]
    unread = sum(1 for n in rows if n.read_at is None)
    return {"notifications": items, "unread": unread}


def mark_read(
    session: Session,
    *,
    account_id: UUID,
    notification_id: UUID | None = None,
    now: datetime | None = None,
) -> None:
    """Marca uma notificação (ou todas) como lida. Escopado ao dono."""
    now = _now(now)
    stmt = select(Notification).where(
        Notification.recipient_account_id == account_id,
        Notification.read_at.is_(None),
    )
    if notification_id is not None:
        stmt = stmt.where(Notification.id == notification_id)
    for n in session.scalars(stmt):
        n.read_at = now
    session.commit()
