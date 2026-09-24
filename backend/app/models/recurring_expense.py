from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Column, Numeric
from sqlmodel import Field, SQLModel

from app.core.time import utcnow


class RecurringExpense(SQLModel, table=True):
    """Un gasto fijo que se repite cada semana (ej. transporte semanal).

    `dia_semana` (0=lunes..6=domingo) es el día de esa semana en el que el
    gasto "cuenta" como hecho. `fecha_inicio` es desde cuándo generarlo — por
    defecto hoy, para no rellenar retroactivamente semanas anteriores a que
    el usuario lo haya creado.
    """

    __tablename__ = "recurring_expenses"

    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="users.id", index=True)
    category_id: int = Field(foreign_key="categories.id")
    monto: Decimal = Field(sa_column=Column(Numeric(12, 2), nullable=False))
    descripcion: str
    dia_semana: int = Field(ge=0, le=6)
    fecha_inicio: date
    activo: bool = Field(default=True)
    created_at: datetime = Field(default_factory=utcnow)
