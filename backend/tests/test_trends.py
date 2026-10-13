from datetime import date, timedelta
from decimal import Decimal

# Miércoles. Su semana va del lunes 5 al domingo 11 de octubre de 2026.
HOY = date(2026, 10, 7)
LUNES = date(2026, 10, 5)


def test_trends_agrupa_por_semana_y_rellena_con_cero(
    client, auth_headers, categorias, presupuesto, gastar, fijar_hoy
):
    fijar_hoy(HOY)
    presupuesto(date(2026, 9, 1), date(2026, 10, 31))
    gastar("20000.00", LUNES, category_id=1)
    gastar("5000.00", HOY, category_id=2)
    gastar("10000.00", LUNES - timedelta(days=1), category_id=1)  # domingo: semana anterior
    gastar("8000.00", LUNES - timedelta(weeks=3), category_id=3)

    r = client.get("/reports/trends?semanas=4", headers=auth_headers)
    assert r.status_code == 200
    data = r.json()

    semanas = data["semanas"]
    assert [s["semana_inicio"] for s in semanas] == [
        (LUNES - timedelta(weeks=n)).isoformat() for n in (3, 2, 1, 0)
    ]
    assert [Decimal(s["total"]) for s in semanas] == [
        Decimal("8000.00"), Decimal("0.00"), Decimal("10000.00"), Decimal("25000.00"),
    ]
    assert semanas[-1]["semana_fin"] == "2026-10-11"
    assert semanas[1]["por_categoria"] == []
    # Ordenadas de mayor a menor.
    assert [c["categoria"] for c in semanas[-1]["por_categoria"]] == ["comida", "transporte"]

    assert Decimal(data["promedio_semanal"]) == Decimal("10750.00")
    assert data["variacion_vs_semana_anterior_pct"] == 150

    dias = data["dias"]
    assert len(dias) == 14
    assert dias[0]["fecha"] == (LUNES - timedelta(weeks=1)).isoformat()
    por_fecha = {d["fecha"]: Decimal(d["total"]) for d in dias}
    assert por_fecha["2026-10-04"] == Decimal("10000.00")
    assert por_fecha["2026-10-05"] == Decimal("20000.00")
    assert por_fecha["2026-10-06"] == Decimal("0.00")


def test_trends_no_se_corta_entre_presupuestos(client, auth_headers, categorias, presupuesto, gastar, fijar_hoy):
    fijar_hoy(HOY)
    presupuesto(date(2026, 9, 1), date(2026, 9, 30))
    presupuesto(date(2026, 10, 1), date(2026, 10, 31))
    gastar("7000.00", date(2026, 9, 30))
    gastar("3000.00", date(2026, 10, 1))

    data = client.get("/reports/trends?semanas=2", headers=auth_headers).json()
    # 30 de septiembre y 1 de octubre caen en la misma semana, en presupuestos distintos.
    assert Decimal(data["semanas"][0]["total"]) == Decimal("10000.00")


def test_trends_sin_gastos(client, auth_headers):
    data = client.get("/reports/trends", headers=auth_headers).json()
    assert len(data["semanas"]) == 8
    assert all(Decimal(s["total"]) == 0 for s in data["semanas"])
    assert data["variacion_vs_semana_anterior_pct"] is None
    assert Decimal(data["promedio_semanal"]) == 0


def test_trends_no_mezcla_usuarios(client, make_user, categorias, presupuesto, gastar, fijar_hoy):
    fijar_hoy(HOY)
    presupuesto(date(2026, 10, 1), date(2026, 10, 31))
    gastar("9000.00", HOY)

    otro, _ = make_user(email="otro@test.com")
    data = client.get("/reports/trends", headers=otro).json()
    assert all(Decimal(s["total"]) == 0 for s in data["semanas"])


def test_trends_valida_el_numero_de_semanas(client, auth_headers):
    assert client.get("/reports/trends?semanas=1", headers=auth_headers).status_code == 422
    assert client.get("/reports/trends?semanas=27", headers=auth_headers).status_code == 422
