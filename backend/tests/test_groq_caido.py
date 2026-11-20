"""PS-104: con Groq caído, limitado o sin respuesta, la API degrada y nunca responde 500 ni 502.

Cliente de Groq falso: nada sale a la red."""

from datetime import date
from types import SimpleNamespace

import pytest

import app.services.groq_client as groq_client
from app.routers.expenses import SIN_IA
from app.services.coach import SIN_GUARDAR

LUNES = date(2026, 3, 30)


class RateLimitError(Exception):
    """Imita el 429 de Groq (`groq.RateLimitError`): _chat convierte cualquier excepción del SDK."""


ERRORES = {
    "red": ConnectionError("connection reset by peer"),
    "timeout": TimeoutError("request timed out"),
    "429": RateLimitError("429 rate_limit_exceeded: tokens per minute"),
}

REGISTRO = ("registro", "recibo", "from-text")
ENDPOINTS = {
    "registro": ("post", "/expenses/parse", lambda _: {"texto": "café 5000"}),
    "recibo": ("post", "/expenses/parse-receipt", lambda _: {"texto_ocr": "TOTAL 5.000"}),
    "from-text": ("post", "/expenses/from-text", lambda _: {"texto": "café 5000"}),
    "reaccion": ("post", "/coach/reaction", lambda gasto: {"expense_id": gasto["id"]}),
    "consejos": ("get", "/coach/insights", None),
    "chat": ("post", "/coach/chat", lambda _: {"mensaje": "hola"}),
    "reporte": ("get", "/reports/weekly", None),
    "wrapped": ("get", "/reports/monthly-wrapped", None),
}


class _Groq:
    """Lanza `error` o devuelve `contenido` (que puede ser None, como hace Groq cuando el modelo solo razonó)."""

    def __init__(self, error=None, contenido=None):
        self.error, self.contenido, self.llamadas = error, contenido, 0
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))

    def _create(self, **_kwargs):
        self.llamadas += 1
        if self.error is not None:
            raise self.error
        mensaje = SimpleNamespace(content=self.contenido)
        return SimpleNamespace(choices=[SimpleNamespace(message=mensaje)], usage=None)


@pytest.fixture()
def groq(monkeypatch):
    def _poner(**kwargs):
        falso = _Groq(**kwargs)
        monkeypatch.setattr(groq_client, "_get_client", lambda: falso)
        return falso

    return _poner


@pytest.fixture()
def gasto(categorias, presupuesto, gastar, fijar_hoy):
    """Un presupuesto con gastos en fin de semana (hay consejos que dar) y un gasto reciente."""
    fijar_hoy(LUNES)
    presupuesto(date(2026, 2, 1), date(2026, 4, 30))
    for sabado in (date(2026, 3, 7), date(2026, 3, 14), date(2026, 3, 21), date(2026, 3, 28)):
        gastar(40000, sabado, 3, "salida")
    gastar(5000, date(2026, 3, 10), 3, "cine")
    return gastar(8000, date(2026, 3, 11), 1, "almuerzo")


def _llamar(client, headers, endpoint, gasto):
    metodo, ruta, cuerpo = ENDPOINTS[endpoint]
    return getattr(client, metodo)(ruta, headers=headers, **({"json": cuerpo(gasto)} if cuerpo else {}))


# --- Groq caído o limitado -------------------------------------------------------


@pytest.mark.parametrize("error", ERRORES)
@pytest.mark.parametrize("endpoint", REGISTRO)
def test_el_registro_con_groq_caido_da_503_y_lleva_al_formulario_manual(
    client, auth_headers, gasto, groq, endpoint, error
):
    groq(error=ERRORES[error])

    r = _llamar(client, auth_headers, endpoint, gasto)

    assert r.status_code == 503
    assert r.json()["detail"] == SIN_IA and "formulario manual" in SIN_IA
    assert "Groq" not in r.json()["detail"] and error not in r.json()["detail"]  # nada del error interno


