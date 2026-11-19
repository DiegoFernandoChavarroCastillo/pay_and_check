"""Funciones añadidas tras el análisis de competidores: apoyos de la universidad, gastos previstos, vacas,
gastos hormiga y suscripciones, simulador de crédito y progreso familiar."""

from datetime import date, timedelta
from decimal import Decimal

from sqlmodel import Session, select

from app.models.coach import EmotionalCheckin
from app.models.plan import LicenseCode, Organization
from app.models.support import SupportResource
from app.models.user import User
from app.services import credito, hormiga

HOY = date(2026, 3, 30)  # lunes
INICIO, FIN = date(2026, 3, 16), date(2026, 4, 12)  # 28 días; con HOY quedan 14


def _con_presupuesto(presupuesto, fijar_hoy, monto="280000.00"):
    fijar_hoy(HOY)
    presupuesto(INICIO, FIN, monto=monto)


def _universidad(db_engine) -> int:
    with Session(db_engine) as session:
        org = Organization(nombre="ECI")
        session.add(org)
        session.flush()
        session.add(LicenseCode(codigo="ECI-TEST", tipo="convenio", organization_id=org.id))
        session.add(SupportResource(organization_id=org.id, tipo="alimentacion", titulo="Auxilio de alimentación",
                                    descripcion="Almuerzo subsidiado", contacto="Bienestar"))
        session.commit()
        return org.id


# --- Apoyos de la universidad -----------------------------------------------------------------------------

def test_sin_convenio_no_hay_apoyos(client, auth_headers):
    r = client.get("/support", headers=auth_headers).json()
    assert r == {"organizacion": None, "motivo_sugerencia": None, "apoyos": []}


def test_con_convenio_ve_los_apoyos_y_se_sugieren_con_estres(client, auth_headers, db_engine, fijar_hoy):
    fijar_hoy(HOY)
    _universidad(db_engine)
    assert client.post("/me/subscription/redeem", json={"codigo": "ECI-TEST"}, headers=auth_headers).status_code == 200

    r = client.get("/support", headers=auth_headers).json()
    assert r["organizacion"] == "ECI" and r["motivo_sugerencia"] is None
    apoyo = r["apoyos"][0]
    assert apoyo["titulo"] == "Auxilio de alimentación" and apoyo["me_interesa"] is False

    with Session(db_engine) as session:
        user_id = session.exec(select(User.id)).first()
        for d in range(3):
            session.add(EmotionalCheckin(user_id=user_id, fecha=HOY - timedelta(days=d), animo="ansioso"))
        session.commit()
    assert client.get("/support", headers=auth_headers).json()["motivo_sugerencia"] == "estres"

    for _ in range(2):  # idempotente
        assert client.post(f"/support/{apoyo['id']}/interest", headers=auth_headers).status_code == 204
    assert client.get("/support", headers=auth_headers).json()["apoyos"][0]["me_interesa"] is True


def test_no_se_marca_interes_en_apoyos_de_otra_universidad(client, auth_headers, db_engine):
    _universidad(db_engine)
    with Session(db_engine) as session:
        recurso_id = session.exec(select(SupportResource.id)).first()
    assert client.post(f"/support/{recurso_id}/interest", headers=auth_headers).status_code == 404


# --- Gastos previstos --------------------------------------------------------------------------------------

