from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import CheckConstraint, Column, Numeric, UniqueConstraint
from sqlmodel import Field, SQLModel

from app.core.time import utcnow


class Challenge(SQLModel, table=True):
    """Reto con ventana de fechas, verificado con los datos reales del usuario.

    `tipo`:
    - "reducir_categoria": gastar como máximo `objetivo` en `category_id`
      (`linea_base` = lo gastado en los 7 días previos).
    - "dias_sin_gasto": acumular `objetivo` días sin gasto opcional.
    - "checkins": hacer `objetivo` check-ins emocionales.
    """

    __tablename__ = "challenges"
    __table_args__ = (
        CheckConstraint(
            "tipo IN ('reducir_categoria', 'dias_sin_gasto', 'checkins')", name="ck_challenges_tipo_valido"
        ),
        CheckConstraint("estado IN ('activo', 'cumplido', 'fallido')", name="ck_challenges_estado_valido"),
    )

    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="users.id", index=True)
    tipo: str
    category_id: int | None = Field(default=None, foreign_key="categories.id")
    descripcion: str
    objetivo: Decimal = Field(sa_column=Column(Numeric(12, 2), nullable=False))
    linea_base: Decimal | None = Field(default=None, sa_column=Column(Numeric(12, 2), nullable=True))
    fecha_inicio: date
    fecha_fin: date
    estado: str = Field(default="activo")
    puntos: int
    created_at: datetime = Field(default_factory=utcnow)


class Achievement(SQLModel, table=True):
    """Insignia desbloqueada. El catálogo (nombre, descripción) vive en
    `services/gamification.py`; aquí solo queda cuál y cuándo."""

    __tablename__ = "achievements"
    __table_args__ = (UniqueConstraint("user_id", "codigo", name="uq_achievements_user_codigo"),)

    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="users.id", index=True)
    codigo: str
    unlocked_at: datetime = Field(default_factory=utcnow)


class PointEvent(SQLModel, table=True):
    """Libro de puntos. `clave` identifica el hecho que los otorga (ej.
    "registro:2026-10-11", "reto:7"): la restricción única por usuario hace
    que recalcular nunca duplique puntos."""

    __tablename__ = "point_events"
    __table_args__ = (UniqueConstraint("user_id", "clave", name="uq_point_events_user_clave"),)

    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="users.id", index=True)
    clave: str
    tipo: str
    puntos: int
    fecha: date
    created_at: datetime = Field(default_factory=utcnow)
