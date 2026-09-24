from datetime import UTC, date, datetime
from decimal import Decimal

from sqlalchemy import Column, Numeric
from sqlmodel import Field, SQLModel


class Budget(SQLModel, table=True):
    __tablename__ = "budgets"

    id: int | None = Field(default=None, primary_key=True)
    owner_id: int = Field(foreign_key="users.id", index=True)
    monto_total: Decimal = Field(sa_column=Column(Numeric(12, 2), nullable=False))
    fecha_inicio: date
    fecha_fin: date
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