def test_gasto_previsto_dice_cuanto_apartar_y_llega_al_coach(
    client, auth_headers, categorias, presupuesto, fijar_hoy, monkeypatch
):
    _con_presupuesto(presupuesto, fijar_hoy)
    r = client.post(
        "/planned-expenses",
        json={"descripcion": "Matrícula", "monto": "700000", "fecha": (HOY + timedelta(days=35)).isoformat()},
        headers=auth_headers,
    )
    assert r.status_code == 201, r.text
    lista = client.get("/planned-expenses", headers=auth_headers).json()
    assert lista[0]["dias"] == 35 and lista[0]["por_semana"] == "140000"
    # 280.000 en 14 días son 140.000 por semana: apartar 140.000 deja el margen en cero.
    assert Decimal(lista[0]["margen_semanal"]) == Decimal("0.00")

    import app.services.coach as coach_service

    monkeypatch.setattr(coach_service, "_redactar_insights", lambda user, patrones: [p.descripcion for p in patrones])
    tipos = [i["tipo"] for i in client.get("/coach/insights", headers=auth_headers).json()]
    assert "gasto_previsto" in tipos

    assert client.post(f"/planned-expenses/{lista[0]['id']}/done", headers=auth_headers).status_code == 204
    assert client.get("/planned-expenses", headers=auth_headers).json() == []


def test_un_gasto_previsto_no_puede_estar_en_el_pasado(client, auth_headers, fijar_hoy):
    fijar_hoy(HOY)
    r = client.post("/planned-expenses", json={"descripcion": "x", "monto": "1000", "fecha": "2026-01-01"},
                    headers=auth_headers)
    assert r.status_code == 422


# --- Vacas -------------------------------------------------------------------------------------------------

def test_una_vaca_registra_mi_parte_y_deja_el_resto_por_cobrar(
    client, auth_headers, categorias, presupuesto, fijar_hoy
):
    _con_presupuesto(presupuesto, fijar_hoy)
    r = client.post(
        "/expenses/split",
        json={"monto_total": "100000", "category_id": 1, "descripcion": "Pizza", "fecha": HOY.isoformat(),
              "personas": ["Juan", "Laura"]},
        headers=auth_headers,
    )
    assert r.status_code == 201, r.text
    data = r.json()
    # 100.000 / 3 = 33.333 para cada uno; el peso que sobra va en la parte propia.
    assert data["mi_parte"] == "33334"
    assert [c["monto"] for c in data["por_cobrar"]] == ["33333.00", "33333.00"]
    assert client.get("/budgets/active/summary", headers=auth_headers).json()["gastado_total"] == "33334.00"

    resumen = client.get("/receivables", headers=auth_headers).json()
    assert resumen["total_pendiente"] == "66666.00"
    cobro = resumen["pendientes"][0]["id"]
    assert client.post(f"/receivables/{cobro}/paid", headers=auth_headers).json()["pagado"] is True
    assert client.get("/receivables", headers=auth_headers).json()["total_pendiente"] == "33333.00"

    # Borrar el gasto se lleva sus cobros.
    assert client.delete(f"/expenses/{data['expense_id']}", headers=auth_headers).status_code == 204
    assert client.get("/receivables", headers=auth_headers).json()["pendientes"] == []


# --- Gastos hormiga y suscripciones ----------------------------------------------------------------------------

def test_detecta_hormiga_y_suscripciones(client, auth_headers, categorias, presupuesto, fijar_hoy, gastar):
    fijar_hoy(HOY)
    presupuesto(date(2026, 1, 1), date(2026, 4, 30), monto="5000000.00")
    for d in range(6):
        gastar(3500, HOY - timedelta(days=d * 2), descripcion="Tinto y pandebono")
    for fecha in (date(2026, 1, 8), date(2026, 2, 8), date(2026, 3, 8)):
        gastar(10900, fecha, category_id=3, descripcion="Spotify")
    gastar(250000, HOY, descripcion="Mercado")
    for fecha in (date(2026, 1, 5), date(2026, 2, 5), date(2026, 3, 5)):
        gastar(45000, fecha, category_id=5, descripcion="Plan del celular")  # servicios: básico, no recortable

    r = {x["nombre"]: x for x in client.get("/reports/repeated", headers=auth_headers).json()}
    assert r["Tinto y pandebono"]["tipo"] == "hormiga" and r["Tinto y pandebono"]["veces"] == 6
    assert r["Spotify"]["tipo"] == "suscripcion" and r["Spotify"]["por_mes"] == "10900"
    assert r["Spotify"]["por_semestre"] == "49050"
    assert "Mercado" not in r
    assert "Plan del celular" not in r


