"""SQLAlchemy 2.0 declarative models for the Mini-WFM.

Schema completo em PLANO.md §4. Racional das decisões em §4.7.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Identity,
    Index,
    Integer,
    SmallInteger,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import CITEXT, JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


# ---------------------------------------------------------------------------
# Identidade
# ---------------------------------------------------------------------------


class Hospital(Base):
    __tablename__ = "hospitals"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(Text, nullable=False)


class Account(Base):
    __tablename__ = "accounts"
    __table_args__ = (
        CheckConstraint(
            "role IN ('coordenador', 'medico')",
            name="account_role_valid",
        ),
        # Coordenador SEMPRE tem hospital; médico NUNCA (vínculos em affiliations).
        CheckConstraint(
            "(role = 'coordenador' AND hospital_id IS NOT NULL) OR "
            "(role = 'medico'      AND hospital_id IS NULL)",
            name="account_hospital_per_role",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(CITEXT, unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(Text, nullable=False)
    role: Mapped[str] = mapped_column(Text, nullable=False)
    # Telefone da coordenação para notificação por WhatsApp (médico usa doctors.phone).
    phone: Mapped[str | None] = mapped_column(Text)
    hospital_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("hospitals.id")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()"), nullable=False
    )


class Doctor(Base):
    __tablename__ = "doctors"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    account_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("accounts.id"), unique=True
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)
    phone: Mapped[str | None] = mapped_column(Text)


# ---------------------------------------------------------------------------
# Especialidades (lookup populado via data migration; ver §4.7 dec. 1)
# ---------------------------------------------------------------------------


class Specialty(Base):
    __tablename__ = "specialties"

    id: Mapped[int] = mapped_column(SmallInteger, Identity(), primary_key=True)
    slug: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)


class DoctorSpecialty(Base):
    __tablename__ = "doctor_specialties"
    __table_args__ = (Index("ix_doctor_specialties_specialty_id", "specialty_id"),)

    doctor_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("doctors.id", ondelete="CASCADE"),
        primary_key=True,
    )
    specialty_id: Mapped[int] = mapped_column(
        SmallInteger, ForeignKey("specialties.id"), primary_key=True
    )


# ---------------------------------------------------------------------------
# Vínculo médico ↔ hospital (N:M; ver §4.7 dec. 2)
# ---------------------------------------------------------------------------


class DoctorHospitalAffiliation(Base):
    __tablename__ = "doctor_hospital_affiliations"
    __table_args__ = (
        CheckConstraint("status IN ('active', 'inactive')", name="dha_status_valid"),
        Index("ix_dha_hospital_status", "hospital_id", "status"),
    )

    doctor_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("doctors.id", ondelete="CASCADE"),
        primary_key=True,
    )
    hospital_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("hospitals.id"), primary_key=True
    )
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'active'"))
    joined_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()"), nullable=False
    )


# ---------------------------------------------------------------------------
# Indisponibilidades (filtradas pelo tick; ver §4.7 dec. 4)
# ---------------------------------------------------------------------------


class DoctorUnavailability(Base):
    __tablename__ = "doctor_unavailabilities"
    __table_args__ = (
        CheckConstraint("ends_at > starts_at", name="unavail_window_valid"),
        Index(
            "ix_unavail_doctor_window",
            "doctor_id",
            "starts_at",
            "ends_at",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    doctor_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("doctors.id", ondelete="CASCADE"),
        nullable=False,
    )
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ends_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    reason: Mapped[str | None] = mapped_column(Text)


# ---------------------------------------------------------------------------
# Plantões e ofertas
# ---------------------------------------------------------------------------


class Shift(Base):
    __tablename__ = "shifts"
    __table_args__ = (
        CheckConstraint(
            "status IN ('open', 'offering', 'accepted', 'confirmed', "
            "'needs_attention', 'cancelled')",
            name="shift_status_valid",
        ),
        CheckConstraint("ends_at > starts_at", name="shift_window_valid"),
        Index("ix_shifts_status_starts_at", "status", "starts_at"),
        Index("ix_shifts_hospital_starts_at", "hospital_id", "starts_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    hospital_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("hospitals.id"), nullable=False
    )
    specialty_id: Mapped[int] = mapped_column(
        SmallInteger, ForeignKey("specialties.id"), nullable=False
    )
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ends_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    rate_cents: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False)
    current_batch: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    batch_size: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("3"))
    batch_window_minutes: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("30")
    )
    escalate_hours_before: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("6")
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()"), nullable=False
    )


class ShiftOffer(Base):
    __tablename__ = "shift_offers"
    __table_args__ = (
        UniqueConstraint(
            "shift_id",
            "doctor_id",
            "batch_number",
            name="uq_offer_unique_per_batch",
        ),
        CheckConstraint(
            "status IN ('pending', 'accepted', 'declined', 'expired', 'superseded')",
            name="offer_status_valid",
        ),
        Index("ix_offers_doctor_status", "doctor_id", "status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    shift_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("shifts.id"), nullable=False
    )
    doctor_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("doctors.id"), nullable=False
    )
    batch_number: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False)
    sent_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    responded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ShiftAssignment(Base):
    __tablename__ = "shift_assignments"
    __table_args__ = (
        CheckConstraint(
            "status IN ('active', 'cancelled', 'completed', 'swapped_out')",
            name="assignment_status_valid",
        ),
        # A LINHA MAIS IMPORTANTE DO BANCO — defesa em profundidade contra
        # dois aceites simultâneos. Ver PLANO §6.
        Index(
            "one_active_assignment_per_shift",
            "shift_id",
            unique=True,
            postgresql_where=text("status = 'active'"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    shift_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("shifts.id"), nullable=False
    )
    doctor_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("doctors.id"), nullable=False
    )
    status: Mapped[str] = mapped_column(Text, nullable=False)
    accepted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    checked_in_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


# ---------------------------------------------------------------------------
# Bônus: troca + audit log
# ---------------------------------------------------------------------------


class SwapRequest(Base):
    __tablename__ = "swap_requests"
    __table_args__ = (
        CheckConstraint(
            "status IN ('pending', 'approved', 'rejected', 'cancelled')",
            name="swap_status_valid",
        ),
        # No máximo UM pedido pendente por assignment — torna a corrida de
        # dois pedidos simultâneos impossível no banco (o serviço também checa).
        Index(
            "uq_swap_pending_per_assignment",
            "from_assignment_id",
            unique=True,
            postgresql_where=text("status = 'pending'"),
        ),
        Index("ix_swap_status", "status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    from_assignment_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("shift_assignments.id"),
        nullable=False,
    )
    to_doctor_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("doctors.id"), nullable=False
    )
    status: Mapped[str] = mapped_column(Text, nullable=False)
    # Motivo (sobretudo na recusa) repassado ao médico que pediu a troca.
    reason: Mapped[str | None] = mapped_column(Text)
    decided_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("accounts.id")
    )
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()"), nullable=False
    )


class Notification(Base):
    """Outbox de notificação. Escrita na mesma transação do evento de domínio
    (oferta enviada, swap pedido/decidido) e drenada pelo tick — nunca chamamos
    o provedor externo dentro da transação do banco (evita dual-write).

    `channel='in_app'` é lido direto pelo feed (não precisa envio);
    `channel='whatsapp'` é entregue pelo dispatch (claim-then-send).
    `dedupe_key` UNIQUE garante enqueue idempotente.
    """

    __tablename__ = "notifications"
    __table_args__ = (
        CheckConstraint(
            "channel IN ('in_app', 'whatsapp')",
            name="notification_channel_valid",
        ),
        CheckConstraint(
            "status IN ('pending', 'sending', 'sent', 'failed', 'skipped')",
            name="notification_status_valid",
        ),
        Index("ix_notifications_dispatch", "channel", "status", "created_at"),
        Index("ix_notifications_recipient", "recipient_account_id", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    recipient_account_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("accounts.id"), nullable=False
    )
    channel: Mapped[str] = mapped_column(Text, nullable=False)
    template: Mapped[str] = mapped_column(Text, nullable=False)
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'pending'"))
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    last_error: Mapped[str | None] = mapped_column(Text)
    dedupe_key: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    provider_message_id: Mapped[str | None] = mapped_column(Text)
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()"), nullable=False
    )
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class AuditEvent(Base):
    __tablename__ = "audit_events"
    __table_args__ = (
        Index("ix_audit_shift_created", "shift_id", "created_at"),
        Index("ix_audit_hospital_created", "hospital_id", "created_at"),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    hospital_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    shift_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    actor_type: Mapped[str | None] = mapped_column(Text)
    actor_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    event_type: Mapped[str] = mapped_column(Text, nullable=False)
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()"), nullable=False
    )
