from datetime import datetime

from sqlalchemy import CheckConstraint, Index
from sqlmodel import Field, SQLModel

from app.core.time import utcnow

BLOQUEOS = ("ninguno", "cupo", "alcance", "inyeccion")


class AiUsage(SQLModel, table=True):
    """Una fila por llamada a Groq (planFinal §5, PS-21). Sin ninguna columna de texto: lo que la persona
    escribe o dicta nunca se guarda aquí, solo cuánto costó y cómo terminó.

    - `exito`: Groq respondió. Solo estas llamadas cuentan para el tope mensual.
    - `uso_respaldo`: lo que vio la persona fue un texto de respaldo (Groq falló, el tope se agotó o un
      guardrail descartó la respuesta).
    - `bloqueado_por`: "cupo" (tope agotado), "alcance" (tema ajeno en el chat), "inyeccion" (la heurística de
      entrada marcó el texto) o "ninguno".
    - `mes`: "YYYY-MM" en la zona horaria del usuario; el tope se reinicia solo al cambiar de mes."""

    __tablename__ = "ai_usage"
    __table_args__ = (
        Index("ix_ai_usage_user_mes", "user_id", "mes"),
        CheckConstraint(
            "bloqueado_por IN ('ninguno', 'cupo', 'alcance', 'inyeccion')",
            name="ck_ai_usage_bloqueado_por_valido",
        ),
    )

    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="users.id", index=True)
    tarea: str = Field(index=True)
    modelo: str
    tokens_entrada: int | None = Field(default=None)
    tokens_salida: int | None = Field(default=None)
    latencia_ms: int | None = Field(default=None)
    exito: bool = Field(default=True)
    uso_respaldo: bool = Field(default=False)
    bloqueado_por: str = Field(default="ninguno")
    mes: str
    created_at: datetime = Field(default_factory=utcnow)
