"""Fases 5 y 7 de plan-app-movil.md: metas verificadas, puntos, rachas, retos, insignias y wrapped."""

from datetime import date, timedelta
from decimal import Decimal

from sqlmodel import Session

import app.services.gamification as gamification_service
import app.services.wrapped as wrapped_service
from app.models.gamification import PointEvent
from app.services.gamification import nivel_para, racha_actual, rachas
from app.services.groq_client import GroqServiceError

LUNES = date(2026, 3, 9)
ENTRETENIMIENTO = 3


def _perfil(client, headers):
    r = client.get("/gamification/profile", headers=headers)
    assert r.status_code == 200, r.text
    return r.json()


def _summary(client, headers):
    return client.get("/budgets/active/summary", headers=headers).json()


# --- Metas ------------------------------------------------------------------


def test_apartar_a_una_meta_descuenta_del_disponible_y_se_verifica_con_datos(
    client, auth_headers, categorias, presupuesto, gastar, fijar_hoy
):
    fijar_hoy(LUNES)
    presupuesto(LUNES, LUNES + timedelta(days=9), monto="100000.00")
    gastar(20000, LUNES)

    meta = client.post(
        "/goals", json={"nombre": "Viaje", "monto_objetivo": "50000"}, headers=auth_headers
    ).json()
    assert (meta["estado"], Decimal(meta["aportado"])) == ("activa", Decimal("0"))

    r = client.post(f"/goals/{meta['id']}/contributions", json={"monto": "30000"}, headers=auth_headers)
    assert r.status_code == 201
    assert Decimal(r.json()["progreso"]) == Decimal("0.6")

    s = _summary(client, auth_headers)
    assert Decimal(s["apartado_total"]) == Decimal("30000.00")
    assert Decimal(s["disponible_total"]) == Decimal("50000.00")  # 100.000 - 20.000 - 30.000
    assert Decimal(s["disponible_por_dia"]) == Decimal("5000.00")

    # No se puede apartar dinero que no existe: quedan 50.000 disponibles.
    r = client.post(f"/goals/{meta['id']}/contributions", json={"monto": "50001"}, headers=auth_headers)
    assert r.status_code == 400

    r = client.post(f"/goals/{meta['id']}/contributions", json={"monto": "20000"}, headers=auth_headers)
    assert (r.json()["estado"], r.json()["cumplida_en"]) == ("cumplida", "2026-03-09")

    # Devolver un aporte la "des-cumple" y libera el dinero.
    aporte_id = r.json()["aportes"][-1]["id"]
    r = client.delete(f"/goals/{meta['id']}/contributions/{aporte_id}", headers=auth_headers)
    assert r.json()["estado"] == "activa"
    assert Decimal(_summary(client, auth_headers)["disponible_total"]) == Decimal("50000.00")

    assert client.delete(f"/goals/{meta['id']}", headers=auth_headers).status_code == 204
    assert Decimal(_summary(client, auth_headers)["disponible_total"]) == Decimal("80000.00")


def test_metas_estan_aisladas_por_usuario_y_exigen_presupuesto(client, make_user):
    headers_a, _ = make_user(email="a@test.com")
    headers_b, _ = make_user(email="b@test.com")
    meta = client.post("/goals", json={"nombre": "Viaje", "monto_objetivo": "50000"}, headers=headers_a).json()

    assert client.get("/goals", headers=headers_b).json() == []
    r = client.post(f"/goals/{meta['id']}/contributions", json={"monto": "10"}, headers=headers_b)
    assert r.status_code == 404

    r = client.post(f"/goals/{meta['id']}/contributions", json={"monto": "10"}, headers=headers_a)
    assert r.status_code == 400  # sin presupuesto activo no hay de dónde apartar


# --- Puntos, rachas y niveles -----------------------------------------------


