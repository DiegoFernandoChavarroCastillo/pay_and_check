from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import CheckConstraint, Column, Numeric
from sqlmodel import Field, SQLModel

from app.core.time import utcnow


class RecurringExpense(SQLModel, table=True):
    """Un gasto fijo que se repite cada semana o cada mes (arriendo, recibo de la luz, transporte).

    No se registra solo: el día que toca queda "por pagar" y la persona lo confirma; ahí se crea el
    gasto y se descuenta del disponible.

    - `frecuencia` "semanal": vence cada `dia_semana` (0=lunes..6=domingo).
    - `frecuencia` "mensual": vence cada `dia_mes` (1..31; en meses más cortos, el último día).
    - `fecha_inicio`: desde cuándo cuenta (por defecto hoy, para no deber vencimientos anteriores).
    - `omitido_hasta`: último vencimiento que la persona decidió saltarse.
    """

    __tablename__ = "recurring_expenses"
    __table_args__ = (
        CheckConstraint("frecuencia IN ('semanal', 'mensual')", name="ck_recurring_frecuencia_valida"),
    )

    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="users.id", index=True)
    category_id: int = Field(foreign_key="categories.id")
    monto: Decimal = Field(sa_column=Column(Numeric(12, 2), nullable=False))
    descripcion: str
    frecuencia: str = Field(default="semanal")
    dia_semana: int = Field(default=0, ge=0, le=6)
    dia_mes: int | None = Field(default=None, ge=1, le=31)
    fecha_inicio: date
    activo: bool = Field(default=True)
    omitido_hasta: date | None = Field(default=None)
    created_at: datetime = Field(default_factory=utcnow)
