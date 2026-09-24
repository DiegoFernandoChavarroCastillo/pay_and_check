from datetime import date
from decimal import Decimal

from sqlmodel import Session

from app.models.category import Category
from app.models.expense import Expense


def _rango_mes_actual() -> tuple[str, str]:
    hoy = date.today()
    inicio = hoy.replace(day=1)
    fin = date(hoy.year, hoy.month, 28)
    return inicio.isoformat(), fin.isoformat()


def test_crear_presupuesto_y_validar_fechas(client, auth_headers):
    inicio, fin = _rango_mes_actual()
    r = client.post(
        "/budgets", json={"monto_total": "300000.00", "fecha_inicio": inicio, "fecha_fin": fin},
        headers=auth_headers,
    )
    assert r.status_code == 201

    # fecha_fin <= fecha_inicio -> rechazado
    r = client.post(
        "/budgets", json={"monto_total": "1000", "fecha_inicio": "2026-01-10", "fecha_fin": "2026-01-01"},
        headers=auth_headers,
    )
    assert r.status_code == 422


def test_get_active_budget_sin_presupuesto_da_404(client, auth_headers):
    r = client.get("/budgets/active", headers=auth_headers)
    assert r.status_code == 404


def test_summary_refleja_gastos_insertados_directo_en_la_db(client, auth_headers, db_engine):
    inicio, fin = _rango_mes_actual()
    r = client.post(
        "/budgets", json={"monto_total": "300000.00", "fecha_inicio": inicio, "fecha_fin": fin},
        headers=auth_headers,
    )
    budget_id = r.json()["id"]
    user_id = client.get("/auth/me", headers=auth_headers).json()["id"]

    with Session(db_engine) as session:
        cat = Category(nombre="comida", owner_id=None)
        session.add(cat)
        session.commit()
        session.refresh(cat)
        session.add(Expense(
            user_id=user_id, budget_id=budget_id, category_id=cat.id,
            monto=Decimal("15000.00"), descripcion="almuerzo", fecha=date.today(),
        ))
        session.add(Expense(
            user_id=user_id, budget_id=budget_id, category_id=cat.id,
            monto=Decimal("25000.00"), descripcion="mercado", fecha=date.today(),
        ))
        session.commit()

    r = client.get("/budgets/active/summary", headers=auth_headers)
    assert r.status_code == 200
    data = r.json()
    assert Decimal(data["gastado_total"]) == Decimal("40000.00")
    assert Decimal(data["disponible_total"]) == Decimal("260000.00")


def test_patch_actualiza_y_summary_lo_refleja_al_instante(client, auth_headers):
    inicio, fin = _rango_mes_actual()
    r = client.post(
        "/budgets", json={"monto_total": "300000.00", "fecha_inicio": inicio, "fecha_fin": fin},
        headers=auth_headers,
    )
    budget_id = r.json()["id"]

    r = client.patch(f"/budgets/{budget_id}", json={"monto_total": "500000.00"}, headers=auth_headers)
    assert r.status_code == 200
    assert r.json()["monto_total"] == "500000.00"

    r = client.get("/budgets/active/summary", headers=auth_headers)
    assert Decimal(r.json()["disponible_total"]) == Decimal("500000.00")


def test_budgets_requiere_autenticacion(client):
    r = client.get("/budgets/active")
    assert r.status_code == 401
