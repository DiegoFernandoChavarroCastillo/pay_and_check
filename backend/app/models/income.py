from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Column, Numeric
from sqlmodel import Field, SQLModel

from app.core.time import utcnow


class Income(SQLModel, table=True):
    """Dinero extra que amplía el presupuesto (ej. lo que le mandan al usuario),
    separado de `monto_total` para no perder el rastro de cuándo y por qué
    entró esa plata."""

    __tablename__ = "incomes"

    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="users.id", index=True)
    budget_id: int = Field(foreign_key="budgets.id", index=True)
    monto: Decimal = Field(sa_column=Column(Numeric(12, 2), nullable=False))
    descripcion: str
    fecha: date
    created_at: datetime = Field(default_factory=utcnow)