def test_rachas_y_niveles():
    dias = {date(2026, 3, d) for d in (1, 2, 3, 6, 7)}
    assert rachas(dias) == [(date(2026, 3, 1), 3), (date(2026, 3, 6), 2)]
    assert racha_actual(dias, date(2026, 3, 7)) == 2
    assert racha_actual(dias, date(2026, 3, 8)) == 2  # ayer cuenta: hoy todavía se puede registrar
    assert racha_actual(dias, date(2026, 3, 9)) == 0

    assert nivel_para(0, "es") == {"numero": 1, "nombre": "Aprendiz", "puntos_nivel": 0, "puntos_siguiente": 100}
    assert nivel_para(100, "en")["nombre"] == "Organized"
    assert nivel_para(99999, "es")["puntos_siguiente"] is None


def test_puntos_por_consistencia_no_por_monto_y_sin_duplicar(
    client, auth_headers, categorias, presupuesto, gastar, fijar_hoy
):
    presupuesto(date(2026, 2, 1), date(2026, 4, 30))
    # Tres días seguidos con registro; el tercer día, dos gastos y uno enorme.
    for dia, monto in ((9, 1000), (10, 1000), (11, 1000), (11, 900000)):
        fijar_hoy(date(2026, 3, dia))
        gastar(monto, date(2026, 3, dia))
    client.post("/checkins", json={"animo": "tranquilo"}, headers=auth_headers)

    perfil = _perfil(client, auth_headers)
    # 3 días x 5 + check-in 5 + racha de 3 días 20 = 40, sin importar los montos.
    assert perfil["puntos"] == 40 and perfil["nuevos_puntos"] == 40
    assert (perfil["racha_actual"], perfil["mejor_racha"]) == (3, 3)
    assert perfil["nuevas_insignias"] == ["Primer paso", "Racha de 3 días", "Me escucho"]
    assert perfil["nivel"]["nombre"] == "Aprendiz"

    otra_vez = _perfil(client, auth_headers)
    assert (otra_vez["puntos"], otra_vez["nuevos_puntos"], otra_vez["nuevas_insignias"]) == (40, 0, [])
    desbloqueadas = {i["codigo"] for i in otra_vez["insignias"] if i["desbloqueada"]}
    assert desbloqueadas == {"primer_registro", "racha_3", "primer_checkin"}


def test_gastos_recurrentes_no_dan_puntos_de_registro(client, auth_headers, categorias, presupuesto, fijar_hoy):
    fijar_hoy(LUNES)
    presupuesto(date(2026, 2, 1), date(2026, 4, 30))
    client.post(
        "/recurring-expenses",
        json={"monto": "12000", "category_id": 2, "descripcion": "bus", "dia_semana": 0,
              "fecha_inicio": "2026-03-09"},
        headers=auth_headers,
    )
    assert len(client.get("/expenses", headers=auth_headers).json()) == 1
    assert _perfil(client, auth_headers)["puntos"] == 0


def test_dos_sincronizaciones_simultaneas_no_rompen_ni_duplican(
    client, auth_headers, categorias, presupuesto, gastar, fijar_hoy, db_engine, monkeypatch
):
    fijar_hoy(LUNES)
    presupuesto(date(2026, 2, 1), date(2026, 4, 30))
    gastar(1000, LUNES)

    # Simula la otra petición: otorga el mismo evento justo después de que esta
    # leyó qué claves existían y antes de que guarde las suyas.
    original = gamification_service.dias_con_checkin

    def _otra_peticion_se_adelanta(session, user_id, today):
        with Session(db_engine) as otra:
            otra.add(PointEvent(user_id=user_id, clave="registro:2026-03-09", tipo="registro", puntos=5, fecha=LUNES))
            otra.commit()
        return original(session, user_id, today)

    monkeypatch.setattr(gamification_service, "dias_con_checkin", _otra_peticion_se_adelanta)
    r = client.get("/challenges", headers=auth_headers)
    assert r.status_code == 200

    monkeypatch.setattr(gamification_service, "dias_con_checkin", original)
    assert _perfil(client, auth_headers)["puntos"] == 5


# --- Retos ------------------------------------------------------------------


