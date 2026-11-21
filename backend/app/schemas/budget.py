from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.schemas.common import Monto


class BudgetCreate(BaseModel):
    monto_total: Monto
    fecha_inicio: date
    fecha_fin: date

    @model_validator(mode="after")
    def fechas_validas(self) -> "BudgetCreate":
        if self.fecha_fin <= self.fecha_inicio:
            raise ValueError("fecha_fin debe ser posterior a fecha_inicio.")
        return self


class BudgetUpdate(BaseModel):
    monto_total: Monto | None = None
    fecha_inicio: date | None = None
    fecha_fin: date | None = None


class BudgetResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    monto_total: Decimal
    fecha_inicio: date
    fecha_fin: date
    created_at: datetime


class CategoriaDesgloseResponse(BaseModel):
    categoria: str
    tipo: str
    gastado: Decimal
    limite: Decimal | None
    excedido: bool


class BudgetSummaryResponse(BaseModel):
    budget: BudgetResponse
    gastado_total: Decimal
    ingresos_total: Decimal
    apartado_total: Decimal
    disponible_total: Decimal
    dias_restantes: int
    semanas_restantes: Decimal
    disponible_por_dia: Decimal
    disponible_por_semana: Decimal
    en_riesgo: bool
    fecha_proyectada_agotamiento: date | None
    desglose_por_categoria: list[CategoriaDesgloseResponse]


class SimulateRequest(BaseModel):
    monto: Decimal = Field(gt=0, le=Decimal("100000000"))


class SimulateGoalImpact(BaseModel):
    nombre: str
    # A cuántos días del ahorro que pide la meta (para llegar a tiempo) equivale la compra.
    dias_equivalentes: int
    aporte_por_dia: Decimal


class SimulateResponse(BaseModel):
    """ "¿Me alcanza?": cómo quedaría el presupuesto si hoy se gastara `monto`. No guarda nada ni usa IA."""

    monto: Decimal
    alcanza: bool
    disponible_por_dia_antes: Decimal
    disponible_por_dia_despues: Decimal
    disponible_total_despues: Decimal
    dias_restantes: int
    en_riesgo_despues: bool
    fecha_agotamiento_despues: date | None
    meta: SimulateGoalImpact | None = None
