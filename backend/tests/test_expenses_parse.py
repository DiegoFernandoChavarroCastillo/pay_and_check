from datetime import date, timedelta
from decimal import Decimal

from sqlmodel import Session

import app.routers.expenses as expenses_router
from app.db.seed import seed_default_categories
from app.services.groq_client import ExpenseParseError, GroqServiceError


def _crear_presupuesto_del_mes(client, headers):
    hoy = date.today()
    inicio = hoy.replace(day=1).isoformat()
    fin = (hoy + timedelta(days=30)).isoformat()
    client.post(
        "/budgets", json={"monto_total": "300000.00", "fecha_inicio": inicio, "fecha_fin": fin},
        headers=headers,
    )


def test_parse_devuelve_json_estructurado_sin_guardar(client, auth_headers, db_engine, monkeypatch):
    with Session(db_engine) as session:
        seed_default_categories(session)

    monkeypatch.setattr(
        expenses_router,
        "parse_expense_text",
        lambda texto, categorias, hoy: {
            "monto": Decimal("5000"), "categoria": "comida", "descripcion": "helado", "fecha": date.today(),
        },
    )

    r = client.post("/expenses/parse", json={"texto": "me compré un helado de $5000"}, headers=auth_headers)
    assert r.status_code == 200
    assert r.json()["monto"] == "5000"
    assert r.json()["categoria"] == "comida"

    # No se guardó ningún gasto
    assert client.get("/expenses", headers=auth_headers).json() == []


def test_parse_sin_monto_claro_da_422_no_500(client, auth_headers, db_engine, monkeypatch):
    with Session(db_engine) as session:
        seed_default_categories(session)

    def _raise(*_a, **_kw):
        raise ExpenseParseError("No se pudo identificar un monto en el texto.")

    monkeypatch.setattr(expenses_router, "parse_expense_text", _raise)

    r = client.post("/expenses/parse", json={"texto": "hoy me sentí feliz"}, headers=auth_headers)
    assert r.status_code == 422


def test_parse_error_de_red_da_502_no_500(client, auth_headers, db_engine, monkeypatch):
    with Session(db_engine) as session:
        seed_default_categories(session)

    def _raise(*_a, **_kw):
        raise GroqServiceError("timeout")

    monkeypatch.setattr(expenses_router, "parse_expense_text", _raise)

    r = client.post("/expenses/parse", json={"texto": "algo"}, headers=auth_headers)
    assert r.status_code == 502


def test_from_text_guarda_el_gasto_y_actualiza_el_summary(client, auth_headers, db_engine, monkeypatch):
    with Session(db_engine) as session:
        seed_default_categories(session)
    _crear_presupuesto_del_mes(client, auth_headers)

    monkeypatch.setattr(
        expenses_router,
        "parse_expense_text",
        lambda texto, categorias, hoy: {
            "monto": Decimal("12000"), "categoria": "transporte", "descripcion": "bus", "fecha": date.today(),
        },
    )

    r = client.post("/expenses/from-text", json={"texto": "pagué 12000 de bus"}, headers=auth_headers)
    assert r.status_code == 201
    assert r.json()["texto_original"] == "pagué 12000 de bus"

    r = client.get("/budgets/active/summary", headers=auth_headers)
    assert r.json()["gastado_total"] == "12000.00"
