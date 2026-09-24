import os

# Hermético a propósito (criterio de aceptación de la Fase 9): pytest no debe
# necesitar un .env real, GROQ_API_KEY real, ni conexión a internet.
# setdefault no pisa valores reales si alguien sí los exportó en el entorno.
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("JWT_SECRET", "test-secret-key")
os.environ.setdefault("GROQ_API_KEY", "test-groq-key")
os.environ.setdefault("GOOGLE_CLIENT_ID", "test-google-client-id")

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

from app.db.session import get_session
from app.main import app


@pytest.fixture()
def db_engine():
    # StaticPool: una sola conexión compartida — si no, cada Session ve una
    # SQLite ":memory:" nueva y vacía.
    engine = create_engine(
        "sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    SQLModel.metadata.create_all(engine)
    yield engine
    SQLModel.metadata.drop_all(engine)


@pytest.fixture()
def client(db_engine):
    def override_get_session():
        with Session(db_engine) as session:
            yield session

    app.dependency_overrides[get_session] = override_get_session
    yield TestClient(app)
    app.dependency_overrides.clear()


@pytest.fixture()
def make_user(client):
    """Registra + loguea un usuario y devuelve sus headers de Authorization."""

    def _make_user(email: str = "user@test.com", password: str = "secret123", nombre: str = "Test User"):
        r = client.post("/auth/register", json={"email": email, "password": password, "nombre": nombre})
        assert r.status_code == 201, r.text
        r = client.post("/auth/login", json={"email": email, "password": password})
        assert r.status_code == 200, r.text
        token = r.json()["access_token"]
        return {"Authorization": f"Bearer {token}"}, r

    return _make_user


@pytest.fixture()
def auth_headers(make_user):
    headers, _ = make_user()
    return headers
