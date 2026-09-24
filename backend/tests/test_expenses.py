from datetime import date

from sqlmodel import Session

from app.db.seed import seed_default_categories


def _crear_presupuesto_del_mes(client, headers):
    hoy = date.today()
    inicio = hoy.replace(day=1).isoformat()
    fin = date(hoy.year, hoy.month, 28).isoformat()
    r = client.post(
        "/budgets", json={"monto_total": "300000.00", "fecha_inicio": inicio, "fecha_fin": fin},
        headers=headers,
    )
    return r.json()["id"]


def test_crear_listar_editar_borrar_gasto_y_summary_se_actualiza(client, auth_headers, db_engine):
    with Session(db_engine) as session:
        seed_default_categories(session)
    _crear_presupuesto_del_mes(client, auth_headers)
    hoy = date.today().isoformat()

    # crear
    r = client.post(
        "/expenses", json={"monto": "10000.00", "category_id": 1, "descripcion": "almuerzo", "fecha": hoy},
        headers=auth_headers,
    )
    assert r.status_code == 201
    expense_id = r.json()["id"]

    r = client.get("/budgets/active/summary", headers=auth_headers)
    assert r.json()["gastado_total"] == "10000.00"

    # listar
    r = client.get("/expenses", headers=auth_headers)
    assert len(r.json()) == 1

    # filtrar por categoría que no tiene gastos
    r = client.get("/expenses?category_id=2", headers=auth_headers)
    assert r.json() == []

    # editar
    r = client.patch(f"/expenses/{expense_id}", json={"monto": "15000.00"}, headers=auth_headers)
    assert r.status_code == 200
    r = client.get("/budgets/active/summary", headers=auth_headers)
    assert r.json()["gastado_total"] == "15000.00"

    # borrar
    r = client.delete(f"/expenses/{expense_id}", headers=auth_headers)
    assert r.status_code == 204
    r = client.get("/budgets/active/summary", headers=auth_headers)
    assert r.json()["gastado_total"] == "0.00"


def test_fecha_fuera_de_cualquier_presupuesto_da_error_claro(client, auth_headers, db_engine):
    with Session(db_engine) as session:
        seed_default_categories(session)
    _crear_presupuesto_del_mes(client, auth_headers)

    r = client.post(
        "/expenses", json={"monto": "5000", "category_id": 1, "descripcion": "x", "fecha": "2020-01-01"},
        headers=auth_headers,
    )
    assert r.status_code == 400


def test_categoria_inexistente_da_404(client, auth_headers, db_engine):
    with Session(db_engine) as session:
        seed_default_categories(session)
    _crear_presupuesto_del_mes(client, auth_headers)

    r = client.post(
        "/expenses",
        json={"monto": "5000", "category_id": 9999, "descripcion": "x", "fecha": date.today().isoformat()},
        headers=auth_headers,
    )
    assert r.status_code == 404


def test_usuario_no_puede_tocar_gasto_de_otro(client, make_user, db_engine):
    with Session(db_engine) as session:
        seed_default_categories(session)

    headers_a, _ = make_user("a@test.com")
    headers_b, _ = make_user("b@test.com")
    _crear_presupuesto_del_mes(client, headers_a)

    r = client.post(
        "/expenses",
        json={"monto": "5000", "category_id": 1, "descripcion": "x", "fecha": date.today().isoformat()},
        headers=headers_a,
    )
    expense_id = r.json()["id"]

    assert client.get("/expenses", headers=headers_b).json() == []
    assert client.patch(f"/expenses/{expense_id}", json={"monto": "1"}, headers=headers_b).status_code == 404
    assert client.delete(f"/expenses/{expense_id}", headers=headers_b).status_code == 404
