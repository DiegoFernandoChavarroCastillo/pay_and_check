from datetime import date
from decimal import Decimal

from sqlmodel import Session

import app.routers.reports as reports_router
from app.db.seed import seed_default_categories


def test_weekly_report_agrega_bien_y_pasa_por_la_ia_mockeada(client, auth_headers, db_engine, monkeypatch):
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
        "/expenses", json={"monto": "20000.00", "category_id": 1, "descripcion": "mercado", "fecha": hoy.isoformat()},
        headers=auth_headers,
    )
    client.post(
        "/expenses", json={"monto": "5000.00", "category_id": 2, "descripcion": "bus", "fecha": hoy.isoformat()},
        headers=auth_headers,
    )

    llamadas = {}

    def _fake_recomendaciones(resumen_texto: str) -> str:
        llamadas["resumen"] = resumen_texto
        return "Recomendación de prueba mencionando comida."

    monkeypatch.setattr(reports_router, "generate_weekly_recommendations", _fake_recomendaciones)

    r = client.get("/reports/weekly", headers=auth_headers)
    assert r.status_code == 200
    data = r.json()

    assert Decimal(data["gasto_total_semana"]) == Decimal("25000.00")
    categorias = {c["categoria"]: Decimal(c["monto"]) for c in data["gasto_por_categoria"]}
    assert categorias["comida"] == Decimal("20000.00")
    assert categorias["transporte"] == Decimal("5000.00")
    assert "comida" in data["recomendaciones"]

    # El prompt recibió el resumen agregado, no transacciones individuales
    # (no debe mencionar "mercado" ni "bus", solo totales por categoría).
    assert "mercado" not in llamadas["resumen"]
    assert "comida" in llamadas["resumen"]


def test_weekly_report_sin_presupuesto_activo_da_404(client, auth_headers):
    r = client.get("/reports/weekly", headers=auth_headers)
    assert r.status_code == 404


def test_weekly_report_si_falla_groq_no_tumba_el_resumen_numerico(client, auth_headers, db_engine, monkeypatch):
    with Session(db_engine) as session:
        seed_default_categories(session)

    hoy = date.today()
    inicio = hoy.replace(day=1).isoformat()
    fin = date(hoy.year, hoy.month, 28).isoformat()
    client.post(
        "/budgets", json={"monto_total": "300000.00", "fecha_inicio": inicio, "fecha_fin": fin},
        headers=auth_headers,
    )

    from app.services.groq_client import GroqServiceError

    def _raise(_resumen: str) -> str:
        raise GroqServiceError("Groq no responde")

    monkeypatch.setattr(reports_router, "generate_weekly_recommendations", _raise)

    r = client.get("/reports/weekly", headers=auth_headers)
    assert r.status_code == 200
    assert r.json()["gasto_total_semana"] == "0.00"
    assert "no se pudieron generar" in r.json()["recomendaciones"].lower()
