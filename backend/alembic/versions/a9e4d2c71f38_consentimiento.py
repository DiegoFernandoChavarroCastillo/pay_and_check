"""consentimiento: politica de privacidad y permiso de SMS

Revision ID: a9e4d2c71f38
Revises: f8c3b6a14d90
Create Date: 2026-11-18

Qué versión de la política aceptó cada persona y cuándo, y cuándo dio el permiso de leer SMS (PS-48). Las cuentas
que ya existían quedan sin aceptar: la app les muestra la política la próxima vez que entren.
"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a9e4d2c71f38"
down_revision: str | Sequence[str] | None = "f8c3b6a14d90"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("users", sa.Column("politica_version", sa.String(), nullable=True))
    op.add_column("users", sa.Column("politica_aceptada_at", sa.DateTime(), nullable=True))
    op.add_column("users", sa.Column("sms_consent_at", sa.DateTime(), nullable=True))


def downgrade() -> None:
    op.drop_column("users", "sms_consent_at")
    op.drop_column("users", "politica_aceptada_at")
    op.drop_column("users", "politica_version")
