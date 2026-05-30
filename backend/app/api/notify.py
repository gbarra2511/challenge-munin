"""Entrega inline do outbox.

`flush_notifications` drena as notificações pendentes logo após uma ação que as
enfileira (oferta enviada, swap pedido/decidido) — assim o WhatsApp chega quase
na hora, em vez de esperar o próximo `/jobs/tick`. O cron continua sendo o
fallback durável; é best-effort, então um erro aqui nunca quebra a request.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from flask import current_app

from app.infra.notifier import get_notifier
from app.services.notifications import dispatch_pending_safe

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


def flush_notifications(session: Session) -> None:
    dispatch_pending_safe(
        session,
        notifier=get_notifier(current_app.config),
        link_base=current_app.config.get("FRONTEND_URL", ""),
    )
