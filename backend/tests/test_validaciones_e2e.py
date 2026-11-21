"""Hallazgos de la prueba de punta a punta en el teléfono (20 nov 2026): validaciones que faltaban en la API."""

from datetime import date

import pytest

from app.core.rate_limit import MAX_FALLOS_CANJE
from app.services.patterns import detect_patterns
from tests.conftest import ACEPTA_POLITICA

HOY = date(2026, 3, 20)
INICIO, FIN = date(2026, 3, 1), date(2026, 3, 31)


@pytest.fixture()
def con_presupuesto(categorias, presupuesto, fijar_hoy):
    fijar_hoy(HOY)
    presupuesto(INICIO, FIN, monto="1000000.00")


def _gasto(client, headers, monto, fecha=HOY, descripcion="gasto"):
    return client.post(
        "/expenses",
        json={"monto": str(monto), "category_id": 1, "descripcion": descripcion, "fecha": fecha.isoformat()},
        headers=headers,
    )


def _ingreso(client, headers, monto, fecha=HOY):
    return client.post(
        "/incomes", json={"monto": str(monto), "descripcion": "mesada", "fecha": fecha.isoformat()}, headers=headers
    )


# --- Montos -------------------------------------------------------------------------------------------------


@pytest.mark.parametrize("monto", ["-5000", "0", "99999999999999"])
def test_gastos_e_ingresos_con_monto_invalido_se_rechazan_sin_500(client, auth_headers, con_presupuesto, monto):
    # Un gasto negativo bajaba lo gastado y subía el disponible; uno enorme reventaba la columna con un 500.
    assert _gasto(client, auth_headers, monto).status_code == 422
    assert _ingreso(client, auth_headers, monto).status_code == 422


def test_editar_un_gasto_a_negativo_tambien_se_rechaza(client, auth_headers, con_presupuesto):
    gasto = _gasto(client, auth_headers, 1000).json()
    r = client.patch(f"/expenses/{gasto['id']}", json={"monto": "-1"}, headers=auth_headers)
    assert r.status_code == 422


def test_la_descripcion_tiene_un_largo_maximo(client, auth_headers, con_presupuesto):
    assert _gasto(client, auth_headers, 1000, descripcion="a" * 5000).status_code == 422
    assert _gasto(client, auth_headers, 1000, descripcion="  almuerzo  ").json()["descripcion"] == "almuerzo"


# --- Fechas futuras -----------------------------------------------------------------------------------------


def test_un_ingreso_o_gasto_con_fecha_futura_no_cuenta_desde_hoy(client, auth_headers, con_presupuesto):
    manana = date(2026, 3, 21)
    assert _ingreso(client, auth_headers, 200000, manana).status_code == 422
    assert _gasto(client, auth_headers, 1000, manana).status_code == 422
    assert _ingreso(client, auth_headers, 200000, HOY).status_code == 201

    gasto = _gasto(client, auth_headers, 1000).json()
    r = client.patch(f"/expenses/{gasto['id']}", json={"fecha": manana.isoformat()}, headers=auth_headers)
    assert r.status_code == 422


# --- Presupuestos que se solapan ----------------------------------------------------------------------------


def _presupuesto(client, headers, inicio, fin):
    return client.post(
        "/budgets",
        json={"monto_total": "1000", "fecha_inicio": inicio.isoformat(), "fecha_fin": fin.isoformat()},
        headers=headers,
    )


def test_no_se_puede_crear_un_presupuesto_que_se_cruce_con_otro(client, auth_headers, con_presupuesto):
    r = _presupuesto(client, auth_headers, date(2026, 3, 25), date(2026, 4, 30))
    assert r.status_code == 409
    assert "1 de marzo de 2026" in r.json()["detail"]
    # El último día es inclusivo: empezar el mismo día en que termina el otro también se cruza.
    assert _presupuesto(client, auth_headers, FIN, date(2026, 4, 30)).status_code == 409
    assert _presupuesto(client, auth_headers, date(2026, 4, 1), date(2026, 4, 30)).status_code == 201


def test_editar_un_presupuesto_para_cruzarlo_con_otro_tambien_se_rechaza(client, auth_headers, con_presupuesto):
    abril = _presupuesto(client, auth_headers, date(2026, 4, 1), date(2026, 4, 30)).json()
    r = client.patch(f"/budgets/{abril['id']}", json={"fecha_inicio": "2026-03-15"}, headers=auth_headers)
    assert r.status_code == 409
    # Editar el propio presupuesto sin cruzarse con otro sigue funcionando.
    r = client.patch(f"/budgets/{abril['id']}", json={"fecha_fin": "2026-05-15"}, headers=auth_headers)
    assert r.status_code == 200


