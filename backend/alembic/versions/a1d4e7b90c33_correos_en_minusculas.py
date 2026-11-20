"""correos en minusculas

Revision ID: a1d4e7b90c33
Revises: 7f2a9c4e1d05
Create Date: 2026-10-12

El login compara el correo tal cual. Desde ahora la API lo normaliza a
minúsculas; aquí se normalizan las cuentas que ya existían.
"""
from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a1d4e7b90c33"
down_revision: str | Sequence[str] | None = "7f2a9c4e1d05"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Si dos cuentas solo se distinguen por mayúsculas, se deja intacta la más nueva: unirlas es una decisión manual.
    op.execute(
        """
        UPDATE users SET email = lower(email)
        WHERE email <> lower(email)
          AND NOT EXISTS (SELECT 1 FROM users u2 WHERE u2.email = lower(users.email))
        """
    )


def downgrade() -> None:
    pass
