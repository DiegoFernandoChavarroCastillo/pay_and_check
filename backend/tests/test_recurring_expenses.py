from datetime import date
from decimal import Decimal

from app.models.recurring_expense import RecurringExpense
from app.services.recurring_expenses import proximo_vencimiento, vencimiento_vigente


def _fijo(**campos) -> RecurringExpense:
    base = {
        "user_id": 1,
        "category_id": 1,
        "monto": Decimal("1000"),
        "descripcion": "x",
        "fecha_inicio": date(2026, 1, 1),
    }
    return RecurringExpense(**{**base, **campos})


def test_vencimientos_semanales():
    lunes = _fijo(frecuencia="semanal", dia_semana=0)
    # 2026-03-11 es miércoles: el lunes de esa semana ya venció; el siguiente es el 16.
    assert vencimiento_vigente(lunes, date(2026, 3, 11)) == date(2026, 3, 9)
    assert proximo_vencimiento(lunes, date(2026, 3, 11)) == date(2026, 3, 16)
    # El mismo día cuenta como vencido y como próximo.
    assert (
        vencimiento_vigente(lunes, date(2026, 3, 9)) == proximo_vencimiento(lunes, date(2026, 3, 9)) == date(2026, 3, 9)
    )


def test_vencimientos_mensuales_y_meses_cortos():
    arriendo = _fijo(frecuencia="mensual", dia_mes=5)
    assert vencimiento_vigente(arriendo, date(2026, 3, 4)) == date(2026, 2, 5)
    assert vencimiento_vigente(arriendo, date(2026, 3, 5)) == date(2026, 3, 5)
    assert proximo_vencimiento(arriendo, date(2026, 3, 6)) == date(2026, 4, 5)
    assert proximo_vencimiento(arriendo, date(2026, 12, 20)) == date(2027, 1, 5)

    # El 31 en un mes de 28 o 30 días vence el último día de ese mes.
    fin_de_mes = _fijo(frecuencia="mensual", dia_mes=31)
    assert vencimiento_vigente(fin_de_mes, date(2026, 2, 28)) == date(2026, 2, 28)
    assert proximo_vencimiento(fin_de_mes, date(2026, 4, 1)) == date(2026, 4, 30)


def test_no_debe_vencimientos_anteriores_a_cuando_se_creo():
    nuevo = _fijo(frecuencia="mensual", dia_mes=5, fecha_inicio=date(2026, 3, 10))
    assert vencimiento_vigente(nuevo, date(2026, 3, 20)) is None
    assert proximo_vencimiento(nuevo, date(2026, 3, 20)) == date(2026, 4, 5)


def test_un_gasto_fijo_mensual_queda_por_pagar_y_se_descuenta_al_confirmarlo(
    client, auth_headers, categorias, presupuesto, fijar_hoy
):
    presupuesto(date(2026, 3, 1), date(2026, 5, 31), monto="900000.00")
    fijar_hoy(date(2026, 3, 2))
    r = client.post(
        "/recurring-expenses",
        json={
            "category_id": 5,
            "monto": "150000",
            "descripcion": "Recibo de la luz",
            "frecuencia": "mensual",
            "dia_mes": 5,
        },
        headers=auth_headers,
    )
    assert r.status_code == 201, r.text
    fijo = r.json()
    assert (fijo["frecuencia"], fijo["proximo_vencimiento"], fijo["pendiente_desde"]) == ("mensual", "2026-03-05", None)

    def disponible():
        return Decimal(client.get("/budgets/active/summary", headers=auth_headers).json()["disponible_total"])

    def pendientes():
        return client.get("/recurring-expenses/pending", headers=auth_headers).json()

    # Antes del día 5 no hay nada por pagar.
    assert pendientes() == []

    # Llega el 5: queda por pagar, pero todavía no descuenta.
    fijar_hoy(date(2026, 3, 5))
    assert [(p["descripcion"], p["monto"], p["fecha"]) for p in pendientes()] == [
        ("Recibo de la luz", "150000.00", "2026-03-05"),
    ]
    assert disponible() == Decimal("900000.00")

    # Sigue pendiente si pasan los días sin confirmarlo.
    fijar_hoy(date(2026, 3, 8))
    assert len(pendientes()) == 1

    # "Ya lo pagué": se registra el gasto y se descuenta.
    r = client.post(f"/recurring-expenses/{fijo['id']}/pay", headers=auth_headers)
    assert r.status_code == 201 and (r.json()["source"], r.json()["fecha"]) == ("recurrente", "2026-03-05")
    assert disponible() == Decimal("750000.00")
    assert pendientes() == []
    # Confirmarlo dos veces no lo cobra dos veces.
    assert client.post(f"/recurring-expenses/{fijo['id']}/pay", headers=auth_headers).status_code == 400
    assert disponible() == Decimal("750000.00")

    # Ya pagado, lo próximo es el mes que viene (aunque se consulte el mismo día del vencimiento).
    assert client.get("/recurring-expenses", headers=auth_headers).json()[0]["proximo_vencimiento"] == "2026-04-05"

    # El mes siguiente vuelve a quedar por pagar.
    fijar_hoy(date(2026, 4, 5))
    assert [p["fecha"] for p in pendientes()] == ["2026-04-05"]


