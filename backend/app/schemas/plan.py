from datetime import date
from typing import Literal

from pydantic import BaseModel, Field


class PlanResponse(BaseModel):
    codigo: str
    precio_cop: int
    cupo_ia_mensual: int
    compartido: bool
    paga: str
    estado_demo: str
    max_integrantes: int | None


class FamiliaResponse(BaseModel):
    codigo: str
    integrantes: int
    max_integrantes: int
    es_titular: bool


class SuscripcionResponse(BaseModel):
    plan: str
    cupo_ia_mensual: int
    usadas: int
    restantes: int
    compartido: bool
    reinicia_el: date
    organizacion: str | None
    familia: FamiliaResponse | None
    aviso: str | None


class CambiarPlanRequest(BaseModel):
    plan: Literal["gratis", "institucional", "premium", "familiar"]


class CanjearRequest(BaseModel):
    codigo: str = Field(min_length=1, max_length=64)
