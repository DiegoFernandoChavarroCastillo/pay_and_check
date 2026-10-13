"""gasto recurrente unico por fecha

Revision ID: 7f2a9c4e1d05
Revises: 0c1201063953
Create Date: 2026-10-11 05:10:00.000000

"""
from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = '7f2a9c4e1d05'
down_revision: str | Sequence[str] | None = '0c1201063953'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    # Si una base ya tuviera gastos recurrentes duplicados (dos sincronizaciones
    # simultáneas antes de esta restricción), se conserva el más antiguo.
    op.execute(
        """
        DELETE FROM expenses a
        USING expenses b
        WHERE a.recurring_expense_id IS NOT NULL
          AND a.recurring_expense_id = b.recurring_expense_id
          AND a.fecha = b.fecha
          AND a.id > b.id
        """
    )
    op.create_unique_constraint('uq_expenses_recurrencia_fecha', 'expenses', ['recurring_expense_id', 'fecha'])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint('uq_expenses_recurrencia_fecha', 'expenses', type_='unique')
