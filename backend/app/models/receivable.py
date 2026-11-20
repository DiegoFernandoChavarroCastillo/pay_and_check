from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Column, Numeric
from sqlmodel import Field, SQLModel

from app.core.time import utcnow


class Receivable(SQLModel, table=True):
    """Lo que otra persona le debe a quien pagó una vaca ("lo pagué por 4"). El gasto de la persona es solo su
    parte (`Expense`); estas filas son las partes de los demás, hasta que se marcan como pagadas."""

    __tablename__ = "receivables"

    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="users.id", index=True)
    expense_id: int | None = Field(default=None, foreign_key="expenses.id", index=True)
    persona: str
    descripcion: str
    monto: Decimal = Field(sa_column=Column(Numeric(12, 2), nullable=False))
    fecha: date
    pagado: bool = Field(default=False)
    pagado_en: date | None = Field(default=None)
    created_at: datetime = Field(default_factory=utcnow)
