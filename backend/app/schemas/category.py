from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict


class CategoryCreate(BaseModel):
    nombre: str
    tipo: Literal["fijo", "opcional"] = "opcional"
    limite: Decimal | None = None


class CategoryUpdate(BaseModel):
    nombre: str | None = None
    tipo: Literal["fijo", "opcional"] | None = None
    limite: Decimal | None = None


class CategoryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    nombre: str
    owner_id: int | None
    tipo: str
    limite: Decimal | None
