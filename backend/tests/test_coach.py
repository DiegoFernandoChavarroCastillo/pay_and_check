"""Fases 3 y 4 de plan-app-movil.md: recibos por OCR, check-ins, patrones y coach."""

from datetime import date, timedelta
from decimal import Decimal

import pytest

import app.routers.expenses as expenses_router
import app.services.coach as coach_service
from app.core.time import fmt_fecha
from app.services.groq_client import ExpenseParseError, GroqServiceError, _validar_gasto
from app.services.prompts import build_coach_rules

LUNES = date(2026, 3, 30)
ENTRETENIMIENTO = 3


@pytest.fixture()
def gastos_de_fin_de_semana(categorias, presupuesto, gastar, fijar_hoy):
    """Cuatro sábados con gasto alto en entretenimiento y un solo gasto pequeño entre semana."""
    fijar_hoy(LUNES)
    presupuesto(date(2026, 2, 1), date(2026, 4, 30))
    for sabado in (date(2026, 3, 7), date(2026, 3, 14), date(2026, 3, 21), date(2026, 3, 28)):
        gastar(40000, sabado, ENTRETENIMIENTO, "salida")
    gastar(5000, date(2026, 3, 10), ENTRETENIMIENTO, "cine")
    gastar(8000, date(2026, 3, 11), 1, "almuerzo")


def _un_mensaje_por_patron(_prompt, contenido):
    return {"mensajes": [f"consejo {i}" for i in range(len(contenido.splitlines()))]}


# --- Recibos ----------------------------------------------------------------


def test_parse_receipt_devuelve_comercio_sin_guardar(client, auth_headers, categorias, monkeypatch):
    monkeypatch.setattr(
        expenses_router,
        "parse_receipt_text",
        lambda texto, categorias, hoy: {
            "monto": Decimal("23500"), "categoria": "comida", "descripcion": "mercado",
            "fecha": date(2026, 3, 1), "comercio": "Éxito",
        },
    )
    r = client.post("/expenses/parse-receipt", json={"texto_ocr": "EXITO\nTOTAL 23.500"}, headers=auth_headers)
    assert r.status_code == 200
    assert r.json()["comercio"] == "Éxito"
    assert client.get("/expenses", headers=auth_headers).json() == []


def test_parse_receipt_ilegible_da_422_y_groq_caido_502(client, auth_headers, categorias, monkeypatch):
    def _ilegible(*_args):
        raise ExpenseParseError("No se pudo identificar un monto en el texto.")

    monkeypatch.setattr(expenses_router, "parse_receipt_text", _ilegible)
    r = client.post("/expenses/parse-receipt", json={"texto_ocr": "###"}, headers=auth_headers)
    assert r.status_code == 422

    def _caido(*_args):
        raise GroqServiceError("sin red")

    monkeypatch.setattr(expenses_router, "parse_receipt_text", _caido)
    r = client.post("/expenses/parse-receipt", json={"texto_ocr": "TOTAL 5000"}, headers=auth_headers)
    assert r.status_code == 502


def test_las_fechas_de_los_consejos_van_en_palabras():
    assert fmt_fecha(date(2026, 10, 13)) == "13 de octubre"
    assert fmt_fecha(date(2026, 10, 13), "en") == "October 13"
    assert fmt_fecha(date(2026, 3, 1), con_anio=True) == "1 de marzo de 2026"


def test_validar_gasto_no_inventa_datos():
    ok = _validar_gasto(
        '{"monto": 23500, "categoria": "comida", "descripcion": "mercado", "fecha": "2026-03-01", '
        '"comercio": " Éxito "}',
        ["comida"],
    )
    assert (ok["monto"], ok["comercio"]) == (Decimal("23500"), "Éxito")

    # Sin el modo JSON de Groq el modelo puede envolver el objeto en backticks o texto.
    envuelto = _validar_gasto(
        'Aquí va:\n```json\n{"monto": 10, "categoria": "comida", "descripcion": "x", "fecha": "2026-03-01"}\n```',
        ["comida"],
    )
    assert envuelto["monto"] == Decimal("10")

    # Un ingreso llega sin categoría y eso es válido; un gasto sin categoría, no.
    ingreso = _validar_gasto(
        '{"tipo": "ingreso", "monto": 200000, "categoria": null, "descripcion": "pago", "fecha": "2026-03-01"}',
        ["comida"],
    )
    assert (ingreso["tipo"], ingreso["categoria"], ok["tipo"]) == ("ingreso", None, "gasto")

    for malo in (
        "no es json",
        None,
        "",
        '{"error": "no se pudo identificar un monto"}',
        '{"monto": 0, "categoria": "comida", "descripcion": "x", "fecha": "2026-03-01"}',
        '{"monto": 10, "categoria": "inventada", "descripcion": "x", "fecha": "2026-03-01"}',
        '{"tipo": "gasto", "monto": 10, "categoria": null, "descripcion": "x", "fecha": "2026-03-01"}',
        '{"tipo": "regalo", "monto": 10, "categoria": "comida", "descripcion": "x", "fecha": "2026-03-01"}',
        '{"monto": 10, "categoria": "comida", "descripcion": "x", "fecha": "ayer"}',
    ):
        with pytest.raises(ExpenseParseError):
            _validar_gasto(malo, ["comida"])


