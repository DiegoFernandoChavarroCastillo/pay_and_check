from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import CheckConstraint, Column, Numeric, UniqueConstraint
from sqlmodel import Field, SQLModel

from app.core.time import utcnow


class Expense(SQLModel, table=True):
    __tablename__ = "expenses"
    __table_args__ = (
        CheckConstraint(
            "source IN ('manual', 'texto', 'voz', 'ocr', 'sms', 'recurrente')",
            name="ck_expenses_source_valido",
        ),
        # Una recurrencia genera como mucho un gasto por fecha: frena el
        # duplicado si dos peticiones simultáneas sincronizan a la vez. Los
        # gastos normales (recurring_expense_id nulo) no se ven afectados.
        UniqueConstraint("recurring_expense_id", "fecha", name="uq_expenses_recurrencia_fecha"),
    )

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
    # Cómo entró el gasto: manual | texto | voz | ocr | sms | recurrente.
    source: str = Field(default="manual")
    comercio: str | None = Field(default=None)
    fecha: date
    created_at: datetime = Field(default_factory=utcnow)
