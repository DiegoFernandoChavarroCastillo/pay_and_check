from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class GoalCreate(BaseModel):
    nombre: str = Field(min_length=1, max_length=80)
    monto_objetivo: Decimal = Field(gt=0)
    fecha_limite: date | None = None


class GoalUpdate(BaseModel):
    nombre: str | None = Field(default=None, min_length=1, max_length=80)
    monto_objetivo: Decimal | None = Field(default=None, gt=0)
    fecha_limite: date | None = None


class ContributionCreate(BaseModel):
    monto: Decimal = Field(gt=0)


class ContributionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    monto: Decimal
    fecha: date
    created_at: datetime


class GoalResponse(BaseModel):
    id: int
    nombre: str
    monto_objetivo: Decimal
    fecha_limite: date | None
    estado: str
    cumplida_en: date | None
    # Calculado a partir de los aportes reales, nunca informado por el usuario.
    aportado: Decimal
    progreso: Decimal
    aportes: list[ContributionResponse]
    created_at: datetime
