from datetime import datetime
from typing import Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import BaseModel, ConfigDict, computed_field, field_validator

from app.core.config import POLITICA_VERSION
from app.schemas.common import Nombre

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
    politica_version: str | None
    politica_aceptada_at: datetime | None
    sms_consent_at: datetime | None

    @computed_field
    @property
    def politica_vigente(self) -> bool:
        """True si aceptó la versión vigente; si es False la app muestra la política antes de dejarla entrar."""
        return self.politica_version == POLITICA_VERSION


class UserUpdate(BaseModel):
    nombre: Nombre | None = None
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
