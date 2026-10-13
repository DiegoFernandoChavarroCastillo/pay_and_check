"""Ajustes del backend para la app móvil (Fase 0 de plan-app-movil.md):
refresh token, perfil, borrado de cuenta, "hoy" por zona horaria y origen del gasto."""

from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from sqlmodel import Session, select

import app.core.time as time_module
import app.routers.expenses as expenses_router
from app.db.seed import seed_default_categories
from app.models.budget import Budget
from app.models.category import Category
from app.models.expense import Expense
from app.models.user import User


def _crear_presupuesto(client, headers, inicio: date, fin: date):
    r = client.post(
        "/budgets",
        json={"monto_total": "300000.00", "fecha_inicio": inicio.isoformat(), "fecha_fin": fin.isoformat()},
        headers=headers,
    )
    assert r.status_code == 201, r.text


def test_refresh_devuelve_un_par_nuevo_usable(client, make_user):
    _, login = make_user()
    refresh_token = login.json()["refresh_token"]

    r = client.post("/auth/refresh", json={"refresh_token": refresh_token})
    assert r.status_code == 200
    assert "refresh_token" in r.json()

    me = client.get("/auth/me", headers={"Authorization": f"Bearer {r.json()['access_token']}"})
    assert me.status_code == 200


def test_los_tipos_de_token_no_son_intercambiables(client, make_user):
    _, login = make_user()
    tokens = login.json()

    # Un refresh token no sirve para autenticarse...
    r = client.get("/auth/me", headers={"Authorization": f"Bearer {tokens['refresh_token']}"})
    assert r.status_code == 401

    # ...ni un access token para renovar.
    r = client.post("/auth/refresh", json={"refresh_token": tokens["access_token"]})
    assert r.status_code == 401

    r = client.post("/auth/refresh", json={"refresh_token": "garbage"})
    assert r.status_code == 401


def test_perfil_tiene_defaults_y_se_puede_editar(client, auth_headers):
    me = client.get("/auth/me", headers=auth_headers).json()
    assert (me["coach_tone"], me["idioma"], me["zona_horaria"]) == ("motivador", "es", "America/Bogota")

    r = client.patch(
        "/auth/me",
        json={"coach_tone": "directo", "idioma": "en", "zona_horaria": "Europe/Madrid"},
        headers=auth_headers,
    )
    assert r.status_code == 200
    assert (r.json()["coach_tone"], r.json()["idioma"], r.json()["zona_horaria"]) == (
        "directo", "en", "Europe/Madrid",
    )
    assert r.json()["nombre"] == "Test User"  # lo no enviado no cambia


def test_perfil_rechaza_valores_invalidos(client, auth_headers):
    r = client.patch("/auth/me", json={"coach_tone": "regañon"}, headers=auth_headers)
    assert r.status_code == 422

    r = client.patch("/auth/me", json={"zona_horaria": "Marte/Olympus"}, headers=auth_headers)
    assert r.status_code == 422


def test_borrar_cuenta_elimina_solo_los_datos_del_usuario(client, make_user, db_engine):
    with Session(db_engine) as session:
        seed_default_categories(session)

    headers_a, _ = make_user(email="a@test.com")
    headers_b, _ = make_user(email="b@test.com")
    hoy = date.today()

    for headers in (headers_a, headers_b):
        _crear_presupuesto(client, headers, hoy, hoy + timedelta(days=30))
        client.post("/categories", json={"nombre": "propia"}, headers=headers)
        r = client.post(
            "/expenses",
            json={"monto": "5000", "category_id": 1, "descripcion": "x", "fecha": hoy.isoformat()},
            headers=headers,
        )
        assert r.status_code == 201, r.text

    assert client.delete("/auth/me", headers=headers_a).status_code == 204
    assert client.get("/auth/me", headers=headers_a).status_code == 401

    with Session(db_engine) as session:
        assert len(session.exec(select(User)).all()) == 1
        assert len(session.exec(select(Budget)).all()) == 1
        assert len(session.exec(select(Expense)).all()) == 1
        # Quedan las 6 por defecto + la propia del usuario B.
        assert len(session.exec(select(Category)).all()) == 7

    assert len(client.get("/expenses", headers=headers_b).json()) == 1


def test_el_presupuesto_activo_usa_el_hoy_de_la_zona_horaria_del_usuario(client, auth_headers, monkeypatch):
    # 2026-03-11 01:00 UTC: en Bogotá (UTC-5) todavía es 10 de marzo.
    instante = datetime(2026, 3, 11, 1, 0, tzinfo=ZoneInfo("UTC"))
    monkeypatch.setattr(time_module, "_now", lambda zona: instante.astimezone(ZoneInfo(zona)))

    _crear_presupuesto(client, auth_headers, date(2026, 3, 1), date(2026, 3, 10))

    assert client.get("/budgets/active", headers=auth_headers).status_code == 200

    client.patch("/auth/me", json={"zona_horaria": "UTC"}, headers=auth_headers)
    assert client.get("/budgets/active", headers=auth_headers).status_code == 404


def test_source_y_comercio_del_gasto(client, auth_headers, db_engine, monkeypatch):
    with Session(db_engine) as session:
        seed_default_categories(session)
    hoy = date.today()
    _crear_presupuesto(client, auth_headers, hoy, hoy + timedelta(days=30))
    base = {"monto": "5000", "category_id": 1, "descripcion": "almuerzo", "fecha": hoy.isoformat()}

    r = client.post("/expenses", json=base, headers=auth_headers)
    assert (r.json()["source"], r.json()["comercio"]) == ("manual", None)

    r = client.post(
        "/expenses",
        json={**base, "source": "ocr", "comercio": "Éxito", "texto_original": "EXITO TOTAL 5.000"},
        headers=auth_headers,
    )
    assert r.status_code == 201
    assert (r.json()["source"], r.json()["comercio"]) == ("ocr", "Éxito")
    assert r.json()["texto_original"] == "EXITO TOTAL 5.000"

    # "recurrente" lo asigna solo el servidor.
    r = client.post("/expenses", json={**base, "source": "recurrente"}, headers=auth_headers)
    assert r.status_code == 422

    monkeypatch.setattr(
        expenses_router,
        "parse_expense_text",
        lambda texto, categorias, hoy: {
            "monto": 7000, "categoria": "comida", "descripcion": "helado", "fecha": date.today(),
        },
    )
    r = client.post("/expenses/from-text", json={"texto": "helado de 7000"}, headers=auth_headers)
    assert r.json()["source"] == "texto"


def test_gasto_generado_por_recurrencia_queda_marcado(client, auth_headers, db_engine):
    with Session(db_engine) as session:
        seed_default_categories(session)
    hoy = date.today()
    _crear_presupuesto(client, auth_headers, hoy - timedelta(days=10), hoy + timedelta(days=30))

    r = client.post(
        "/recurring-expenses",
        json={
            "monto": "12000", "category_id": 2, "descripcion": "transporte",
            "dia_semana": hoy.weekday(), "fecha_inicio": hoy.isoformat(),
        },
        headers=auth_headers,
    )
    assert r.status_code == 201, r.text

    gastos = client.get("/expenses", headers=auth_headers).json()
    assert [g["source"] for g in gastos] == ["recurrente"]


def test_google_sin_client_id_configurado_rechaza_cualquier_token(client, monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "GOOGLE_CLIENT_ID", "")
    r = client.post("/auth/google", json={"id_token": "cualquier-token"})
    assert r.status_code == 401
    assert "no está configurado" in r.json()["detail"]
