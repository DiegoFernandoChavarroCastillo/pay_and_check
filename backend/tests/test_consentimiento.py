"""PS-48 y PS-49: la política de privacidad se acepta para tener cuenta, el permiso de SMS va aparte, y borrar
la cuenta no deja ninguna fila de la persona en ninguna tabla."""

import json
from datetime import timedelta
from types import SimpleNamespace

import pytest
from sqlalchemy import func, select
from sqlmodel import Session, SQLModel

import app.routers.auth as auth_router
import app.services.groq_client as groq_client
from app.core.config import POLITICA_VERSION
from tests.conftest import ACEPTA_POLITICA

DATOS = {"email": "ana@test.com", "password": "secret123", "nombre": "Ana"}


def _token(client, datos=DATOS):
    return {"Authorization": f"Bearer {client.post('/auth/login', json=datos).json()['access_token']}"}


@pytest.mark.parametrize(
    "extra",
    [
        {},
        {"acepta_politica": False, "politica_version": POLITICA_VERSION},
        {"acepta_politica": True},
        {"acepta_politica": True, "politica_version": "2020-01"},
    ],
)
def test_sin_aceptar_la_politica_vigente_no_hay_cuenta(client, extra):
    r = client.post("/auth/register", json={**DATOS, **extra})

    assert r.status_code == 422
    assert client.post("/auth/login", json=DATOS).status_code == 401


def test_el_registro_guarda_version_y_fecha_de_la_aceptacion(client):
    r = client.post("/auth/register", json={**DATOS, **ACEPTA_POLITICA})

    assert r.status_code == 201
    cuenta = r.json()
    assert cuenta["politica_version"] == POLITICA_VERSION
    assert cuenta["politica_aceptada_at"] is not None
    assert cuenta["politica_vigente"] is True
    assert cuenta["sms_consent_at"] is None


def test_la_cuenta_de_google_entra_sin_politica_y_la_acepta_despues(client, monkeypatch):
    monkeypatch.setattr(
        auth_router,
        "verify_google_token",
        lambda _token: {"google_id": "g-1", "email": "beto@test.com", "nombre": "Beto"},
    )
    token = client.post("/auth/google", json={"id_token": "x"}).json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    assert client.get("/auth/me", headers=headers).json()["politica_vigente"] is False

    assert client.put("/auth/me/consent", json={"politica_version": "vieja"}, headers=headers).status_code == 422
    r = client.put("/auth/me/consent", json={"politica_version": POLITICA_VERSION}, headers=headers)
    assert r.status_code == 200
    assert r.json()["politica_vigente"] is True


def test_una_politica_nueva_vuelve_a_pedirse(client, monkeypatch):
    client.post("/auth/register", json={**DATOS, **ACEPTA_POLITICA})
    headers = _token(client)
    monkeypatch.setattr("app.schemas.user.POLITICA_VERSION", "2027-01")

    assert client.get("/auth/me", headers=headers).json()["politica_vigente"] is False


def test_el_permiso_de_sms_se_da_y_se_revoca(client, auth_headers):
    r = client.put("/auth/me/consent/sms", json={"acepta": True}, headers=auth_headers)
    assert r.json()["sms_consent_at"] is not None

    r = client.put("/auth/me/consent/sms", json={"acepta": False}, headers=auth_headers)
    assert r.json()["sms_consent_at"] is None


def test_el_consentimiento_requiere_sesion(client):
    assert client.put("/auth/me/consent", json={"politica_version": POLITICA_VERSION}).status_code == 401
    assert client.put("/auth/me/consent/sms", json={"acepta": True}).status_code == 401


# --- PS-49 -----------------------------------------------------------------------------------------------------


def _columnas_de_usuario():
    """Toda columna de cualquier tabla que apunta a users.id, más la llave de la propia tabla users."""
    for tabla in SQLModel.metadata.sorted_tables:
        if tabla.name == "users":
            yield tabla, tabla.c.id
        for columna in tabla.columns:
            if any(fk.column.table.name == "users" for fk in columna.foreign_keys):
                yield tabla, columna


def _filas_de(db_engine, user_id):
    with Session(db_engine) as session:
        return {
            f"{tabla.name}.{columna.name}": n
            for tabla, columna in _columnas_de_usuario()
            if (n := session.exec(select(func.count()).select_from(tabla).where(columna == user_id)).one()[0])
        }


def test_borrar_la_cuenta_no_deja_filas_en_ninguna_tabla(
    client, auth_headers, db_engine, categorias, presupuesto, gastar, fijar_hoy, monkeypatch
):
    """Recorre el metadata: una tabla nueva con llave a users que `delete_me` olvide hace fallar esta prueba."""
    from datetime import date

    hoy = date(2026, 3, 30)
    fijar_hoy(hoy)
    contenido = json.dumps({"en_alcance": True, "respuesta": "Vas bien."})
    eleccion = SimpleNamespace(message=SimpleNamespace(content=contenido))
    falso = SimpleNamespace(
        chat=SimpleNamespace(completions=SimpleNamespace(create=lambda **_k: SimpleNamespace(choices=[eleccion])))
    )
    monkeypatch.setattr(groq_client, "_get_client", lambda: falso)

    presupuesto(hoy - timedelta(days=5), hoy + timedelta(days=20))
    gastar(1000, hoy)
    otra_persona = client.post(
        "/auth/register", json={**ACEPTA_POLITICA, "email": "b@test.com", "password": "secret123", "nombre": "B"}
    )
    assert otra_persona.status_code == 201

    llamadas = [
        ("post", "/incomes", {"monto": "5000", "descripcion": "regalo", "fecha": hoy.isoformat()}),
        ("post", "/recurring-expenses", {"category_id": 1, "monto": "2000", "descripcion": "bus", "dia_semana": 0}),
        ("post", "/categories", {"nombre": "propia", "limite": "1000"}),
        ("post", "/checkins", {"animo": "neutral"}),
        ("post", "/challenges", {"plantilla": "checkins"}),
        ("post", "/coach/chat", {"mensaje": "¿cómo voy?"}),
        ("put", "/me/subscription", {"plan": "premium"}),
        ("put", "/auth/me/consent/sms", {"acepta": True}),
    ]
    for metodo, ruta, cuerpo in llamadas:
        r = getattr(client, metodo)(ruta, json=cuerpo, headers=auth_headers)
        assert r.status_code < 300, (ruta, r.text)
    meta = client.post("/goals", json={"nombre": "Viaje", "monto_objetivo": "5000"}, headers=auth_headers).json()
    client.post(f"/goals/{meta['id']}/contributions", json={"monto": "1000"}, headers=auth_headers)

    user_id = client.get("/auth/me", headers=auth_headers).json()["id"]
    otro_id = otra_persona.json()["id"]
    antes = _filas_de(db_engine, user_id)
    assert len(antes) >= 10, antes  # la prueba sí sembró datos en muchas tablas

    assert client.delete("/auth/me", headers=auth_headers).status_code == 204

    assert _filas_de(db_engine, user_id) == {}
    assert _filas_de(db_engine, otro_id) == {"users.id": 1}
    assert client.post("/auth/login", json={"email": "user@test.com", "password": "secret123"}).status_code == 401
