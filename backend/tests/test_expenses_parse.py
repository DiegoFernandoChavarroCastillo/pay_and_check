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


def test_parse_error_de_red_da_503_no_500(client, auth_headers, db_engine, monkeypatch):
    with Session(db_engine) as session:
        seed_default_categories(session)

    def _raise(*_a, **_kw):
        raise GroqServiceError("timeout")

    monkeypatch.setattr(expenses_router, "parse_expense_text", _raise)

    r = client.post("/expenses/parse", json={"texto": "algo"}, headers=auth_headers)
    assert r.status_code == 503
    assert "formulario manual" in r.json()["detail"]


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


def test_parse_reconoce_un_ingreso_y_no_exige_categoria(client, auth_headers, db_engine, monkeypatch):
    monkeypatch.setattr(
        expenses_router,
        "parse_expense_text",
        lambda texto, categorias, hoy: {
            "tipo": "ingreso", "monto": Decimal("200000"), "categoria": None, "descripcion": "pago de mis papás",
            "fecha": date.today(),
        },
    )  # fmt: skip

    r = client.post("/expenses/parse", json={"texto": "recibí un pago de 200,000 por mis papás"}, headers=auth_headers)
    assert r.status_code == 200
    assert (r.json()["tipo"], r.json()["categoria"], r.json()["monto"]) == ("ingreso", None, "200000")

    # Guardar directo como gasto un texto que es un ingreso no tiene sentido: se rechaza.
    r = client.post("/expenses/from-text", json={"texto": "recibí un pago de 200,000"}, headers=auth_headers)
    assert r.status_code == 422



# --- Varios movimientos en una frase (auditoría: el uber de 12.500 se perdía) -----------------------------

def _dos_movimientos(hoy):
    import json

    return json.dumps({"movimientos": [
        {"tipo": "gasto", "monto": 18000, "categoria": "comida", "descripcion": "almuerzo", "fecha": hoy.isoformat()},
        {"tipo": "gasto", "monto": 12500, "categoria": "transporte", "descripcion": "uber", "fecha": hoy.isoformat()},
    ]})


def test_parse_devuelve_todos_los_movimientos_de_la_frase(monkeypatch):
    from app.services import groq_client

    hoy = date(2026, 11, 18)
    monkeypatch.setattr(groq_client, "_chat", lambda *_a, **_kw: _dos_movimientos(hoy))
    data = groq_client.parse_expense_text("almuerzo 18 mil y un uber de 12.500", ["comida", "transporte"], hoy)

    assert data["monto"] == Decimal("18000")
    assert [(a["monto"], a["categoria"]) for a in data["adicionales"]] == [(Decimal("12500"), "transporte")]


def test_un_movimiento_adicional_invalido_no_tumba_el_primero(monkeypatch):
    import json

    from app.services import groq_client

    hoy = date(2026, 11, 18)
    raw = json.dumps({"movimientos": [
        {"tipo": "gasto", "monto": 18000, "categoria": "comida", "descripcion": "almuerzo", "fecha": hoy.isoformat()},
        {"tipo": "gasto", "monto": -1, "categoria": "inventada", "descripcion": "x", "fecha": hoy.isoformat()},
    ]})
    monkeypatch.setattr(groq_client, "_chat", lambda *_a, **_kw: raw)
    data = groq_client.parse_expense_text("almuerzo 18 mil y algo raro", ["comida"], hoy)
    assert data["monto"] == Decimal("18000")
    assert "adicionales" not in data


def test_el_objeto_suelto_sigue_valiendo(monkeypatch):
    import json

    from app.services import groq_client

    hoy = date(2026, 11, 18)
    raw = json.dumps({"tipo": "gasto", "monto": 5000, "categoria": "comida", "descripcion": "helado",
                      "fecha": hoy.isoformat()})
    monkeypatch.setattr(groq_client, "_chat", lambda *_a, **_kw: raw)
    assert groq_client.parse_expense_text("helado 5000", ["comida"], hoy)["monto"] == Decimal("5000")


def test_parse_y_from_text_con_dos_movimientos(client, auth_headers, db_engine, monkeypatch):
    from app.services import groq_client

    with Session(db_engine) as session:
        seed_default_categories(session)
    _crear_presupuesto_del_mes(client, auth_headers)
    monkeypatch.setattr(groq_client, "_chat", lambda *_a, **_kw: _dos_movimientos(date.today()))

    r = client.post("/expenses/parse", json={"texto": "almuerzo 18 mil y un uber de 12.500"}, headers=auth_headers)
    assert r.status_code == 200, r.text
    assert r.json()["adicionales"][0]["descripcion"] == "uber"
    assert client.get("/expenses", headers=auth_headers).json() == []

    r = client.post("/expenses/from-text", json={"texto": "almuerzo 18 mil y un uber de 12.500"}, headers=auth_headers)
    assert r.status_code == 201, r.text
    assert sorted(g["descripcion"] for g in client.get("/expenses", headers=auth_headers).json()) == [
        "almuerzo", "uber",
    ]
