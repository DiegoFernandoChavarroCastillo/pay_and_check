from datetime import UTC, datetime

from sqlalchemy import CheckConstraint
from sqlmodel import Field, SQLModel


class User(SQLModel, table=True):
    __tablename__ = "users"
    __table_args__ = (
        # Un usuario debe tener al menos un método de login (password o Google),
        # nunca ninguno de los dos.
        CheckConstraint(
            "hashed_password IS NOT NULL OR google_id IS NOT NULL",
            name="ck_users_has_login_method",
        ),
    )

    id: int | None = Field(default=None, primary_key=True)
    email: str = Field(unique=True, index=True)
    hashed_password: str | None = Field(default=None)
    google_id: str | None = Field(default=None, unique=True, index=True)
    nombre: str
    # Estilo del coach: motivador | directo | humoristico | minimalista.
    coach_tone: str = Field(default="motivador")
    idioma: str = Field(default="es")
    # Nombre IANA (ej. "America/Bogota") — define qué día es "hoy" para el usuario.
    zona_horaria: str = Field(default="America/Bogota")
    # Preparado para el modo familiar/grupal — no se usa en el MVP.
    group_id: int | None = Field(default=None, foreign_key="groups.id")
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    # Consentimiento (Ley 1581 de 2012): qué versión de la política aceptó y cuándo. None = aún no la acepta
    # (cuentas creadas con Google o antes de existir la política); la app le pide aceptarla al entrar.
    politica_version: str | None = Field(default=None)
    politica_aceptada_at: datetime | None = Field(default=None)
    # Permiso aparte para leer los SMS bancarios en el teléfono. None = no lo ha dado o lo revocó.
    sms_consent_at: datetime | None = Field(default=None)