def test_omitir_un_vencimiento_no_registra_gasto_y_vuelve_a_avisar_el_siguiente(
    client, auth_headers, categorias, presupuesto, fijar_hoy
):
    presupuesto(date(2026, 3, 1), date(2026, 5, 31))
    fijar_hoy(date(2026, 3, 9))  # lunes
    fijo = client.post(
        "/recurring-expenses",
        json={"category_id": 2, "monto": "25000", "descripcion": "Recarga", "dia_semana": 0},
        headers=auth_headers,
    ).json()
    assert fijo["pendiente_desde"] == "2026-03-09"

    assert client.post(f"/recurring-expenses/{fijo['id']}/skip", headers=auth_headers).status_code == 204
    # Omitido el de hoy (lunes 9), el próximo es el lunes siguiente.
    assert client.get("/recurring-expenses", headers=auth_headers).json()[0]["proximo_vencimiento"] == "2026-03-16"
    assert client.get("/recurring-expenses/pending", headers=auth_headers).json() == []
    assert client.get("/expenses", headers=auth_headers).json() == []

    fijar_hoy(date(2026, 3, 16))
    assert [p["fecha"] for p in client.get("/recurring-expenses/pending", headers=auth_headers).json()] == [
        "2026-03-16"
    ]


def test_un_gasto_fijo_pausado_no_queda_por_pagar_y_las_frecuencias_exigen_su_dia(
    client, auth_headers, categorias, presupuesto, fijar_hoy
):
    presupuesto(date(2026, 3, 1), date(2026, 5, 31))
    fijar_hoy(date(2026, 3, 9))
    fijo = client.post(
        "/recurring-expenses",
        json={"category_id": 2, "monto": "25000", "descripcion": "Recarga", "dia_semana": 0},
        headers=auth_headers,
    ).json()
    client.patch(f"/recurring-expenses/{fijo['id']}", json={"activo": False}, headers=auth_headers)
    assert client.get("/recurring-expenses/pending", headers=auth_headers).json() == []

    for cuerpo in (
        {"category_id": 2, "monto": "1000", "descripcion": "x", "frecuencia": "mensual"},
        {"category_id": 2, "monto": "1000", "descripcion": "x", "frecuencia": "semanal"},
        {"category_id": 2, "monto": "1000", "descripcion": "x", "frecuencia": "mensual", "dia_mes": 32},
    ):
        assert client.post("/recurring-expenses", json=cuerpo, headers=auth_headers).status_code == 422


def test_crud_recurring_expenses_via_api(client, auth_headers):
    r = client.post("/categories", json={"nombre": "transporte propio"}, headers=auth_headers)
    cat_id = r.json()["id"]

    r = client.post(
        "/recurring-expenses",
        json={"category_id": cat_id, "monto": "15000.00", "descripcion": "bus", "dia_semana": 0},
        headers=auth_headers,
    )
    assert r.status_code == 201
    recurring_id = r.json()["id"]
    assert r.json()["activo"] is True

    r = client.get("/recurring-expenses", headers=auth_headers)
    assert len(r.json()) == 1

    r = client.patch(f"/recurring-expenses/{recurring_id}", json={"activo": False}, headers=auth_headers)
    assert r.status_code == 200
    assert r.json()["activo"] is False

    r = client.delete(f"/recurring-expenses/{recurring_id}", headers=auth_headers)
    assert r.status_code == 204


def test_recurring_expenses_requiere_autenticacion(client):
    assert client.get("/recurring-expenses").status_code == 401


def test_recurring_expenses_categoria_ajena_da_404(client, make_user):
    headers_a, _ = make_user("a@test.com")
    headers_b, _ = make_user("b@test.com")

    r = client.post("/categories", json={"nombre": "privada de a"}, headers=headers_a)
    cat_id = r.json()["id"]

    r = client.post(
        "/recurring-expenses",
        json={"category_id": cat_id, "monto": "1000", "descripcion": "x", "dia_semana": 0},
        headers=headers_b,
    )
    assert r.status_code == 404
