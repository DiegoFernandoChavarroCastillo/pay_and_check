from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict


class ExpenseCreate(BaseModel):
    monto: Decimal
    category_id: int
    descripcion: str
    fecha: date


class ExpenseUpdate(BaseModel):
    monto: Decimal | None = None
    category_id: int | None = None
    descripcion: str | None = None
    fecha: date | None = None


class ExpenseParseRequest(BaseModel):
    texto: str


class ExpenseParseResponse(BaseModel):
    monto: Decimal
    categoria: str
    descripcion: str
    fecha: date


class ExpenseResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    budget_id: int
    category_id: int
    monto: Decimal
    descripcion: str
    texto_original: str | None
    fecha: date
    created_at: datetime
