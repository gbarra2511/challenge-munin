"""Schemas Pydantic v2 para validação de request e shape de response.

Não usamos EmailStr (exigiria a dep email-validator) — e-mail é só `str`
com checagem mínima; a unicidade real é garantida pelo CITEXT UNIQUE no banco.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class LoginIn(BaseModel):
    email: str = Field(min_length=3, max_length=320)
    password: str = Field(min_length=1, max_length=200)


class DoctorCreateIn(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    email: str = Field(min_length=3, max_length=320)
    password: str = Field(min_length=6, max_length=200)
    phone: str | None = Field(default=None, max_length=40)
    specialty_ids: list[int] = Field(min_length=1)
    hospital_ids: list[UUID] = Field(default_factory=list)


class OfferCreateIn(BaseModel):
    # Vazio/ausente → usa o ranking. Preenchido → oferta manual a esses médicos.
    doctor_ids: list[UUID] = Field(default_factory=list)


class SwapRequestIn(BaseModel):
    """Médico A pede para passar a assignment a um colega elegível B."""

    model_config = ConfigDict(extra="forbid")

    assignment_id: UUID
    to_doctor_id: UUID


class SwapDecisionIn(BaseModel):
    """Coordenação aprova/recusa; motivo é repassado ao médico A."""

    model_config = ConfigDict(extra="forbid")

    reason: str | None = Field(default=None, max_length=500)


class ShiftCreateIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    specialty_id: int
    starts_at: datetime
    ends_at: datetime
    rate_cents: int = Field(gt=0)
    batch_size: int | None = Field(default=None, gt=0)
    batch_window_minutes: int | None = Field(default=None, gt=0)
    escalate_hours_before: int | None = Field(default=None, ge=0)

    @field_validator("starts_at", "ends_at")
    @classmethod
    def _must_be_tz_aware(cls, v: datetime) -> datetime:
        if v.tzinfo is None:
            raise ValueError("datetime must be timezone-aware (ISO 8601 with offset)")
        return v

    @field_validator("ends_at")
    @classmethod
    def _ends_after_starts(cls, v: datetime, info) -> datetime:  # type: ignore[no-untyped-def]
        starts = info.data.get("starts_at")
        if starts is not None and v <= starts:
            raise ValueError("ends_at must be after starts_at")
        return v


class RankingPreviewIn(BaseModel):
    """Dry-run do ranking ANTES de o plantão existir (preview na criação).
    Só precisa do que define elegibilidade: especialidade + janela."""

    model_config = ConfigDict(extra="forbid")

    specialty_id: int
    starts_at: datetime
    ends_at: datetime

    @field_validator("starts_at", "ends_at")
    @classmethod
    def _must_be_tz_aware(cls, v: datetime) -> datetime:
        if v.tzinfo is None:
            raise ValueError("datetime must be timezone-aware (ISO 8601 with offset)")
        return v

    @field_validator("ends_at")
    @classmethod
    def _ends_after_starts(cls, v: datetime, info) -> datetime:  # type: ignore[no-untyped-def]
        starts = info.data.get("starts_at")
        if starts is not None and v <= starts:
            raise ValueError("ends_at must be after starts_at")
        return v