def test_reto_de_reducir_categoria_se_verifica_solo_y_no_duplica_puntos(
    client, auth_headers, categorias, presupuesto, gastar, fijar_hoy
):
    presupuesto(date(2026, 2, 1), date(2026, 4, 30))
    fijar_hoy(LUNES)
    gastar(50000, date(2026, 3, 5), ENTRETENIMIENTO, "concierto")  # semana previa: línea base

    r = client.post(
        "/challenges",
        json={"plantilla": "reducir_categoria", "category_id": ENTRETENIMIENTO, "porcentaje": 20},
        headers=auth_headers,
    )
    assert r.status_code == 201, r.text
    reto = r.json()
    assert (Decimal(reto["linea_base"]), Decimal(reto["objetivo"])) == (Decimal("50000.00"), Decimal("40000.00"))
    assert (reto["fecha_inicio"], reto["fecha_fin"], reto["estado"]) == ("2026-03-09", "2026-03-15", "activo")
    assert "40.000" in reto["descripcion"] and "entretenimiento" in reto["descripcion"]

    # No se puede duplicar el mismo reto.
    r = client.post(
        "/challenges", json={"plantilla": "reducir_categoria", "category_id": ENTRETENIMIENTO}, headers=auth_headers
    )
    assert r.status_code == 400

    gastar(30000, date(2026, 3, 10), ENTRETENIMIENTO, "cine")
    fijar_hoy(date(2026, 3, 12))
    en_curso = client.get("/challenges", headers=auth_headers).json()[0]
    assert (en_curso["estado"], Decimal(en_curso["valor_actual"])) == ("activo", Decimal("30000.00"))
    puntos_antes = _perfil(client, auth_headers)["puntos"]

    # Termina la ventana: gastó 30.000 <= 40.000 -> cumplido, sin que el usuario reporte nada.
    fijar_hoy(date(2026, 3, 16))
    perfil = _perfil(client, auth_headers)
    assert perfil["puntos"] - puntos_antes >= 50
    assert "Reto superado" in perfil["nuevas_insignias"]
    assert client.get("/challenges", headers=auth_headers).json()[0]["estado"] == "cumplido"

    repetido = _perfil(client, auth_headers)
    assert (repetido["puntos"], repetido["nuevos_puntos"]) == (perfil["puntos"], 0)


def test_reto_fallido_no_da_puntos_y_sin_linea_base_no_se_crea(
    client, auth_headers, categorias, presupuesto, gastar, fijar_hoy
):
    presupuesto(date(2026, 2, 1), date(2026, 4, 30))
    fijar_hoy(LUNES)

    r = client.post(
        "/challenges", json={"plantilla": "reducir_categoria", "category_id": ENTRETENIMIENTO}, headers=auth_headers
    )
    assert r.status_code == 400  # no hay gasto la semana anterior con qué comparar

    gastar(50000, date(2026, 3, 5), ENTRETENIMIENTO)
    client.post(
        "/challenges", json={"plantilla": "reducir_categoria", "category_id": ENTRETENIMIENTO}, headers=auth_headers
    )
    gastar(45000, date(2026, 3, 11), ENTRETENIMIENTO)

    fijar_hoy(date(2026, 3, 16))
    perfil = _perfil(client, auth_headers)
    assert client.get("/challenges", headers=auth_headers).json()[0]["estado"] == "fallido"
    assert all(e["tipo"] != "reto" for e in perfil["eventos_recientes"])


