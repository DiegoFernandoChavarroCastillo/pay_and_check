from datetime import date, timedelta
from decimal import Decimal

from sqlmodel import Session

import app.routers.reports as reports_router
from app.db.seed import seed_default_categories


def test_weekly_report_agrega_bien_y_pasa_por_la_ia_mockeada(client, auth_headers, db_engine, monkeypatch):
    with Session(db_engine) as session:
        seed_default_categories(session)

    hoy = date.today()
    inicio = hoy.replace(day=1).isoformat()
    fin = (hoy + timedelta(days=30)).isoformat()
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
    fin = (hoy + timedelta(days=30)).isoformat()
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


def test_reporte_semanal_descarta_consejos_de_inversion_y_cifras_inventadas(
    client, auth_headers, categorias, presupuesto, gastar, fijar_hoy, monkeypatch
):
    from app.routers import reports as reports_router

    fijar_hoy(date(2026, 3, 11))
    presupuesto(date(2026, 3, 1), date(2026, 3, 31))
    gastar("20000.00", date(2026, 3, 10), category_id=1)

    for texto in (
        "Vas con margen: asigna el ahorro a una inversión de bajo riesgo.",
        "Vas bien; si reduces 7.500 más, cierras la semana perfecta.",
    ):
        monkeypatch.setattr(reports_router, "generate_weekly_recommendations", lambda _r, t=texto: t)
        data = client.get("/reports/weekly", headers=auth_headers).json()
        assert "invers" not in data["recomendaciones"] and "7.500" not in data["recomendaciones"]
        assert "20.000" in data["recomendaciones"]

