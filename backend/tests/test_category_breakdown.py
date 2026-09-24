from datetime import date

from sqlmodel import Session

from app.db.seed import seed_default_categories


def test_desglose_por_categoria_marca_excedido(client, auth_headers, db_engine):
    with Session(db_engine) as session:
        seed_default_categories(session)

    hoy = date.today()
    inicio = hoy.replace(day=1).isoformat()
    fin = date(hoy.year, hoy.month, 28).isoformat()
    client.post(
        "/budgets", json={"monto_total": "300000.00", "fecha_inicio": inicio, "fecha_fin": fin},
        headers=auth_headers,
    )

    r = client.post(
        "/categories", json={"nombre": "salidas", "tipo": "opcional", "limite": "30000.00"},
        headers=auth_headers,
    )
    cat_id = r.json()["id"]

    client.post(
        "/expenses",
        json={"monto": "40000.00", "category_id": cat_id, "descripcion": "salida", "fecha": hoy.isoformat()},
        headers=auth_headers,
    )

    r = client.get("/budgets/active/summary", headers=auth_headers)
    desglose = {c["categoria"]: c for c in r.json()["desglose_por_categoria"]}
    assert desglose["salidas"]["gastado"] == "40000.00"
    assert desglose["salidas"]["excedido"] is True


def test_desglose_categoria_sin_limite_nunca_excedido(client, auth_headers, db_engine):
    with Session(db_engine) as session:
        seed_default_categories(session)

    hoy = date.today()
    inicio = hoy.replace(day=1).isoformat()
    fin = date(hoy.year, hoy.month, 28).isoformat()
    client.post(
        "/budgets", json={"monto_total": "300000.00", "fecha_inicio": inicio, "fecha_fin": fin},
        headers=auth_headers,
    )
    client.post(
        "/expenses",
        json={"monto": "999999.00", "category_id": 1, "descripcion": "mucha comida", "fecha": hoy.isoformat()},
        headers=auth_headers,
    )

    r = client.get("/budgets/active/summary", headers=auth_headers)
    comida = next(c for c in r.json()["desglose_por_categoria"] if c["categoria"] == "comida")
    assert comida["limite"] is None
    assert comida["excedido"] is False
