from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Column, Numeric
from sqlmodel import Field, SQLModel

from app.core.time import utcnow


class Expense(SQLModel, table=True):
    __tablename__ = "expenses"

    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="users.id", index=True)
    budget_id: int = Field(foreign_key="budgets.id", index=True)
    category_id: int = Field(foreign_key="categories.id", index=True)
    monto: Decimal = Field(sa_column=Column(Numeric(12, 2), nullable=False))
    descripcion: str
    # Guarda el texto que el usuario escribió si el gasto vino de la IA (Fase 7).
    texto_original: str | None = Field(default=None)
    # Si vino de un RecurringExpense (Fase 11) — evita generarlo dos veces.
    recurring_expense_id: int | None = Field(default=None, foreign_key="recurring_expenses.id")
    fecha: date
    created_at: datetime = Field(default_factory=utcnow)