def test_retos_de_checkins_y_dias_sin_gasto(client, auth_headers, categorias, presupuesto, gastar, fijar_hoy):
    presupuesto(date(2026, 2, 1), date(2026, 4, 30))
    fijar_hoy(LUNES)
    for plantilla in ("checkins", "dias_sin_gasto"):
        assert client.post("/challenges", json={"plantilla": plantilla}, headers=auth_headers).status_code == 201

    # Lunes: gasto opcional (comida). Martes a jueves: solo transporte "fijo" no existe por defecto,
    # así que no se gasta nada esos días.
    gastar(5000, LUNES, 1)
    for dia in range(9, 14):
        fijar_hoy(date(2026, 3, dia))
        client.post("/checkins", json={"animo": "neutral"}, headers=auth_headers)

    retos = {r["tipo"]: r for r in client.get("/challenges", headers=auth_headers).json()}
    assert (retos["checkins"]["estado"], Decimal(retos["checkins"]["valor_actual"])) == ("cumplido", Decimal("5"))
    # Hoy es viernes 13: días cerrados lun-jue, de los cuales 3 (mar, mié, jue) sin gasto opcional.
    assert (retos["dias_sin_gasto"]["estado"], Decimal(retos["dias_sin_gasto"]["valor_actual"])) == (
        "cumplido", Decimal("3"),
    )


def test_sugerencias_de_retos_y_abandonar(client, auth_headers, categorias, presupuesto, gastar, fijar_hoy):
    presupuesto(date(2026, 2, 1), date(2026, 4, 30))
    fijar_hoy(LUNES)

    sugerencias = client.get("/challenges/suggestions", headers=auth_headers).json()
    # Con presupuesto pero sin metas: el reto de aportar a una meta no se ofrece.
    generales = ["dias_sin_gasto", "checkins", "registro_diario", "semana_en_ritmo"]
    assert [s["plantilla"] for s in sugerencias] == generales

    reto = client.post("/challenges", json={"plantilla": "checkins"}, headers=auth_headers).json()
    sugerencias = client.get("/challenges/suggestions", headers=auth_headers).json()
    assert [s["plantilla"] for s in sugerencias] == [p for p in generales if p != "checkins"]

    client.post("/goals", json={"nombre": "Viaje", "monto_objetivo": "50000"}, headers=auth_headers)
    sugerencias = client.get("/challenges/suggestions", headers=auth_headers).json()
    assert sugerencias[-1]["plantilla"] == "aportar_meta"

    assert client.delete(f"/challenges/{reto['id']}", headers=auth_headers).status_code == 204
    assert client.get("/challenges", headers=auth_headers).json() == []


def test_semana_en_ritmo_da_puntos_e_insignia_equilibrio(
    client, auth_headers, categorias, presupuesto, gastar, fijar_hoy
):
    # 70 días y 700.000: ritmo esperado de 70.000 por semana.
    presupuesto(date(2026, 3, 2), date(2026, 5, 10), monto="700000.00")
    fijar_hoy(date(2026, 3, 4))
    gastar(60000, date(2026, 3, 4))

    fijar_hoy(LUNES)  # la semana del 2 al 8 de marzo ya cerró, por debajo del ritmo
    perfil = _perfil(client, auth_headers)
    assert {"tipo": "semana_en_ritmo", "puntos": 30, "fecha": "2026-03-08"} in perfil["eventos_recientes"]
    assert "Equilibrio" in perfil["nuevas_insignias"]


# --- Wrapped ----------------------------------------------------------------


