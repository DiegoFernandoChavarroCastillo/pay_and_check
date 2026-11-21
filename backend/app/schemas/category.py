from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict

from app.schemas.common import Monto, Nombre


class CategoryCreate(BaseModel):
    nombre: Nombre
    tipo: Literal["fijo", "opcional"] = "opcional"
    limite: Monto | None = None


class CategoryUpdate(BaseModel):
    nombre: Nombre | None = None
    tipo: Literal["fijo", "opcional"] | None = None
    limite: Monto | None = None


class CategoryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    nombre: str
    owner_id: int | None
    tipo: str
    limite: Decimal | None
