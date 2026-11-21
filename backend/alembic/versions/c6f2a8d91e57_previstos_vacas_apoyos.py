"""apoyos de la universidad, gastos previstos, vacas y progreso familiar

Revision ID: c6f2a8d91e57
Revises: b3d7e1f04a26
Create Date: 2026-11-19

Tablas de las funciones añadidas tras el análisis de competidores:
apoyos que ofrece la universidad y el interés anónimo en ellos, gastos grandes previstos, cuentas por cobrar
de las vacas y el permiso de compartir el progreso con la familia.
"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c6f2a8d91e57"
down_revision: str | Sequence[str] | None = "b3d7e1f04a26"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "support_resources",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("tipo", sa.String(), nullable=False),
        sa.Column("titulo", sa.String(), nullable=False),
        sa.Column("descripcion", sa.String(), nullable=False),
        sa.Column("contacto", sa.String(), nullable=False),
        sa.Column("activo", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint(
            "tipo IN ('beca', 'alimentacion', 'bienestar', 'ingresos', 'otro')", name="ck_support_resources_tipo"
        ),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_support_resources_organization_id", "support_resources", ["organization_id"])
    op.create_table(
        "support_interests",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("resource_id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["resource_id"], ["support_resources.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "resource_id", name="uq_support_interest_user_resource"),
    )
    op.create_index("ix_support_interests_user_id", "support_interests", ["user_id"])
    op.create_index("ix_support_interests_resource_id", "support_interests", ["resource_id"])
    op.create_table(
        "planned_expenses",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("descripcion", sa.String(), nullable=False),
        sa.Column("monto", sa.Numeric(12, 2), nullable=False),
        sa.Column("fecha", sa.Date(), nullable=False),
        sa.Column("hecho", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_planned_expenses_user_id", "planned_expenses", ["user_id"])
    op.create_table(
        "receivables",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("expense_id", sa.Integer(), nullable=True),
        sa.Column("persona", sa.String(), nullable=False),
        sa.Column("descripcion", sa.String(), nullable=False),
        sa.Column("monto", sa.Numeric(12, 2), nullable=False),
        sa.Column("fecha", sa.Date(), nullable=False),
        sa.Column("pagado", sa.Boolean(), nullable=False),
        sa.Column("pagado_en", sa.Date(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["expense_id"], ["expenses.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_receivables_user_id", "receivables", ["user_id"])
    op.create_index("ix_receivables_expense_id", "receivables", ["expense_id"])
    op.add_column(
        "subscriptions",
        sa.Column("comparte_progreso", sa.Boolean(), nullable=False, server_default=sa.false()),
    )


def downgrade() -> None:
    op.drop_column("subscriptions", "comparte_progreso")
    op.drop_table("receivables")
    op.drop_table("planned_expenses")
    op.drop_table("support_interests")
    op.drop_table("support_resources")
