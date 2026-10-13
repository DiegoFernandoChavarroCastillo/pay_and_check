"""mas tipos de reto

Revision ID: c9f3a5d27e41
Revises: b7e2f4a61d58
Create Date: 2026-10-12

Tres tipos de reto nuevos: registro_diario, aportar_meta y semana_en_ritmo.
"""
from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c9f3a5d27e41"
down_revision: str | Sequence[str] | None = "b7e2f4a61d58"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_ANTES = "tipo IN ('reducir_categoria', 'dias_sin_gasto', 'checkins')"
_AHORA = (
    "tipo IN ('reducir_categoria', 'dias_sin_gasto', 'checkins', 'registro_diario', 'aportar_meta', "
    "'semana_en_ritmo')"
)


def upgrade() -> None:
    op.drop_constraint("ck_challenges_tipo_valido", "challenges", type_="check")
    op.create_check_constraint("ck_challenges_tipo_valido", "challenges", _AHORA)


def downgrade() -> None:
    op.execute(f"DELETE FROM challenges WHERE NOT ({_ANTES})")
    op.drop_constraint("ck_challenges_tipo_valido", "challenges", type_="check")
    op.create_check_constraint("ck_challenges_tipo_valido", "challenges", _ANTES)
