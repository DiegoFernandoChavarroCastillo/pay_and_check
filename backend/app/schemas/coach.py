from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

Animo = Literal["ansioso", "preocupado", "neutral", "tranquilo", "confiado"]


class CheckinCreate(BaseModel):
    animo: Animo
    nota: str | None = Field(default=None, max_length=500)


class CheckinResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    fecha: date
    animo: str
    nota: str | None
    created_at: datetime


class ReactionRequest(BaseModel):
    expense_id: int


class CoachTextResponse(BaseModel):
    mensaje: str


class InsightAction(BaseModel):
    tipo: str
    etiqueta: str
    payload: dict


class InsightResponse(BaseModel):
    tipo: str
    mensaje: str
    descripcion: str
    datos: dict
    accion: InsightAction | None


class ChatRequest(BaseModel):
    mensaje: str = Field(min_length=1, max_length=1000)


class ChatMessageResponse(BaseModel):
    id: int
    rol: Literal["usuario", "coach"]
    contenido: str
    created_at: datetime
