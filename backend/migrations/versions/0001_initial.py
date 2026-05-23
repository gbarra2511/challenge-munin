"""initial schema with specialties bootstrap

Revision ID: 0001
Revises:
Create Date: 2026-05-23

Cria o schema completo do Mini-WFM (10 tabelas) e popula `specialties`
com as 8 especialidades-base via bulk_insert (data migration).

Escrita manual em vez de --autogenerate porque autogenerate não cobre:
- CREATE EXTENSION
- CHECK constraints
- Índice único PARCIAL (one_active_assignment_per_shift)
- Data migration (bulk_insert)
- Ordem garantida pra demonstrar o desenho do schema

Ver PLANO.md §4 para schema completo e §4.7 para decisões.
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# Identificadores Alembic
revision = "0001"
down_revision: str | None = None
branch_labels = None
depends_on = None


# Especialidades-base do sistema. IDs FIXOS para que dev/CI/prod
# possam referenciar por constante (ex.: SPECIALTY_CARDIOLOGIA = 3).
# Adicionar novas → criar nova migration, nunca reordenar/remover.
SPECIALTIES_SEED: list[dict[str, object]] = [
    {"id": 1, "slug": "clinica-medica",          "name": "Clínica Médica"},
    {"id": 2, "slug": "pediatria",               "name": "Pediatria"},
    {"id": 3, "slug": "cardiologia",             "name": "Cardiologia"},
    {"id": 4, "slug": "ginecologia-obstetricia", "name": "Ginecologia e Obstetrícia"},
    {"id": 5, "slug": "ortopedia",               "name": "Ortopedia"},
    {"id": 6, "slug": "anestesiologia",          "name": "Anestesiologia"},
    {"id": 7, "slug": "uti",                     "name": "Medicina Intensiva (UTI)"},
    {"id": 8, "slug": "pronto-socorro",          "name": "Pronto-Socorro"},
]


def upgrade() -> None:
    # citext: emails case-insensitive em accounts.email
    op.execute("CREATE EXTENSION IF NOT EXISTS citext")

    # -------- Identidade --------
    op.create_table(
        "hospitals",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.Text(), nullable=False),
    )

    op.create_table(
        "accounts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("email", postgresql.CITEXT(), nullable=False, unique=True),
        sa.Column("password_hash", sa.Text(), nullable=False),
        sa.Column("role", sa.Text(), nullable=False),
        sa.Column(
            "hospital_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("hospitals.id"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "role IN ('coordenador', 'medico')",
            name="account_role_valid",
        ),
        sa.CheckConstraint(
            "(role = 'coordenador' AND hospital_id IS NOT NULL) OR "
            "(role = 'medico'      AND hospital_id IS NULL)",
            name="account_hospital_per_role",
        ),
    )

    op.create_table(
        "doctors",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "account_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("accounts.id"),
            unique=True,
        ),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("phone", sa.Text()),
    )

    # -------- Especialidades --------
    op.create_table(
        "specialties",
        sa.Column("id", sa.SmallInteger(), sa.Identity(), primary_key=True),
        sa.Column("slug", sa.Text(), nullable=False, unique=True),
        sa.Column("name", sa.Text(), nullable=False),
    )

    # Data migration — ver PLANO §4.7 decisão 1.
    op.bulk_insert(
        sa.table(
            "specialties",
            sa.column("id", sa.SmallInteger),
            sa.column("slug", sa.Text),
            sa.column("name", sa.Text),
        ),
        SPECIALTIES_SEED,
    )
    # Inserimos com IDs explícitos -> avançar a sequence pra evitar
    # conflito em qualquer INSERT futuro sem ID. Identity columns no
    # Postgres usam uma sequence interna que pg_get_serial_sequence resolve.
    op.execute(
        "SELECT setval(pg_get_serial_sequence('specialties', 'id'), "
        f"{len(SPECIALTIES_SEED)})"
    )

    op.create_table(
        "doctor_specialties",
        sa.Column(
            "doctor_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("doctors.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "specialty_id",
            sa.SmallInteger(),
            sa.ForeignKey("specialties.id"),
            primary_key=True,
        ),
    )
    op.create_index(
        "ix_doctor_specialties_specialty_id",
        "doctor_specialties",
        ["specialty_id"],
    )

    # -------- Afiliação médico ↔ hospital (N:M) --------
    op.create_table(
        "doctor_hospital_affiliations",
        sa.Column(
            "doctor_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("doctors.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "hospital_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("hospitals.id"),
            primary_key=True,
        ),
        sa.Column(
            "status",
            sa.Text(),
            nullable=False,
            server_default=sa.text("'active'"),
        ),
        sa.Column(
            "joined_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "status IN ('active', 'inactive')",
            name="dha_status_valid",
        ),
    )
    op.create_index(
        "ix_dha_hospital_status",
        "doctor_hospital_affiliations",
        ["hospital_id", "status"],
    )

    # -------- Indisponibilidades --------
    op.create_table(
        "doctor_unavailabilities",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "doctor_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("doctors.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ends_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("reason", sa.Text()),
        sa.CheckConstraint(
            "ends_at > starts_at", name="unavail_window_valid"
        ),
    )
    op.create_index(
        "ix_unavail_doctor_window",
        "doctor_unavailabilities",
        ["doctor_id", "starts_at", "ends_at"],
    )

    # -------- Plantões e ofertas --------
    op.create_table(
        "shifts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "hospital_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("hospitals.id"),
            nullable=False,
        ),
        sa.Column(
            "specialty_id",
            sa.SmallInteger(),
            sa.ForeignKey("specialties.id"),
            nullable=False,
        ),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ends_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("rate_cents", sa.Integer(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column(
            "current_batch",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column(
            "batch_size",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("3"),
        ),
        sa.Column(
            "batch_window_minutes",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("30"),
        ),
        sa.Column(
            "escalate_hours_before",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("6"),
        ),
        sa.Column(
            "version",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "status IN ('open', 'offering', 'accepted', 'confirmed', "
            "'needs_attention', 'cancelled')",
            name="shift_status_valid",
        ),
        sa.CheckConstraint("ends_at > starts_at", name="shift_window_valid"),
    )
    op.create_index(
        "ix_shifts_status_starts_at", "shifts", ["status", "starts_at"]
    )
    op.create_index(
        "ix_shifts_hospital_starts_at",
        "shifts",
        ["hospital_id", "starts_at"],
    )

    op.create_table(
        "shift_offers",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "shift_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("shifts.id"),
            nullable=False,
        ),
        sa.Column(
            "doctor_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("doctors.id"),
            nullable=False,
        ),
        sa.Column("batch_number", sa.Integer(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("responded_at", sa.DateTime(timezone=True)),
        sa.UniqueConstraint(
            "shift_id",
            "doctor_id",
            "batch_number",
            name="uq_offer_unique_per_batch",
        ),
        sa.CheckConstraint(
            "status IN ('pending', 'accepted', 'declined', "
            "'expired', 'superseded')",
            name="offer_status_valid",
        ),
    )
    op.create_index(
        "ix_offers_doctor_status", "shift_offers", ["doctor_id", "status"]
    )

    op.create_table(
        "shift_assignments",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "shift_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("shifts.id"),
            nullable=False,
        ),
        sa.Column(
            "doctor_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("doctors.id"),
            nullable=False,
        ),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("checked_in_at", sa.DateTime(timezone=True)),
        sa.CheckConstraint(
            "status IN ('active', 'cancelled', 'completed')",
            name="assignment_status_valid",
        ),
    )
    # **A LINHA MAIS IMPORTANTE DO BANCO**: índice único PARCIAL impede
    # dois assignments ativos pro mesmo plantão. Defesa em profundidade
    # contra falha da camada de aplicação. Ver PLANO §6.
    op.create_index(
        "one_active_assignment_per_shift",
        "shift_assignments",
        ["shift_id"],
        unique=True,
        postgresql_where=sa.text("status = 'active'"),
    )

    # -------- Bônus --------
    op.create_table(
        "swap_requests",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "from_assignment_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("shift_assignments.id"),
            nullable=False,
        ),
        sa.Column(
            "to_doctor_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("doctors.id"),
            nullable=False,
        ),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "status IN ('pending', 'approved', 'rejected', 'cancelled')",
            name="swap_status_valid",
        ),
    )

    op.create_table(
        "audit_events",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column("hospital_id", postgresql.UUID(as_uuid=True)),
        sa.Column("shift_id", postgresql.UUID(as_uuid=True)),
        sa.Column("actor_type", sa.Text()),
        sa.Column("actor_id", postgresql.UUID(as_uuid=True)),
        sa.Column("event_type", sa.Text(), nullable=False),
        sa.Column("payload", postgresql.JSONB(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_audit_shift_created", "audit_events", ["shift_id", "created_at"]
    )
    op.create_index(
        "ix_audit_hospital_created",
        "audit_events",
        ["hospital_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_table("audit_events")
    op.drop_table("swap_requests")
    op.drop_index(
        "one_active_assignment_per_shift", table_name="shift_assignments"
    )
    op.drop_table("shift_assignments")
    op.drop_table("shift_offers")
    op.drop_table("shifts")
    op.drop_table("doctor_unavailabilities")
    op.drop_table("doctor_hospital_affiliations")
    op.drop_table("doctor_specialties")
    op.drop_table("specialties")
    op.drop_table("doctors")
    op.drop_table("accounts")
    op.drop_table("hospitals")
    # Não dropamos a extensão citext: pode ser usada por outros schemas
    # ou ferramentas que compartilhem o database.
