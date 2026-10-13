"""limites propios y categorias fijas

Revision ID: b7e2f4a61d58
Revises: a1d4e7b90c33
Create Date: 2026-10-12

- `category_limits`: el límite que cada persona le pone a una categoría por defecto.
- Transporte, salud y servicios pasan a "fijo": no son gasto discrecional.
"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b7e2f4a61d58"
down_revision: str | Sequence[str] | None = "a1d4e7b90c33"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_FIJAS = "('transporte', 'salud', 'servicios')"


def upgrade() -> None:
    op.create_table(
        "category_limits",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("category_id", sa.Integer(), sa.ForeignKey("categories.id"), nullable=False),
        sa.Column("limite", sa.Numeric(12, 2), nullable=False),
        sa.UniqueConstraint("user_id", "category_id", name="uq_category_limits_user_category"),
    )
    op.create_index("ix_category_limits_user_id", "category_limits", ["user_id"])
    op.execute(f"UPDATE categories SET tipo = 'fijo' WHERE owner_id IS NULL AND nombre IN {_FIJAS}")


def downgrade() -> None:
    op.execute(f"UPDATE categories SET tipo = 'opcional' WHERE owner_id IS NULL AND nombre IN {_FIJAS}")
    op.drop_index("ix_category_limits_user_id", table_name="category_limits")
    op.drop_table("category_limits")
