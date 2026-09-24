from datetime import date
from decimal import Decimal

from pydantic import BaseModel


class CategoriaGastoResponse(BaseModel):
    categoria: str
    monto: Decimal


class WeeklyReportResponse(BaseModel):
    semana_inicio: date
    semana_fin: date
    gasto_total_semana: Decimal
    gasto_por_categoria: list[CategoriaGastoResponse]
    ritmo_esperado_semanal: Decimal
    diferencia_vs_ritmo: Decimal
    recomendaciones: str
