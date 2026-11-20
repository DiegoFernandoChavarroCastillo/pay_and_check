"""panel institucional: token de acceso por organizacion

Revision ID: b3d7e1f04a26
Revises: a9e4d2c71f38
Create Date: 2026-11-19

El panel agregado para Bienestar Universitario (`GET /panel/{id}`) se abre con un token por organización. Sin
token la organización no tiene panel.
"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b3d7e1f04a26"
down_revision: str | Sequence[str] | None = "a9e4d2c71f38"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("organizations", sa.Column("panel_token", sa.String(), nullable=True))


def downgrade() -> None:
    op.drop_column("organizations", "panel_token")
