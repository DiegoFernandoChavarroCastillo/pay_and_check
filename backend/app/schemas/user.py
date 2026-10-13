from datetime import datetime
from typing import Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import BaseModel, ConfigDict, field_validator

CoachTone = Literal["motivador", "directo", "humoristico", "minimalista"]
Idioma = Literal["es", "en"]


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: str
    nombre: str
    coach_tone: str
    idioma: str
    zona_horaria: str
    created_at: datetime


class UserUpdate(BaseModel):
    nombre: str | None = None
    coach_tone: CoachTone | None = None
    idioma: Idioma | None = None
    zona_horaria: str | None = None

    @field_validator("zona_horaria")
    @classmethod
    def zona_horaria_valida(cls, value: str | None) -> str | None:
        if value is None:
            return value
        try:
            ZoneInfo(value)
        except (ZoneInfoNotFoundError, ValueError) as exc:
            raise ValueError("zona_horaria debe ser un nombre IANA válido, ej. America/Bogota.") from exc
        return value
