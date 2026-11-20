"""app movil fase 0: perfil de usuario (tono, idioma, zona horaria) y origen del gasto

Revision ID: c3d81f0a7b21
Revises: ba1ba56966a7
Create Date: 2026-10-11 03:30:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa
import sqlmodel

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'c3d81f0a7b21'
down_revision: str | Sequence[str] | None = 'ba1ba56966a7'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    # server_default en todas: ya existen usuarios y gastos, y agregar una
    # columna NOT NULL sobre filas existentes sin default falla en Postgres.
    op.add_column(
        'users',
        sa.Column('coach_tone', sqlmodel.sql.sqltypes.AutoString(), nullable=False, server_default='motivador'),
    )
    op.add_column(
        'users',
        sa.Column('idioma', sqlmodel.sql.sqltypes.AutoString(), nullable=False, server_default='es'),
    )
    op.add_column(
        'users',
        sa.Column(
            'zona_horaria', sqlmodel.sql.sqltypes.AutoString(), nullable=False, server_default='America/Bogota'
        ),
    )
    op.add_column(
        'expenses',
        sa.Column('source', sqlmodel.sql.sqltypes.AutoString(), nullable=False, server_default='manual'),
    )
    op.add_column('expenses', sa.Column('comercio', sqlmodel.sql.sqltypes.AutoString(), nullable=True))

    # Los gastos previos sí permiten deducir su origen.
    op.execute("UPDATE expenses SET source = 'texto' WHERE texto_original IS NOT NULL")
    op.execute("UPDATE expenses SET source = 'recurrente' WHERE recurring_expense_id IS NOT NULL")

    op.create_check_constraint(
        'ck_expenses_source_valido',
        'expenses',
        "source IN ('manual', 'texto', 'voz', 'ocr', 'sms', 'recurrente')",
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint('ck_expenses_source_valido', 'expenses', type_='check')
    op.drop_column('expenses', 'comercio')
    op.drop_column('expenses', 'source')
    op.drop_column('users', 'zona_horaria')
    op.drop_column('users', 'idioma')
    op.drop_column('users', 'coach_tone')