# --- Check-ins --------------------------------------------------------------


def test_checkin_es_uno_por_dia_y_se_reemplaza(client, auth_headers, fijar_hoy):
    fijar_hoy(LUNES)
    r = client.post("/checkins", json={"animo": "ansioso"}, headers=auth_headers)
    assert r.status_code == 200
    r = client.post("/checkins", json={"animo": "tranquilo", "nota": "mejor"}, headers=auth_headers)
    assert r.status_code == 200

    checkins = client.get("/checkins", headers=auth_headers).json()
    assert [(c["fecha"], c["animo"], c["nota"]) for c in checkins] == [("2026-03-30", "tranquilo", "mejor")]

    r = client.post("/checkins", json={"animo": "eufórico"}, headers=auth_headers)
    assert r.status_code == 422


# --- Patrones e insights ----------------------------------------------------


def test_insights_detectan_gasto_de_fin_de_semana_con_cifras_y_accion(
    client, auth_headers, gastos_de_fin_de_semana, monkeypatch
):
    monkeypatch.setattr(coach_service, "generate_coach_json", _un_mensaje_por_patron)

    insights = client.get("/coach/insights", headers=auth_headers).json()
    finde = next(i for i in insights if i["tipo"] == "fin_de_semana")

    # 4 sábados x 40.000 entre 8 días de fin de semana = 20.000; 5.000 entre 20 días hábiles = 250.
    assert finde["datos"]["categoria"] == "entretenimiento"
    assert Decimal(finde["datos"]["promedio_fin_de_semana"]) == Decimal("20000.00")
    assert Decimal(finde["datos"]["promedio_entre_semana"]) == Decimal("250.00")
    assert "20.000" in finde["descripcion"]
    assert finde["mensaje"].startswith("consejo")
    assert finde["accion"]["tipo"] == "crear_reto"
    assert finde["accion"]["payload"] == {
        "plantilla": "reducir_categoria", "category_id": ENTRETENIMIENTO, "porcentaje": 20,
    }

    # La acción de un tap funciona tal cual contra el endpoint normal... si hay gasto la semana previa.
    r = client.post("/challenges", json=finde["accion"]["payload"], headers=auth_headers)
    assert r.status_code == 201, r.text


def test_insights_se_cachean_por_dia_y_refresh_los_recalcula(
    client, auth_headers, gastos_de_fin_de_semana, monkeypatch
):
    llamadas = []

    def _contar(prompt, contenido):
        llamadas.append(prompt)
        return _un_mensaje_por_patron(prompt, contenido)

    monkeypatch.setattr(coach_service, "generate_coach_json", _contar)

    primero = client.get("/coach/insights", headers=auth_headers).json()
    assert client.get("/coach/insights", headers=auth_headers).json() == primero
    assert len(llamadas) == 1

    client.get("/coach/insights?refresh=true", headers=auth_headers)
    assert len(llamadas) == 2

    # Cambiar el tono invalida la caché: el consejo debe redactarse en el nuevo estilo.
    client.patch("/auth/me", json={"coach_tone": "directo"}, headers=auth_headers)
    client.get("/coach/insights", headers=auth_headers)
    assert len(llamadas) == 3
    assert "al grano" in llamadas[-1]


def test_insights_usan_el_texto_determinista_si_la_ia_falla_o_rompe_las_reglas(
    client, auth_headers, gastos_de_fin_de_semana, monkeypatch
):
    def _caido(*_args):
        raise GroqServiceError("sin red")

    monkeypatch.setattr(coach_service, "generate_coach_json", _caido)
    insights = client.get("/coach/insights", headers=auth_headers).json()
    assert insights and all(i["mensaje"] == i["descripcion"] for i in insights)

    monkeypatch.setattr(
        coach_service,
        "generate_coach_json",
        lambda _p, contenido: {"mensajes": ["Eres un irresponsable con tu plata."] * len(contenido.splitlines())},
    )
    insights = client.get("/coach/insights?refresh=true", headers=auth_headers).json()
    assert all(i["mensaje"] == i["descripcion"] for i in insights)


def test_sin_datos_no_hay_insights_ni_llamada_a_la_ia(client, auth_headers, monkeypatch):
    def _no_debe_llamarse(*_args):
        raise AssertionError("no hay patrones: no se debe llamar a la IA")

    monkeypatch.setattr(coach_service, "generate_coach_json", _no_debe_llamarse)
    assert client.get("/coach/insights", headers=auth_headers).json() == []


