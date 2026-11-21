"""Tipos compartidos por los esquemas de entrada: montos y textos con límites.

Sin estos límites la API aceptaba gastos e ingresos negativos o en cero (inflaban el disponible) y un monto
enorme reventaba la columna NUMERIC(12, 2) de Postgres con un 500."""

from decimal import Decimal
from typing import Annotated

from pydantic import AfterValidator, Field

# Mil millones de pesos: muy por encima de cualquier movimiento de un estudiante y por debajo del máximo de la
# columna NUMERIC(12, 2) (10^10).
MONTO_MAXIMO = Decimal("1000000000")

Monto = Annotated[Decimal, Field(gt=0, le=MONTO_MAXIMO, decimal_places=2)]


def _sin_espacios_extremos(valor: str) -> str:
    return valor.strip()


# Descripciones de movimientos, nombres de categorías, etc. Llegan a la lista de la app y, recortados, al
# contexto de la IA: un texto de miles de caracteres no aporta nada y solo ocupa espacio.
Descripcion = Annotated[str, AfterValidator(_sin_espacios_extremos), Field(max_length=200)]
Nombre = Annotated[str, AfterValidator(_sin_espacios_extremos), Field(min_length=1, max_length=80)]
