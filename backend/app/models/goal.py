from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import CheckConstraint, Column, Numeric
from sqlmodel import Field, SQLModel

from app.core.time import utcnow


class Goal(SQLModel, table=True):
    """Meta de ahorro. El progreso nunca se auto-reporta: es la suma de sus
    `GoalContribution`, que solo se aceptan si hay dinero disponible."""

    __tablename__ = "goals"
    __table_args__ = (
        CheckConstraint("estado IN ('activa', 'cumplida')", name="ck_goals_estado_valido"),
    )

    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="users.id", index=True)
    nombre: str
    monto_objetivo: Decimal = Field(sa_column=Column(Numeric(12, 2), nullable=False))
    fecha_limite: date | None = Field(default=None)
    estado: str = Field(default="activa")
    cumplida_en: date | None = Field(default=None)
    created_at: datetime = Field(default_factory=utcnow)


class GoalContribution(SQLModel, table=True):
    """Dinero "apartado" hacia una meta. Es virtual (no hay banco conectado):
    se descuenta del disponible del presupuesto al que pertenece su fecha."""

    __tablename__ = "goal_contributions"

    id: int | None = Field(default=None, primary_key=True)
    goal_id: int = Field(foreign_key="goals.id", index=True)
    user_id: int = Field(foreign_key="users.id", index=True)
    budget_id: int = Field(foreign_key="budgets.id", index=True)
    monto: Decimal = Field(sa_column=Column(Numeric(12, 2), nullable=False))
    fecha: date
    created_at: datetime = Field(default_factory=utcnow)
