"""registro de uso de Groq

Revision ID: e5a1c9d37b62
Revises: d2b8c6e19f74
Create Date: 2026-11-18

Una fila por llamada a Groq, sin texto de la persona. Es la base del tope mensual de solicitudes de IA.
"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "e5a1c9d37b62"
down_revision: str | Sequence[str] | None = "d2b8c6e19f74"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "ai_usage",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("tarea", sa.String(), nullable=False),
        sa.Column("modelo", sa.String(), nullable=False),
        sa.Column("tokens_entrada", sa.Integer(), nullable=True),
        sa.Column("tokens_salida", sa.Integer(), nullable=True),
        sa.Column("latencia_ms", sa.Integer(), nullable=True),
        sa.Column("exito", sa.Boolean(), nullable=False),
        sa.Column("uso_respaldo", sa.Boolean(), nullable=False),
        sa.Column("bloqueado_por", sa.String(), nullable=False),
        sa.Column("mes", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint(
            "bloqueado_por IN ('ninguno', 'cupo', 'alcance', 'inyeccion')",
            name="ck_ai_usage_bloqueado_por_valido",
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_ai_usage_user_id", "ai_usage", ["user_id"])
    op.create_index("ix_ai_usage_tarea", "ai_usage", ["tarea"])
    op.create_index("ix_ai_usage_user_mes", "ai_usage", ["user_id", "mes"])


def downgrade() -> None:
    op.drop_index("ix_ai_usage_user_mes", table_name="ai_usage")
    op.drop_index("ix_ai_usage_tarea", table_name="ai_usage")
    op.drop_index("ix_ai_usage_user_id", table_name="ai_usage")
    op.drop_table("ai_usage")
