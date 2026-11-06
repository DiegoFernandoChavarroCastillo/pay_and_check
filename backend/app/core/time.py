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


_MESES = {
    "es": ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre",
           "noviembre", "diciembre"],
    "en": ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October",
           "November", "December"],
}  # fmt: skip


def fmt_fecha(fecha: date, idioma: str = "es", con_anio: bool = False) -> str:
    """Fecha como se dice en voz alta ("13 de octubre"), no en formato ISO: estos textos los lee una persona."""
    if idioma == "en":
        return f"{_MESES['en'][fecha.month - 1]} {fecha.day}" + (f", {fecha.year}" if con_anio else "")
    return f"{fecha.day} de {_MESES['es'][fecha.month - 1]}" + (f" de {fecha.year}" if con_anio else "")
