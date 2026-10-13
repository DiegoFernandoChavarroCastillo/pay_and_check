from datetime import UTC, date, datetime
from typing import TYPE_CHECKING
from zoneinfo import ZoneInfo

if TYPE_CHECKING:
    from app.models.user import User


def utcnow() -> datetime:
    """`default_factory` compartido para columnas `created_at` — evita repetir
    la misma lambda en cada modelo nuevo."""
    return datetime.now(UTC)


def _now(zona_horaria: str) -> datetime:
    return datetime.now(ZoneInfo(zona_horaria))


def today_for(user: "User") -> date:
    """El "hoy" del usuario según su zona horaria. `date.today()` usa el reloj
    del servidor (UTC en producción), que a las 7 pm en Colombia ya es mañana."""
    return _now(user.zona_horaria).date()
