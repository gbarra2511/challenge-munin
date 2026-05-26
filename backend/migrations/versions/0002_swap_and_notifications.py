"""swap fields + notifications outbox

Revision ID: 0002
Revises: 0001
Create Date: 2026-05-26

Aditiva (sem destrutivo) — suporta dois bônus Tier 1:

1. **Swap de plantão**: a tabela `swap_requests` já existia (0001); aqui ela
   ganha `reason`/`decided_by`/`decided_at`, um índice **parcial único** que
   impede dois pedidos pendentes na mesma assignment, e o CHECK de
   `shift_assignments` passa a aceitar `'swapped_out'` (estado do médico que
   passou o plantão — conta a história no audit sem reusar `'cancelled'`).
2. **Outbox de notificação**: nova tabela `notifications`, escrita na mesma
   transação do evento de domínio e drenada pelo tick. `accounts.phone` permite
   alcançar a coordenação no WhatsApp.

Escrita manual (como a 0001): autogenerate não cobre CHECK constraints,
índice parcial, nem o re-create do constraint nomeado.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0002"
down_revision: str | None = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # -------- accounts.phone (coordenação no WhatsApp) --------
    op.add_column("accounts", sa.Column("phone", sa.Text(), nullable=True))

    # -------- shift_assignments: + 'swapped_out' no CHECK --------
    op.drop_constraint("assignment_status_valid", "shift_assignments", type_="check")
    op.create_check_constraint(
        "assignment_status_valid",
        "shift_assignments",
        "status IN ('active', 'cancelled', 'completed', 'swapped_out')",
    )

    # -------- swap_requests: campos de decisão + guardas --------
    op.add_column("swap_requests", sa.Column("reason", sa.Text(), nullable=True))
    op.add_column(
        "swap_requests",
        sa.Column(
            "decided_by",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("accounts.id"),
            nullable=True,
        ),
    )
    op.add_column(
        "swap_requests",
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
    )
    # No máximo UM pedido pendente por assignment (defesa em profundidade:
    # o serviço também checa, mas o índice torna a corrida impossível).
    op.create_index(
        "uq_swap_pending_per_assignment",
        "swap_requests",
        ["from_assignment_id"],
        unique=True,
        postgresql_where=sa.text("status = 'pending'"),
    )
    op.create_index("ix_swap_status", "swap_requests", ["status"])

    # -------- notifications (outbox) --------
    op.create_table(
        "notifications",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "recipient_account_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("accounts.id"),
            nullable=False,
        ),
        sa.Column("channel", sa.Text(), nullable=False),
        sa.Column("template", sa.Text(), nullable=False),
        sa.Column("payload", postgresql.JSONB(), nullable=False),
        sa.Column(
            "status",
            sa.Text(),
            nullable=False,
            server_default=sa.text("'pending'"),
        ),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("last_error", sa.Text()),
        # dedupe_key UNIQUE → enqueue idempotente (ON CONFLICT DO NOTHING).
        sa.Column("dedupe_key", sa.Text(), nullable=False, unique=True),
        sa.Column("provider_message_id", sa.Text()),
        sa.Column("read_at", sa.DateTime(timezone=True)),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("sent_at", sa.DateTime(timezone=True)),
        sa.CheckConstraint(
            "channel IN ('in_app', 'whatsapp')",
            name="notification_channel_valid",
        ),
        sa.CheckConstraint(
            "status IN ('pending', 'sending', 'sent', 'failed', 'skipped')",
            name="notification_status_valid",
        ),
    )
    # Scan do dispatch: pendentes de um canal, em ordem de chegada.
    op.create_index(
        "ix_notifications_dispatch",
        "notifications",
        ["channel", "status", "created_at"],
    )
    # Feed in-app por conta.
    op.create_index(
        "ix_notifications_recipient",
        "notifications",
        ["recipient_account_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_table("notifications")

    op.drop_index("ix_swap_status", table_name="swap_requests")
    op.drop_index("uq_swap_pending_per_assignment", table_name="swap_requests")
    op.drop_column("swap_requests", "decided_at")
    op.drop_column("swap_requests", "decided_by")
    op.drop_column("swap_requests", "reason")

    op.drop_constraint("assignment_status_valid", "shift_assignments", type_="check")
    op.create_check_constraint(
        "assignment_status_valid",
        "shift_assignments",
        "status IN ('active', 'cancelled', 'completed')",
    )

    op.drop_column("accounts", "phone")