@pytest.mark.parametrize("error", ERRORES)
def test_el_chat_con_groq_caido_responde_su_respaldo_y_no_guarda_el_turno(
    client, auth_headers, gasto, groq, db_engine, error
):
    groq(error=ERRORES[error])

    r = client.post("/coach/chat", json={"mensaje": "¿cómo voy?"}, headers=auth_headers)

    assert r.status_code == 200
    assert r.json()["contenido"].startswith("Ahora mismo no puedo responder con detalle")
    assert "Disponible" in r.json()["contenido"]  # lleva la situación real de la persona
    assert (r.json()["id"], r.json()["rol"]) == (SIN_GUARDAR, "coach")
    # El historial se reenvía al modelo y no debe llevar textos de respaldo (ni el mensaje que no se respondió).
    assert client.get("/coach/chat", headers=auth_headers).json() == []


def test_el_chat_caido_no_toca_el_historial_que_ya_habia(client, auth_headers, groq):
    groq(contenido='{"en_alcance": true, "respuesta": "Vas bien."}')
    client.post("/coach/chat", json={"mensaje": "hola"}, headers=auth_headers)
    antes = client.get("/coach/chat", headers=auth_headers).json()
    assert len(antes) == 2

    groq(error=ERRORES["429"])
    assert client.post("/coach/chat", json={"mensaje": "otra"}, headers=auth_headers).status_code == 200

    assert client.get("/coach/chat", headers=auth_headers).json() == antes


@pytest.mark.parametrize("error", ERRORES)
@pytest.mark.parametrize("endpoint", ["reaccion", "consejos", "reporte", "wrapped"])
def test_el_resto_de_la_ia_degrada_a_sus_textos_de_respaldo(client, auth_headers, gasto, groq, endpoint, error):
    groq(error=ERRORES[error])
    assert _llamar(client, auth_headers, endpoint, gasto).status_code == 200


def test_con_groq_caido_el_reporte_semanal_dice_que_no_hay_recomendaciones(client, auth_headers, gasto, groq):
    groq(error=ERRORES["red"])
    r = client.get("/reports/weekly", headers=auth_headers)
    assert r.json()["recomendaciones"] == "No se pudieron generar recomendaciones de IA en este momento."
    assert r.json()["gasto_total_semana"] is not None  # el resumen numérico sigue


# --- Groq responde, pero sin nada ------------------------------------------------


@pytest.mark.parametrize("contenido", [None, ""])
def test_una_respuesta_vacia_de_groq_no_es_un_500(client, auth_headers, gasto, groq, contenido):
    groq(contenido=contenido)

    chat = client.post("/coach/chat", json={"mensaje": "hola"}, headers=auth_headers)
    assert chat.status_code == 200 and chat.json()["id"] == SIN_GUARDAR
    assert client.get("/coach/chat", headers=auth_headers).json() == []

    semanal = client.get("/reports/weekly", headers=auth_headers)
    assert semanal.status_code == 200 and semanal.json()["recomendaciones"].strip()  # el resumen de respaldo

    reaccion = _llamar(client, auth_headers, "reaccion", gasto)
    assert reaccion.status_code == 200 and "por día" in reaccion.json()["mensaje"]

    # Un parseo sin nada que interpretar es un 422 (no un gasto), nunca un 5xx.
    assert _llamar(client, auth_headers, "registro", gasto).status_code == 422


@pytest.mark.parametrize("fallo", [*ERRORES, "vacio", "none"])
@pytest.mark.parametrize("endpoint", ENDPOINTS)
def test_ningun_endpoint_con_ia_responde_500_ni_502(client, auth_headers, gasto, groq, endpoint, fallo):
    if fallo in ERRORES:
        groq(error=ERRORES[fallo])
    else:
        groq(contenido="" if fallo == "vacio" else None)

    assert _llamar(client, auth_headers, endpoint, gasto).status_code not in (500, 502)


# --- El cliente ----------------------------------------------------------------


def test_el_cliente_de_groq_se_crea_con_timeout_de_15_segundos_y_sin_reintentos(monkeypatch):
    creados = []

    class _Espia:
        def __init__(self, **kwargs):
            creados.append(kwargs)

    monkeypatch.setattr(groq_client, "Groq", _Espia)
    monkeypatch.setattr(groq_client, "_client", None)

    groq_client._get_client()

    assert creados == [{"api_key": groq_client.settings.GROQ_API_KEY, "timeout": 15.0, "max_retries": 0}]
