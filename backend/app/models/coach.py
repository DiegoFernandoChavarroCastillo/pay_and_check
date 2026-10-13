from datetime import date, datetime

from sqlalchemy import CheckConstraint, UniqueConstraint
from sqlmodel import Field, SQLModel

from app.core.time import utcnow

ANIMOS = ("ansioso", "preocupado", "neutral", "tranquilo", "confiado")
# Ánimos que el análisis de patrones trata como "día difícil".
ANIMOS_BAJOS = ("ansioso", "preocupado")


class EmotionalCheckin(SQLModel, table=True):
    """Cómo se siente el usuario con su dinero ese día. Uno por día: registrar
    de nuevo el mismo día reemplaza el anterior."""

    __tablename__ = "emotional_checkins"
    __table_args__ = (
        UniqueConstraint("user_id", "fecha", name="uq_checkins_user_fecha"),
        CheckConstraint(
            "animo IN ('ansioso', 'preocupado', 'neutral', 'tranquilo', 'confiado')",
            name="ck_checkins_animo_valido",
        ),
    )

    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="users.id", index=True)
    fecha: date
    animo: str
    nota: str | None = Field(default=None)
    created_at: datetime = Field(default_factory=utcnow)


class CoachMessage(SQLModel, table=True):
    """Historial del coach. `tipo`:
    - "insights": caché diaria de los consejos (contenido = JSON).
    - "chat_user" / "chat_coach": turnos del chat.
    """

    __tablename__ = "coach_messages"

    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="users.id", index=True)
    tipo: str = Field(index=True)
    contenido: str
    fecha: date
    created_at: datetime = Field(default_factory=utcnow)
