from collections.abc import Generator

from sqlmodel import Session, create_engine

from app.core.config import settings

# pool_pre_ping: comprueba cada conexión antes de usarla y la reemplaza si
# está muerta. Un Postgres gestionado (Neon) cierra las conexiones inactivas y
# suspende la base tras unos minutos sin uso; sin esto, la siguiente petición
# reutilizaba esa conexión cerrada y fallaba con un 500.
engine = create_engine(settings.DATABASE_URL, pool_pre_ping=True, pool_recycle=300)


def get_session() -> Generator[Session, None, None]:
    """Dependencia de FastAPI: entrega una sesión de DB por request."""
    with Session(engine) as session:
        yield session
