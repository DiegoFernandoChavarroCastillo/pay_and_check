from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Column, Numeric
from sqlmodel import Field, SQLModel

from app.core.time import utcnow


class PlannedExpense(SQLModel, table=True):
    """Un gasto grande que se sabe que viene (matrícula, libros, pasajes de vacaciones, regalos de diciembre).
    No descuenta nada por sí solo: sirve para avisar con tiempo y decir cuánto apartar por semana."""

    __tablename__ = "planned_expenses"

    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="users.id", index=True)
    descripcion: str
    monto: Decimal = Field(sa_column=Column(Numeric(12, 2), nullable=False))
    fecha: date
    hecho: bool = Field(default=False)
    created_at: datetime = Field(default_factory=utcnow)