# --- Contraseñas --------------------------------------------------------------------------------------------


@pytest.mark.parametrize("clave", ["1234567", "12345678", "password", "aaaaaaaaaa", "abababab"])
def test_el_registro_rechaza_contrasenas_cortas_o_obvias(client, clave):
    r = client.post(
        "/auth/register",
        json={"email": "nueva@test.com", "password": clave, "nombre": "Nueva", **ACEPTA_POLITICA},
    )
    assert r.status_code == 422


# --- Metas y puntos -----------------------------------------------------------------------------------------


def _puntos(client, headers):
    return client.get("/gamification/profile", headers=headers).json()["puntos"]


def test_devolver_el_aporte_quita_los_puntos_de_la_meta(client, auth_headers, con_presupuesto):
    """Antes: meta de $1.000, aportar, cobrar los puntos de "meta cumplida", devolver el dinero, repetir."""
    base = _puntos(client, auth_headers)
    for i in range(3):
        meta = client.post("/goals", json={"nombre": f"meta {i}", "monto_objetivo": "1000"}, headers=auth_headers)
        meta = meta.json()
        cumplida = client.post(
            f"/goals/{meta['id']}/contributions", json={"monto": "1000"}, headers=auth_headers
        ).json()
        assert cumplida["estado"] == "cumplida"
        assert _puntos(client, auth_headers) > base
        aporte = cumplida["aportes"][0]["id"]
        client.delete(f"/goals/{meta['id']}/contributions/{aporte}", headers=auth_headers)
        assert _puntos(client, auth_headers) == base


def test_borrar_una_meta_cumplida_quita_sus_puntos(client, auth_headers, con_presupuesto):
    base = _puntos(client, auth_headers)
    meta = client.post("/goals", json={"nombre": "viaje", "monto_objetivo": "1000"}, headers=auth_headers).json()
    client.post(f"/goals/{meta['id']}/contributions", json={"monto": "1000"}, headers=auth_headers)
    assert _puntos(client, auth_headers) > base
    client.delete(f"/goals/{meta['id']}", headers=auth_headers)
    assert _puntos(client, auth_headers) == base


def test_no_se_puede_apartar_mas_de_lo_que_le_falta_a_la_meta(client, auth_headers, con_presupuesto):
    meta = client.post("/goals", json={"nombre": "viaje", "monto_objetivo": "500000"}, headers=auth_headers).json()
    r = client.post(f"/goals/{meta['id']}/contributions", json={"monto": "600000"}, headers=auth_headers)
    assert r.status_code == 400
    assert r.json()["detail"] == "A esta meta solo le faltan $500.000."

    r = client.post(f"/goals/{meta['id']}/contributions", json={"monto": "5000000"}, headers=auth_headers)
    assert r.json()["detail"] == "Solo tienes $1.000.000 disponible para apartar."  # con formato, sin decimales


# --- Canje de códigos ---------------------------------------------------------------------------------------


def test_el_canje_de_codigos_tiene_limite_de_intentos(client, auth_headers):
    for i in range(MAX_FALLOS_CANJE):
        r = client.post("/me/subscription/redeem", json={"codigo": f"ECI-20{i:02d}"}, headers=auth_headers)
        assert r.status_code == 404
    r = client.post("/me/subscription/redeem", json={"codigo": "ECI-2099"}, headers=auth_headers)
    assert r.status_code == 429
    assert "Retry-After" in r.headers


# --- Consejo de límite por categoría ------------------------------------------------------------------------


def test_sin_dos_semanas_de_historia_no_se_propone_un_limite_por_categoria(
    client, auth_headers, con_presupuesto, db_engine
):
    from sqlmodel import Session, select

    from app.models.user import User

    _gasto(client, auth_headers, 20000)  # comida
    client.post(
        "/expenses",
        json={"monto": "5000", "category_id": 2, "descripcion": "bus", "fecha": HOY.isoformat()},
        headers=auth_headers,
    )
    with Session(db_engine) as session:
        user = session.exec(select(User)).one()
        dominante = next(p for p in detect_patterns(session, user, HOY) if p.tipo == "categoria_dominante")
    # Con un día de datos el "90 % de lo gastado" quedaba por debajo de lo ya gastado: se propone un reto.
    assert dominante.accion["tipo"] != "poner_limite"
