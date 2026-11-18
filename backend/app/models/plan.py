from datetime import date, datetime

from sqlalchemy import CheckConstraint
from sqlmodel import Field, SQLModel

from app.core.time import utcnow

PLANES = ("gratis", "institucional", "premium", "familiar")
TIPOS_CODIGO = ("convenio", "familiar")


class Organization(SQLModel, table=True):
    """Quien paga un plan institucional (la universidad, ej. "ECI")."""

    __tablename__ = "organizations"

    id: int | None = Field(default=None, primary_key=True)
    nombre: str = Field(unique=True, index=True)
    activa: bool = Field(default=True)
    created_at: datetime = Field(default_factory=utcnow)


class LicenseCode(SQLModel, table=True):
    """Código que se canjea por un plan (docs/planes.md). Hay dos tipos:
    - "convenio": de una organización; activa el plan Institucional. Puede vencer y tener tope de usos.
    - "familiar": de un grupo; une a la persona a esa familia. Se limita por integrantes, no por usos."""

    __tablename__ = "license_codes"
    __table_args__ = (
        CheckConstraint("tipo IN ('convenio', 'familiar')", name="ck_license_codes_tipo_valido"),
        CheckConstraint(
            "(tipo = 'convenio' AND organization_id IS NOT NULL AND group_id IS NULL) "
            "OR (tipo = 'familiar' AND group_id IS NOT NULL AND organization_id IS NULL)",
            name="ck_license_codes_destino_segun_tipo",
        ),
    )

    id: int | None = Field(default=None, primary_key=True)
    codigo: str = Field(unique=True, index=True)  # en mayúsculas
    tipo: str
    organization_id: int | None = Field(default=None, foreign_key="organizations.id")
    group_id: int | None = Field(default=None, foreign_key="groups.id")
    vence_en: date | None = Field(default=None)  # último día válido, en la zona de quien canjea
    max_usos: int | None = Field(default=None)
    usos: int = Field(default=0)
    created_at: datetime = Field(default_factory=utcnow)


class Subscription(SQLModel, table=True):
    """El plan de una persona. Sin fila equivale a Gratis: la cuenta nueva no necesita una.

    La familia vive en `users.group_id`; `es_titular` marca a quien la activó (si esa persona se va, la
    familia se disuelve)."""

    __tablename__ = "subscriptions"
    __table_args__ = (
        CheckConstraint(
            "plan IN ('gratis', 'institucional', 'premium', 'familiar')",
            name="ck_subscriptions_plan_valido",
        ),
    )

    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="users.id", unique=True, index=True)
    plan: str
    organization_id: int | None = Field(default=None, foreign_key="organizations.id")
    license_code_id: int | None = Field(default=None, foreign_key="license_codes.id")
    es_titular: bool = Field(default=False)
    iniciada_en: datetime = Field(default_factory=utcnow)
