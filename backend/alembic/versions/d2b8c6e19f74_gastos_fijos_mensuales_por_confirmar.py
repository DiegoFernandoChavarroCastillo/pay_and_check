"""gastos fijos mensuales por confirmar

Revision ID: d2b8c6e19f74
Revises: c9f3a5d27e41
Create Date: 2026-10-12

Los gastos fijos pueden ser mensuales y ya no se registran solos: quedan por pagar hasta que la
persona los confirma u omite.
"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d2b8c6e19f74"
down_revision: str | Sequence[str] | None = "c9f3a5d27e41"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "recurring_expenses", sa.Column("frecuencia", sa.String(), nullable=False, server_default="semanal")
    )
    op.add_column("recurring_expenses", sa.Column("dia_mes", sa.Integer(), nullable=True))
    op.add_column("recurring_expenses", sa.Column("omitido_hasta", sa.Date(), nullable=True))
    op.create_check_constraint(
        "ck_recurring_frecuencia_valida", "recurring_expenses", "frecuencia IN ('semanal', 'mensual')"
    )


def downgrade() -> None:
    op.drop_constraint("ck_recurring_frecuencia_valida", "recurring_expenses", type_="check")
    op.drop_column("recurring_expenses", "omitido_hasta")
    op.drop_column("recurring_expenses", "dia_mes")
    op.drop_column("recurring_expenses", "frecuencia")