def test_patron_animo_y_gasto(client, auth_headers, categorias, presupuesto, gastar, fijar_hoy, monkeypatch):
    monkeypatch.setattr(coach_service, "generate_coach_json", _un_mensaje_por_patron)
    presupuesto(date(2026, 2, 1), date(2026, 4, 30))

    # Dos días con ansiedad y gasto alto, dos días tranquilos con gasto bajo.
    for dia, animo, monto in (
        (date(2026, 3, 24), "ansioso", 60000),
        (date(2026, 3, 25), "preocupado", 40000),
        (date(2026, 3, 26), "tranquilo", 10000),
        (date(2026, 3, 27), "confiado", 10000),
    ):
        fijar_hoy(dia)
        client.post("/checkins", json={"animo": animo}, headers=auth_headers)
        gastar(monto, dia)

    fijar_hoy(LUNES)
    insights = client.get("/coach/insights", headers=auth_headers).json()
    animo = next(i for i in insights if i["tipo"] == "animo_gasto")
    assert "50.000" in animo["descripcion"] and "10.000" in animo["descripcion"]


# --- Reacción y chat --------------------------------------------------------


def test_reaccion_usa_la_ia_y_cae_al_respaldo_sin_culpa(
    client, auth_headers, categorias, presupuesto, gastar, fijar_hoy, monkeypatch
):
    fijar_hoy(LUNES)
    presupuesto(LUNES, LUNES + timedelta(days=9), monto="100000.00")
    gasto = gastar(10000, LUNES)

    vistos = {}

    def _ia(prompt, _mensajes=None):
        vistos["prompt"] = prompt
        return "Buen registro, vas con 9.000 por día."

    monkeypatch.setattr(coach_service, "generate_coach_text", _ia)
    r = client.post("/coach/reaction", json={"expense_id": gasto["id"]}, headers=auth_headers)
    assert r.json()["mensaje"] == "Buen registro, vas con 9.000 por día."
    # El contexto que recibe la IA trae la cifra real: (100.000 - 10.000) / 10 días.
    assert "Disponible por día: 9.000" in vistos["prompt"]

    monkeypatch.setattr(coach_service, "generate_coach_text", lambda *_a: "Qué vergüenza, otra vez malgastando.")
    r = client.post("/coach/reaction", json={"expense_id": gasto["id"]}, headers=auth_headers)
    assert "9.000" in r.json()["mensaje"] and "vergüenza" not in r.json()["mensaje"]

    def _caido(*_args):
        raise GroqServiceError("sin red")

    monkeypatch.setattr(coach_service, "generate_coach_text", _caido)
    r = client.post("/coach/reaction", json={"expense_id": gasto["id"]}, headers=auth_headers)
    assert r.status_code == 200 and "9.000" in r.json()["mensaje"]

    r = client.post("/coach/reaction", json={"expense_id": 9999}, headers=auth_headers)
    assert r.status_code == 404


def test_chat_guarda_el_historial_y_lo_envia_como_contexto(client, auth_headers, monkeypatch):
    recibidos = []

    def _ia(_prompt, mensajes=None):
        recibidos.append(mensajes)
        return f"respuesta {len(recibidos)}"

    monkeypatch.setattr(coach_service, "generate_coach_text", _ia)

    r = client.post("/coach/chat", json={"mensaje": "hola"}, headers=auth_headers)
    assert (r.json()["rol"], r.json()["contenido"]) == ("coach", "respuesta 1")
    client.post("/coach/chat", json={"mensaje": "¿cómo voy?"}, headers=auth_headers)

    assert [m["content"] for m in recibidos[1]] == ["hola", "respuesta 1", "¿cómo voy?"]
    historial = client.get("/coach/chat", headers=auth_headers).json()
    assert [(m["rol"], m["contenido"]) for m in historial] == [
        ("usuario", "hola"), ("coach", "respuesta 1"), ("usuario", "¿cómo voy?"), ("coach", "respuesta 2"),
    ]


def test_chat_no_da_asesoria_de_inversion_y_no_guarda_nada_si_la_ia_cae(client, auth_headers, monkeypatch):
    monkeypatch.setattr(coach_service, "generate_coach_text", lambda *_a: "Te recomiendo invertir en Bitcoin ya.")
    r = client.post("/coach/chat", json={"mensaje": "¿en qué invierto?"}, headers=auth_headers)
    assert r.status_code == 200
    assert "bitcoin" not in r.json()["contenido"].lower()
    assert "no asesoría financiera" in r.json()["contenido"]

    def _caido(*_args):
        raise GroqServiceError("sin red")

    monkeypatch.setattr(coach_service, "generate_coach_text", _caido)
    r = client.post("/coach/chat", json={"mensaje": "hola"}, headers=auth_headers)
    assert r.status_code == 502
    assert len(client.get("/coach/chat", headers=auth_headers).json()) == 2


def test_las_reglas_del_coach_incluyen_tono_idioma_y_guardrails():
    reglas = build_coach_rules("Ana", "humoristico", "en")
    assert "Ana" in reglas and "humor amable" in reglas and "inglés" in reglas
    assert "Cero culpa" in reglas and "No das asesoría de inversión" in reglas

    assert coach_service.rompe_guardrails("Vas muy bien, sigue así.") is None
    assert coach_service.rompe_guardrails("Eso fue irresponsable.") == "culpa"
    assert coach_service.rompe_guardrails("Compra acciones de esa empresa.") == "inversion"
