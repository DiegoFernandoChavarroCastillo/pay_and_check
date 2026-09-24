from decimal import Decimal

from sqlalchemy import CheckConstraint, Column, Numeric
from sqlmodel import Field, SQLModel


class Category(SQLModel, table=True):
    """owner_id nulo = categoría por defecto del sistema; con valor = personalizada del usuario.

    `tipo`: "fijo" (gasto que sí o sí ocurre, ej. transporte) vs "opcional"
    (discrecional, ej. entretenimiento). `limite`: tope de gasto de esa
    categoría durante el presupuesto activo (None = sin tope) — ver Fase 11.
    """

    __tablename__ = "categories"
    __table_args__ = (
        CheckConstraint("tipo IN ('fijo', 'opcional')", name="ck_categories_tipo_valido"),
    )

    id: int | None = Field(default=None, primary_key=True)
    nombre: str
    owner_id: int | None = Field(default=None, foreign_key="users.id", index=True)
    tipo: str = Field(default="opcional")
    limite: Decimal | None = Field(default=None, sa_column=Column(Numeric(12, 2), nullable=True))
