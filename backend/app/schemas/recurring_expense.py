from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class RecurringExpenseCreate(BaseModel):
    category_id: int
    monto: Decimal
    descripcion: str
    dia_semana: int = Field(ge=0, le=6)
    fecha_inicio: date | None = None  # default: hoy (no rellena semanas pasadas)


class RecurringExpenseUpdate(BaseModel):
    category_id: int | None = None
    monto: Decimal | None = None
    descripcion: str | None = None
    dia_semana: int | None = Field(default=None, ge=0, le=6)
    activo: bool | None = None


class RecurringExpenseResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    category_id: int
    monto: Decimal
    descripcion: str
    dia_semana: int
    fecha_inicio: date
    activo: bool
    created_at: datetime
