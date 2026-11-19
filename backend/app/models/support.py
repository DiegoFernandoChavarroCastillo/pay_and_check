from datetime import datetime

from sqlalchemy import CheckConstraint, UniqueConstraint
from sqlmodel import Field, SQLModel

from app.core.time import utcnow

TIPOS_APOYO = ("beca", "alimentacion", "bienestar", "ingresos", "otro")


class SupportResource(SQLModel, table=True):
    """Un apoyo que ofrece la universidad del convenio (beca, auxilio de alimentación, apoyo psicológico,
    monitorías pagas…). Lo ven los estudiantes con plan Institucional de esa organización."""

    __tablename__ = "support_resources"
    __table_args__ = (
        CheckConstraint(
            "tipo IN ('beca', 'alimentacion', 'bienestar', 'ingresos', 'otro')", name="ck_support_resources_tipo"
        ),
    )

    id: int | None = Field(default=None, primary_key=True)
    organization_id: int = Field(foreign_key="organizations.id", index=True)
    tipo: str
    titulo: str
    descripcion: str
    # Cómo pedirlo: un enlace o un texto ("Oficina de Bienestar, bloque A, piso 2").
    contacto: str
    activo: bool = Field(default=True)
    created_at: datetime = Field(default_factory=utcnow)


class SupportInterest(SQLModel, table=True):
    """La persona tocó "Me interesa" en un apoyo. A la universidad solo le llega la cuenta agregada por apoyo
    (anonimato k ≥ 5 en el panel), nunca quién fue: el contacto lo hace el estudiante por su cuenta."""

    __tablename__ = "support_interests"
    __table_args__ = (UniqueConstraint("user_id", "resource_id", name="uq_support_interest_user_resource"),)

    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="users.id", index=True)
    resource_id: int = Field(foreign_key="support_resources.id", index=True)
    created_at: datetime = Field(default_factory=utcnow)
