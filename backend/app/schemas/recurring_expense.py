from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field, model_validator

Frecuencia = Literal["semanal", "mensual"]


class RecurringExpenseCreate(BaseModel):
    category_id: int
    monto: Decimal = Field(gt=0)
    descripcion: str
    frecuencia: Frecuencia = "semanal"
    dia_semana: int | None = Field(default=None, ge=0, le=6)
    dia_mes: int | None = Field(default=None, ge=1, le=31)
    fecha_inicio: date | None = None  # default: hoy (no debe vencimientos anteriores)

    @model_validator(mode="after")
    def dia_segun_frecuencia(self) -> "RecurringExpenseCreate":
        if self.frecuencia == "semanal" and self.dia_semana is None:
            raise ValueError("Un gasto semanal necesita el día de la semana.")
        if self.frecuencia == "mensual" and self.dia_mes is None:
            raise ValueError("Un gasto mensual necesita el día del mes.")
        return self


class RecurringExpenseUpdate(BaseModel):
    category_id: int | None = None
    monto: Decimal | None = Field(default=None, gt=0)
    descripcion: str | None = None
    dia_semana: int | None = Field(default=None, ge=0, le=6)
    dia_mes: int | None = Field(default=None, ge=1, le=31)
    activo: bool | None = None


class RecurringExpenseResponse(BaseModel):
    id: int
    category_id: int
    monto: Decimal
    descripcion: str
    frecuencia: str
    dia_semana: int
    dia_mes: int | None
    fecha_inicio: date
    activo: bool
    created_at: datetime
    # Calculados al consultar.
    proximo_vencimiento: date
    pendiente_desde: date | None


class PendingPaymentResponse(BaseModel):
    """Un gasto fijo que ya venció y espera que la persona confirme que lo pagó."""

    recurring_id: int
    category_id: int
    descripcion: str
    monto: Decimal
    fecha: date
