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
    # Preparado para el modo familiar/grupal — no se usa en el MVP.
    group_id: int | None = Field(default=None, foreign_key="groups.id")
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
