"""Esquemas de las funciones añadidas tras el análisis de competidores (noviembre 2026)."""

from datetime import date
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, field_validator

# --- Apoyos de la universidad -----------------------------------------------------------------------------


class SupportResourceResponse(BaseModel):
    id: int
    tipo: str
    titulo: str
    descripcion: str
    contacto: str
    me_interesa: bool


class SupportListResponse(BaseModel):
    organizacion: str | None
    # "en_riesgo" | "estres" | None: por qué la app los está sugiriendo ahora.
    motivo_sugerencia: str | None
    apoyos: list[SupportResourceResponse]


# --- Gastos previstos --------------------------------------------------------------------------------------


class PlannedExpenseCreate(BaseModel):
    descripcion: str = Field(min_length=1, max_length=120)
    monto: Decimal = Field(gt=0, le=Decimal("100000000"))
    fecha: date


class PlannedExpenseResponse(BaseModel):
    id: int
    descripcion: str
    monto: Decimal
    fecha: date
    hecho: bool
    dias: int | None = None
    por_semana: Decimal | None = None
    margen_semanal: Decimal | None = None


# --- Vacas -------------------------------------------------------------------------------------------------


class SplitCreate(BaseModel):
    """ "Lo pagué por N personas": se registra solo la parte propia como gasto y las demás quedan por cobrar."""

    monto_total: Decimal = Field(gt=0, le=Decimal("100000000"))
    category_id: int
    descripcion: str = Field(min_length=1, max_length=200)
    fecha: date
    # Los demás (sin contar a quien pagó). Entre 1 y 20 personas.
    personas: list[str] = Field(min_length=1, max_length=20)

    @field_validator("personas")
    @classmethod
    def _sin_vacios(cls, v: list[str]) -> list[str]:
        limpias = [p.strip()[:60] for p in v]
        if any(not p for p in limpias):
            raise ValueError("Cada persona necesita un nombre.")
        return limpias


class ReceivableResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    expense_id: int | None
    persona: str
    descripcion: str
    monto: Decimal
    fecha: date
    pagado: bool
    pagado_en: date | None


class SplitResponse(BaseModel):
    expense_id: int
    mi_parte: Decimal
    por_cobrar: list[ReceivableResponse]


class ReceivableSummary(BaseModel):
    total_pendiente: Decimal
    pendientes: list[ReceivableResponse]


# --- Gastos hormiga y suscripciones --------------------------------------------------------------------------


class RepeatedSpendResponse(BaseModel):
    nombre: str
    tipo: str
    veces: int
    total: Decimal
    por_mes: Decimal
    por_semestre: Decimal


# --- Crédito -----------------------------------------------------------------------------------------------


class CreditRequest(BaseModel):
    monto: Decimal = Field(gt=0, le=Decimal("100000000"))
    cuotas: int = Field(ge=1, le=120)
    tasa_ea: Decimal = Field(ge=0, le=Decimal("200"))  # tasa efectiva anual en %
    cargo_mensual: Decimal = Field(default=Decimal("0"), ge=0, le=Decimal("1000000"))  # cuota de manejo, seguro


class CreditResponse(BaseModel):
    cuota: Decimal
    cuotas: int
    tasa_mensual: Decimal
    total_pagado: Decimal
    intereses: Decimal
    por_dia: Decimal
    # Con presupuesto activo: el número del día de hoy y cómo quedaría pagando la cuota.
    disponible_por_dia: Decimal | None = None
    disponible_por_dia_con_cuota: Decimal | None = None


# --- Familia -----------------------------------------------------------------------------------------------


class ShareProgressRequest(BaseModel):
    comparte: bool


class FamilyMemberProgress(BaseModel):
    nombre: str
    comparte: bool
    racha: int | None
    constancia: Decimal | None
    metas_activas: int | None
    progreso_metas: Decimal | None
    presupuesto_alcanza: bool | None
