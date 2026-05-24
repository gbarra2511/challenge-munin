"""Audit log: uma linha imutável por transição relevante de domínio.

Toda mudança de estado de plantão/oferta grava aqui (PLANO §5, regra dura).
Alimenta a timeline do detalhe do plantão (bônus) e dá rastreabilidade
pro pair-debug.
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Any
from uuid import UUID

from app.models import AuditEvent

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


def record_event(
    session: Session,
    *,
    event_type: str,
    payload: dict[str, Any],
    shift_id: UUID | None = None,
    hospital_id: UUID | None = None,
    actor_type: str | None = None,
    actor_id: UUID | None = None,
) -> None:
    session.add(
        AuditEvent(
            event_type=event_type,
            payload=payload,
            shift_id=shift_id,
            hospital_id=hospital_id,
            actor_type=actor_type,
            actor_id=actor_id,
        )
    )
