from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict

from app.schemas.common import Descripcion, Monto


class IncomeCreate(BaseModel):
    monto: Monto
    descripcion: Descripcion
    fecha: date


class IncomeUpdate(BaseModel):
    monto: Monto | None = None
    descripcion: Descripcion | None = None
    fecha: date | None = None


class IncomeResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    budget_id: int
    monto: Decimal
    descripcion: str
    fecha: date
    created_at: datetime