def test_wrapped_mensual_resume_el_mes_con_datos_reales(
    client, auth_headers, categorias, presupuesto, gastar, fijar_hoy, monkeypatch
):
    def _caido(*_args):
        raise GroqServiceError("sin red")

    monkeypatch.setattr(wrapped_service, "generate_coach_text", _caido)

    presupuesto(date(2026, 2, 1), date(2026, 4, 30))
    fijar_hoy(date(2026, 3, 20))
    gastar(20000, date(2026, 2, 5), 1, "mercado feb")
    gastar(40000, date(2026, 2, 25), 1, "mercado fin de feb")
    gastar(30000, date(2026, 3, 3), 1, "mercado")
    gastar(50000, date(2026, 3, 7), ENTRETENIMIENTO, "concierto")
    gastar(10000, date(2026, 3, 7), 2, "taxi")
    client.post("/checkins", json={"animo": "confiado"}, headers=auth_headers)

    w = client.get("/reports/monthly-wrapped?mes=2026-03", headers=auth_headers).json()
    assert Decimal(w["gasto_total"]) == Decimal("90000.00")
    assert (w["num_gastos"], w["dias_con_registro"]) == (3, 2)
    assert (w["categoria_top"]["categoria"], w["categoria_top"]["porcentaje"]) == ("entretenimiento", 55)
    assert w["gasto_mayor"]["descripcion"] == "concierto"
    assert (w["dia_mas_gasto"]["fecha"], Decimal(w["dia_mas_gasto"]["monto"])) == ("2026-03-07", Decimal("60000.00"))
    # Marzo va por el día 20: se compara con febrero hasta el 20 (20.000), no con el mes entero (60.000).
    assert w["variacion_vs_mes_anterior_pct"] == 350
    assert w["animo_frecuente"] == "confiado"
    assert "3 gastos" in w["frase_coach"]  # respaldo determinista: la IA está caída

    # Sin `mes`, usa el mes en curso del usuario.
    assert client.get("/reports/monthly-wrapped", headers=auth_headers).json()["mes"] == 3
    assert client.get("/reports/monthly-wrapped?mes=2026-13", headers=auth_headers).status_code == 422


def test_borrar_cuenta_tambien_borra_coach_metas_y_gamificacion(
    client, auth_headers, categorias, presupuesto, gastar, fijar_hoy
):
    fijar_hoy(LUNES)
    presupuesto(LUNES, LUNES + timedelta(days=30))
    gastar(1000, LUNES)
    client.post("/checkins", json={"animo": "neutral"}, headers=auth_headers)
    meta = client.post("/goals", json={"nombre": "Viaje", "monto_objetivo": "5000"}, headers=auth_headers).json()
    client.post(f"/goals/{meta['id']}/contributions", json={"monto": "1000"}, headers=auth_headers)
    client.post("/challenges", json={"plantilla": "checkins"}, headers=auth_headers)
    _perfil(client, auth_headers)

    assert client.delete("/auth/me", headers=auth_headers).status_code == 204


def test_wrapped_no_compara_con_un_mes_que_se_empezo_a_medias(
    client, auth_headers, categorias, presupuesto, gastar, fijar_hoy, monkeypatch
):
    monkeypatch.setattr(wrapped_service, "generate_coach_text", lambda *_a: "ok")
    presupuesto(date(2026, 2, 1), date(2026, 4, 30))
    fijar_hoy(date(2026, 3, 20))
    # Empezó a registrar el 21 de febrero: ese mes solo tiene una semana de datos.
    gastar(20000, date(2026, 2, 21), 1, "mercado feb")
    gastar(30000, date(2026, 3, 3), 1, "mercado")

    w = client.get("/reports/monthly-wrapped?mes=2026-03", headers=auth_headers).json()
    assert w["variacion_vs_mes_anterior_pct"] is None


