from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel

Plantilla = Literal["reducir_categoria", "dias_sin_gasto", "checkins"]


class ChallengeCreate(BaseModel):
    plantilla: Plantilla
    category_id: int | None = None
    porcentaje: int = 20


class ChallengeResponse(BaseModel):
    id: int
    tipo: str
    category_id: int | None
    descripcion: str
    objetivo: Decimal
    linea_base: Decimal | None
    # Calculado con los datos reales al momento de la consulta.
    valor_actual: Decimal
    fecha_inicio: date
    fecha_fin: date
    estado: str
    puntos: int


class ChallengeSuggestionResponse(BaseModel):
    plantilla: str
    category_id: int | None
    porcentaje: int | None
    titulo: str
    motivo: str
    puntos: int


class LevelResponse(BaseModel):
    numero: int
    nombre: str
    puntos_nivel: int
    puntos_siguiente: int | None


class BadgeResponse(BaseModel):
    codigo: str
    nombre: str
    descripcion: str
    desbloqueada: bool
    unlocked_at: datetime | None


class PointEventResponse(BaseModel):
    tipo: str
    puntos: int
    fecha: date


class MetricsResponse(BaseModel):
    ratio_ahorro: Decimal | None
    consistencia: Decimal
    mejora_mensual: Decimal | None


class GamificationProfileResponse(BaseModel):
    puntos: int
    nivel: LevelResponse
    racha_actual: int
    mejor_racha: int
    metricas: MetricsResponse
    insignias: list[BadgeResponse]
    eventos_recientes: list[PointEventResponse]
    # Lo otorgado en esta misma consulta, para que la app lo celebre una vez.
    nuevos_puntos: int
    nuevas_insignias: list[str]
