from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

# "recurrente" no se acepta desde la API: solo lo asigna sync_recurring_expenses.
ExpenseSourceInput = Literal["manual", "texto", "voz", "ocr", "sms"]


class ExpenseCreate(BaseModel):
    monto: Decimal
    category_id: int
    descripcion: str
    fecha: date
    source: ExpenseSourceInput = "manual"
    comercio: str | None = None
    # El texto/voz/recibo original, cuando el gasto se confirma tras un parseo con IA.
    texto_original: str | None = None


class ExpenseUpdate(BaseModel):
    monto: Decimal | None = None
    category_id: int | None = None
    descripcion: str | None = None
    comercio: str | None = None
    fecha: date | None = None


class ExpenseParseRequest(BaseModel):
    texto: str


class ExpenseParseResponse(BaseModel):
    # "ingreso" cuando el texto describe dinero recibido; entonces no hay categoría
    # y la app lo confirma como ingreso (POST /incomes), no como gasto.
    tipo: Literal["gasto", "ingreso"] = "gasto"
    monto: Decimal
    categoria: str | None
    descripcion: str
    fecha: date


class ReceiptParseRequest(BaseModel):
    # Texto que el OCR del teléfono reconoció en el recibo (la foto no se sube).
    texto_ocr: str = Field(min_length=1, max_length=6000)


class ReceiptParseResponse(ExpenseParseResponse):
    comercio: str | None


class ExpenseResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    budget_id: int
    category_id: int
    monto: Decimal
    descripcion: str
    texto_original: str | None
    source: str
    comercio: str | None
    fecha: date
    created_at: datetime
