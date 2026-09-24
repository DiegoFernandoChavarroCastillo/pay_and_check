from datetime import UTC, datetime


def utcnow() -> datetime:
    """`default_factory` compartido para columnas `created_at` — evita repetir
    la misma lambda en cada modelo nuevo."""
    return datetime.now(UTC)