def test_retos_de_registro_diario_aporte_a_meta_y_semana_en_ritmo(
    client, auth_headers, categorias, presupuesto, gastar, fijar_hoy
):
    presupuesto(date(2026, 3, 2), date(2026, 3, 29), monto="400000.00")  # 4 semanas: ritmo de 100.000
    fijar_hoy(LUNES)

    def crear(plantilla):
        return client.post("/challenges", json={"plantilla": plantilla}, headers=auth_headers)

    # Sin una meta no hay a qué aportar.
    assert crear("aportar_meta").status_code == 400
    meta = client.post("/goals", json={"nombre": "Viaje", "monto_objetivo": "50000"}, headers=auth_headers).json()
    for plantilla in ("registro_diario", "aportar_meta", "semana_en_ritmo"):
        assert crear(plantilla).status_code == 201, plantilla

    def retos():
        return {r["tipo"]: r for r in client.get("/challenges", headers=auth_headers).json()}

    assert Decimal(retos()["semana_en_ritmo"]["objetivo"]) == Decimal("100000.00")

    # Registra de lunes a jueves: 4 de 5 días, todavía activo.
    for dia in range(9, 13):
        fijar_hoy(date(2026, 3, dia))
        gastar(10000, date(2026, 3, dia))
    assert (retos()["registro_diario"]["estado"], Decimal(retos()["registro_diario"]["valor_actual"])) == (
        "activo", Decimal("4"),
    )
    assert retos()["aportar_meta"]["estado"] == "activo"

    # Viernes: quinto día con registro y un aporte a la meta. Los dos se cumplen en el acto.
    fijar_hoy(date(2026, 3, 13))
    gastar(10000, date(2026, 3, 13))
    client.post(f"/goals/{meta['id']}/contributions", json={"monto": "5000"}, headers=auth_headers)
    estado = retos()
    assert (estado["registro_diario"]["estado"], estado["aportar_meta"]["estado"]) == ("cumplido", "cumplido")
    # El de no pasarse del ritmo no se decide hasta que termina la semana, aunque vaya bien.
    assert (estado["semana_en_ritmo"]["estado"], Decimal(estado["semana_en_ritmo"]["valor_actual"])) == (
        "activo", Decimal("50000.00"),
    )

    fijar_hoy(date(2026, 3, 16))
    assert retos()["semana_en_ritmo"]["estado"] == "cumplido"
    assert _perfil(client, auth_headers)["puntos"] >= 35 + 30 + 50


def test_semana_en_ritmo_no_se_cumple_si_se_pasa_del_ritmo(
    client, auth_headers, categorias, presupuesto, gastar, fijar_hoy
):
    presupuesto(date(2026, 3, 2), date(2026, 3, 29), monto="400000.00")
    fijar_hoy(LUNES)
    client.post("/challenges", json={"plantilla": "semana_en_ritmo"}, headers=auth_headers)
    gastar(120000, LUNES)

    fijar_hoy(date(2026, 3, 16))
    reto = client.get("/challenges", headers=auth_headers).json()[0]
    assert reto["estado"] == "fallido"


def test_insignias_por_usar_la_app_de_verdad(client, auth_headers, categorias, presupuesto, gastar, fijar_hoy):
    def obtenidas():
        return {i["codigo"] for i in _perfil(client, auth_headers)["insignias"] if i["desbloqueada"]}

    presupuesto(date(2026, 3, 2), date(2026, 3, 15), monto="400000.00")
    fijar_hoy(LUNES)
    gastar(10000, LUNES, source="voz")
    assert {"primer_registro", "voz"} <= obtenidas()
    nuevas = {"sms", "primer_ingreso", "primer_limite", "previsor", "primer_aporte", "fin_de_periodo"}
    assert not nuevas & obtenidas()

    gastar(8000, LUNES, source="sms")
    client.post("/incomes", json={"monto": "50000", "descripcion": "mesada", "fecha": LUNES.isoformat()},
                headers=auth_headers)  # fmt: skip
    client.patch("/categories/1", json={"limite": "200000"}, headers=auth_headers)
    client.post("/recurring-expenses", json={"monto": "5000", "descripcion": "bus", "category_id": 2, "dia_semana": 0},
                headers=auth_headers)  # fmt: skip
    meta = client.post("/goals", json={"nombre": "Viaje", "monto_objetivo": "50000"}, headers=auth_headers).json()
    client.post(f"/goals/{meta['id']}/contributions", json={"monto": "5000"}, headers=auth_headers)
    assert nuevas - {"fin_de_periodo"} <= obtenidas()
    # El presupuesto sigue en curso: "Llegué al final" todavía no.
    assert "fin_de_periodo" not in obtenidas()

    # Terminó el periodo sin gastar más de lo que había.
    fijar_hoy(date(2026, 3, 16))
    assert "fin_de_periodo" in obtenidas()


def test_el_catalogo_de_insignias_esta_completo_en_ambos_idiomas():
    assert len(gamification_service.INSIGNIAS) == 23
    for codigo, textos in gamification_service.INSIGNIAS.items():
        assert set(textos) == {"es", "en"}, codigo
        assert all(len(parte) > 3 for idioma in textos.values() for parte in idioma), codigo

