from collections.abc import Generator

from sqlmodel import Session, create_engine

from app.core.config import settings

engine = create_engine(settings.DATABASE_URL)


def get_session() -> Generator[Session, None, None]:
    """Dependencia de FastAPI: entrega una sesión de DB por request."""
    with Session(engine) as session:
        yield session
