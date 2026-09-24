from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict


class IncomeCreate(BaseModel):
    monto: Decimal
    descripcion: str
    fecha: date


class IncomeUpdate(BaseModel):
    monto: Decimal | None = None
    descripcion: str | None = None
    fecha: date | None = None


class IncomeResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    budget_id: int
    monto: Decimal
    descripcion: str
    fecha: date
    created_at: datetime
