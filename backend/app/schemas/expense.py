from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.common import Descripcion, Monto

# "recurrente" no se acepta desde la API: solo lo asigna el pago de un gasto fijo.
ExpenseSourceInput = Literal["manual", "texto", "voz", "ocr", "sms"]


class ExpenseCreate(BaseModel):
    monto: Monto
    category_id: int
    descripcion: Descripcion
    fecha: date
    source: ExpenseSourceInput = "manual"
    comercio: Descripcion | None = None
    # El texto/voz/recibo original, cuando el gasto se confirma tras un parseo con IA.
    texto_original: str | None = Field(default=None, max_length=6000)


class ExpenseUpdate(BaseModel):
    monto: Monto | None = None
    category_id: int | None = None
    descripcion: Descripcion | None = None
    comercio: Descripcion | None = None
    fecha: date | None = None


class ExpenseParseRequest(BaseModel):
    texto: str = Field(min_length=1, max_length=500)


class ExpenseParseResponse(BaseModel):
    # "ingreso" cuando el texto describe dinero recibido; entonces no hay categoría
    # y la app lo confirma como ingreso (POST /incomes), no como gasto.
    tipo: Literal["gasto", "ingreso"] = "gasto"
    monto: Decimal
    categoria: str | None
    descripcion: str
    fecha: date
    # Los demás movimientos de la misma frase ("almuerzo 18 mil y un uber de 12.500"): la app los confirma uno
    # tras otro. Salen de la misma llamada a la IA, así que cuentan como una sola solicitud del cupo.
    adicionales: list["ExpenseParseResponse"] = []


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
