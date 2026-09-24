from datetime import date
from decimal import Decimal


def _crear_presupuesto_del_mes(client, headers):
    hoy = date.today()
    inicio = hoy.replace(day=1).isoformat()
    fin = date(hoy.year, hoy.month, 28).isoformat()
    client.post(
        "/budgets", json={"monto_total": "300000.00", "fecha_inicio": inicio, "fecha_fin": fin},
        headers=headers,
    )


def test_ingreso_sube_disponible_sin_tocar_monto_total(client, auth_headers):
    _crear_presupuesto_del_mes(client, auth_headers)
    hoy = date.today().isoformat()

    r = client.post(
        "/incomes", json={"monto": "50000.00", "descripcion": "regalo", "fecha": hoy},
        headers=auth_headers,
    )
    assert r.status_code == 201

    r = client.get("/budgets/active/summary", headers=auth_headers)
    data = r.json()
    assert data["budget"]["monto_total"] == "300000.00"
    assert data["ingresos_total"] == "50000.00"
    assert Decimal(data["disponible_total"]) == Decimal("350000.00")


def test_ingreso_fuera_de_presupuesto_da_400(client, auth_headers):
    _crear_presupuesto_del_mes(client, auth_headers)
    r = client.post(
        "/incomes", json={"monto": "1000", "descripcion": "x", "fecha": "2020-01-01"},
        headers=auth_headers,
    )
    assert r.status_code == 400


def test_editar_y_borrar_ingreso(client, auth_headers):
    _crear_presupuesto_del_mes(client, auth_headers)
    hoy = date.today().isoformat()
    r = client.post(
        "/incomes", json={"monto": "50000.00", "descripcion": "regalo", "fecha": hoy},
        headers=auth_headers,
    )
    income_id = r.json()["id"]

    r = client.patch(f"/incomes/{income_id}", json={"monto": "70000.00"}, headers=auth_headers)
    assert r.status_code == 200
    r = client.get("/budgets/active/summary", headers=auth_headers)
    assert r.json()["ingresos_total"] == "70000.00"

    r = client.delete(f"/incomes/{income_id}", headers=auth_headers)
    assert r.status_code == 204
    r = client.get("/budgets/active/summary", headers=auth_headers)
    assert r.json()["ingresos_total"] == "0.00"


def test_incomes_requiere_autenticacion(client):
    assert client.get("/incomes").status_code == 401
