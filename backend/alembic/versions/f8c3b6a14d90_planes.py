"""planes: organizaciones, codigos de canje y suscripciones

Revision ID: f8c3b6a14d90
Revises: e5a1c9d37b62
Create Date: 2026-11-18

El plan de cada persona, los convenios (organizaciones y sus códigos) y los códigos familiares. Sin fila de
suscripción equivale a Gratis, así que no hay datos que migrar.
"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "f8c3b6a14d90"
down_revision: str | Sequence[str] | None = "e5a1c9d37b62"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "organizations",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("nombre", sa.String(), nullable=False),
        sa.Column("activa", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_organizations_nombre", "organizations", ["nombre"], unique=True)

    op.create_table(
        "license_codes",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("codigo", sa.String(), nullable=False),
        sa.Column("tipo", sa.String(), nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=True),
        sa.Column("group_id", sa.Integer(), nullable=True),
        sa.Column("vence_en", sa.Date(), nullable=True),
        sa.Column("max_usos", sa.Integer(), nullable=True),
        sa.Column("usos", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint("tipo IN ('convenio', 'familiar')", name="ck_license_codes_tipo_valido"),
        sa.CheckConstraint(
            "(tipo = 'convenio' AND organization_id IS NOT NULL AND group_id IS NULL) "
            "OR (tipo = 'familiar' AND group_id IS NOT NULL AND organization_id IS NULL)",
            name="ck_license_codes_destino_segun_tipo",
        ),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.ForeignKeyConstraint(["group_id"], ["groups.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_license_codes_codigo", "license_codes", ["codigo"], unique=True)

    op.create_table(
        "subscriptions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("plan", sa.String(), nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=True),
        sa.Column("license_code_id", sa.Integer(), nullable=True),
        sa.Column("es_titular", sa.Boolean(), nullable=False),
        sa.Column("iniciada_en", sa.DateTime(), nullable=False),
        sa.CheckConstraint(
            "plan IN ('gratis', 'institucional', 'premium', 'familiar')",
            name="ck_subscriptions_plan_valido",
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.ForeignKeyConstraint(["license_code_id"], ["license_codes.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_subscriptions_user_id", "subscriptions", ["user_id"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_subscriptions_user_id", table_name="subscriptions")
    op.drop_table("subscriptions")
    op.drop_index("ix_license_codes_codigo", table_name="license_codes")
    op.drop_table("license_codes")
    op.drop_index("ix_organizations_nombre", table_name="organizations")
    op.drop_table("organizations")