def test_la_clave_junta_variaciones_del_mismo_concepto():
    assert hormiga.clave_de("Domicilio de Rappi") == hormiga.clave_de("domicilio rappi 32000")


# --- Crédito -----------------------------------------------------------------------------------------------

def test_cuota_fija_de_un_credito():
    c = credito.simular(Decimal("1000000"), 12, Decimal("26.82"))
    # 26,82 % E.A. equivale a 2 % mensual: la cuota de un millón a 12 meses es 94.558 (cuota francesa).
    assert c.tasa_mensual == Decimal("2.00")
    assert Decimal("94000") < c.cuota < Decimal("95000")
    assert c.total_pagado == c.cuota * 12 and c.intereses == c.total_pagado - Decimal("1000000")


def test_credito_sin_intereses_reparte_el_monto():
    c = credito.simular(Decimal("600000"), 6, Decimal("0"))
    assert c.cuota == Decimal("100000") and c.intereses == 0


def test_endpoint_de_credito_muestra_el_impacto_en_el_dia(client, auth_headers, categorias, presupuesto, fijar_hoy):
    _con_presupuesto(presupuesto, fijar_hoy)
    r = client.post("/budgets/simulate-credit", json={"monto": "600000", "cuotas": 6, "tasa_ea": "0"},
                    headers=auth_headers)
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["cuota"] == "100000" and data["por_dia"] == "3333"
    assert data["disponible_por_dia"] == "20000.00" and data["disponible_por_dia_con_cuota"] == "16667.00"


# --- Familia -----------------------------------------------------------------------------------------------

def _familia(client, make_user):
    titular, _ = make_user("papa@t.com")
    codigo = client.put("/me/subscription", json={"plan": "familiar"}, headers=titular).json()["familia"]["codigo"]
    hijo, _ = make_user("hijo@t.com", nombre="Camilo Gómez")
    assert client.post("/me/subscription/redeem", json={"codigo": codigo}, headers=hijo).status_code == 200
    return titular, hijo


def test_el_titular_solo_ve_el_progreso_de_quien_lo_comparte(client, make_user):
    titular, hijo = _familia(client, make_user)
    progreso = client.get("/me/family/progress", headers=titular).json()
    assert progreso == [{"nombre": "Camilo", "comparte": False, "racha": None, "constancia": None,
                         "metas_activas": None, "progreso_metas": None, "presupuesto_alcanza": None}]

    assert client.put("/me/subscription/share-progress", json={"comparte": True}, headers=hijo).status_code == 204
    progreso = client.get("/me/family/progress", headers=titular).json()[0]
    assert progreso["comparte"] is True and progreso["metas_activas"] == 0 and progreso["racha"] == 0
    # Quien no es titular no ve el progreso de nadie.
    assert client.get("/me/family/progress", headers=hijo).status_code == 403


def test_compartir_progreso_es_del_plan_familiar(client, auth_headers):
    r = client.put("/me/subscription/share-progress", json={"comparte": True}, headers=auth_headers)
    assert r.status_code == 409


# --- Panel ---------------------------------------------------------------------------------------------------

def test_borrar_la_cuenta_borra_lo_nuevo(client, auth_headers, categorias, presupuesto, fijar_hoy):
    _con_presupuesto(presupuesto, fijar_hoy)
    client.post("/expenses/split", json={"monto_total": "30000", "category_id": 1, "descripcion": "x",
                                         "fecha": HOY.isoformat(), "personas": ["A"]}, headers=auth_headers)
    client.post("/planned-expenses", json={"descripcion": "y", "monto": "1000",
                                           "fecha": (HOY + timedelta(days=3)).isoformat()}, headers=auth_headers)
    assert client.delete("/auth/me", headers=auth_headers).status_code == 204
