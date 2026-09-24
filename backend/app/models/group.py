from sqlmodel import Field, SQLModel


class Group(SQLModel, table=True):
    """Tabla mínima preparada para el modo familiar/grupal (no usada en el MVP)."""

    __tablename__ = "groups"

    id: int | None = Field(default=None, primary_key=True)
    nombre: str
