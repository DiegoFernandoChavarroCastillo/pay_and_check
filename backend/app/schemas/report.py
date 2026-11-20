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


class TrendSemanaResponse(BaseModel):
    semana_inicio: date
    semana_fin: date
    total: Decimal
    por_categoria: list[CategoriaGastoResponse]


class TrendDiaResponse(BaseModel):
    fecha: date
    total: Decimal


class TrendsResponse(BaseModel):
    # De la semana más antigua a la actual.
    semanas: list[TrendSemanaResponse]
    # Día a día de la semana anterior y la actual (14 días).
    dias: list[TrendDiaResponse]
    promedio_semanal: Decimal
    # None si la semana anterior no tuvo gasto.
    variacion_vs_semana_anterior_pct: int | None


class WrappedCategoriaTop(BaseModel):
    categoria: str
    monto: Decimal
    porcentaje: int


class WrappedGastoMayor(BaseModel):
    descripcion: str
    monto: Decimal
    fecha: date
    categoria: str


class WrappedDia(BaseModel):
    fecha: date
    monto: Decimal


class MonthlyWrappedResponse(BaseModel):
    anio: int
    mes: int
    gasto_total: Decimal
    ingresos_total: Decimal
    num_gastos: int
    dias_con_registro: int
    categoria_top: WrappedCategoriaTop | None
    gasto_mayor: WrappedGastoMayor | None
    dia_mas_gasto: WrappedDia | None
    variacion_vs_mes_anterior_pct: int | None
    ratio_ahorro: Decimal | None
    aportado_a_metas: Decimal
    puntos_ganados: int
    insignias: list[str]
    animo_frecuente: str | None
    frase_coach: str
