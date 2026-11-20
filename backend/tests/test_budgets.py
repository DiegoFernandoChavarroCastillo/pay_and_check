from datetime import date, timedelta
from decimal import Decimal

from sqlmodel import Session

from app.models.category import Category
from app.models.expense import Expense


def _rango_mes_actual() -> tuple[str, str]:
    hoy = date.today()
    inicio = hoy.replace(day=1)
    fin = hoy + timedelta(days=30)
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


# --- "¿Me alcanza?" -------------------------------------------------------------------------------------

def test_simular_una_compra_no_guarda_nada(client, auth_headers, categorias, presupuesto, gastar, fijar_hoy):
    from datetime import date

    hoy = date(2026, 3, 30)
    fijar_hoy(hoy)
    presupuesto(date(2026, 3, 16), date(2026, 4, 12), monto="280000.00")  # quedan 14 días
    gastar(40000, hoy)

    r = client.post("/budgets/active/simulate", json={"monto": "100000"}, headers=auth_headers)
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["alcanza"] is True
    assert data["disponible_por_dia_antes"] == "17142.86"
    assert data["disponible_por_dia_despues"] == "10000.00"
    assert data["meta"] is None
    assert len(client.get("/expenses", headers=auth_headers).json()) == 1


def test_simular_dice_a_cuantos_dias_de_la_meta_equivale(client, auth_headers, categorias, presupuesto, fijar_hoy):
    from datetime import date

    hoy = date(2026, 3, 30)
    fijar_hoy(hoy)
    presupuesto(date(2026, 3, 16), date(2026, 4, 12), monto="280000.00")
    r = client.post(
        "/goals",
        json={"nombre": "Viaje", "monto_objetivo": "100000.00", "fecha_limite": "2026-04-09"},
        headers=auth_headers,
    )
    assert r.status_code == 201, r.text

    data = client.post("/budgets/active/simulate", json={"monto": "30000"}, headers=auth_headers).json()
    # 100.000 en 10 días: 10.000 por día; 30.000 equivalen a 3 días de ahorro.
    assert data["meta"] == {"nombre": "Viaje", "dias_equivalentes": 3, "aporte_por_dia": "10000"}


def test_simular_una_compra_que_no_cabe(client, auth_headers, categorias, presupuesto, fijar_hoy):
    from datetime import date

    fijar_hoy(date(2026, 3, 30))
    presupuesto(date(2026, 3, 16), date(2026, 4, 12), monto="100000.00")
    data = client.post("/budgets/active/simulate", json={"monto": "150000"}, headers=auth_headers).json()
    assert data["alcanza"] is False
    assert data["disponible_total_despues"] == "-50000.00"


def test_simular_sin_presupuesto_da_404(client, auth_headers):
    assert client.post("/budgets/active/simulate", json={"monto": "1000"}, headers=auth_headers).status_code == 404
