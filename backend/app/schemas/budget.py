from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, model_validator


class BudgetCreate(BaseModel):
    monto_total: Decimal
    fecha_inicio: date
    fecha_fin: date

    @model_validator(mode="after")
    def fechas_validas(self) -> "BudgetCreate":
        if self.fecha_fin <= self.fecha_inicio:
            raise ValueError("fecha_fin debe ser posterior a fecha_inicio.")
        return self


class BudgetUpdate(BaseModel):
    monto_total: Decimal | None = None
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
    disponible_total: Decimal
    dias_restantes: int
    semanas_restantes: Decimal
    disponible_por_dia: Decimal
    disponible_por_semana: Decimal
    en_riesgo: bool
    fecha_proyectada_agotamiento: date | None
    desglose_por_categoria: list[CategoriaDesgloseResponse]
