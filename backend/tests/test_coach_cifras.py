"""El chat responde en concreto: las cifras que alguien puede preguntar ("¿cuánto puedo gastar por semana?")
llegan ya calculadas al modelo, y si el modelo no las da (o le devuelve la cuenta a la persona) responde el
backend con la cifra."""

import json
from datetime import date, timedelta

import pytest

import app.services.coach as coach_service
from app.services.coach import pide_la_cuenta
from app.services.groq_client import GroqServiceError

HOY = date(2026, 3, 30)  # lunes
INICIO, FIN = date(2026, 3, 16), date(2026, 4, 12)  # 28 días; con HOY quedan 14
PREGUNTA = "¿Cuánto tengo disponible para gastar semanalmente?"


def _turno(respuesta: str, en_alcance: bool = True) -> str:
    return json.dumps({"en_alcance": en_alcance, "respuesta": respuesta})


@pytest.fixture()
def situacion(client, auth_headers, categorias, presupuesto, gastar, fijar_hoy):
    """Presupuesto de 280.000 con 40.000 gastados hoy: quedan 240.000 en 14 días, 120.000 por semana."""
    fijar_hoy(HOY)
    presupuesto(INICIO, FIN, monto="280000.00")
    gastar(40000, HOY)


@pytest.fixture()
def ia(monkeypatch):
    """Groq falso: devuelve las respuestas en orden y guarda los prompts que recibió."""

    def _poner(*respuestas):
        llamadas = []
        pendientes = list(respuestas)

        def _generar(prompt, turnos=None):
            llamadas.append({"prompt": prompt, "turnos": turnos})
            siguiente = pendientes.pop(0) if len(pendientes) > 1 else pendientes[0]
            if isinstance(siguiente, Exception):
                raise siguiente
            return siguiente

        monkeypatch.setattr(coach_service, "generate_coach_text", _generar)
        return llamadas

    return _poner


def _chat(client, auth_headers, mensaje=PREGUNTA):
    r = client.post("/coach/chat", json={"mensaje": mensaje}, headers=auth_headers)
    assert r.status_code == 200, r.text
    return r.json()


def test_el_contexto_trae_el_disponible_por_semana_ya_calculado(client, auth_headers, situacion, ia):
    llamadas = ia(_turno("Puedes gastar 120.000 por semana."))
    _chat(client, auth_headers)

    prompt = llamadas[0]["prompt"]
    assert "Cifras ya calculadas" in prompt
    assert "Disponible para gastar por semana: 120.000." in prompt
    assert "Gastado esta semana (desde el lunes): 40.000." in prompt
    assert "Nunca le pidas a la persona que haga una cuenta" in prompt


def test_la_respuesta_con_la_cifra_se_muestra_tal_cual(client, auth_headers, situacion, ia):
    ia(_turno("Esta semana puedes gastar 120.000. ¡Vas bien!"))
    assert _chat(client, auth_headers)["contenido"] == "Esta semana puedes gastar 120.000. ¡Vas bien!"


def test_si_le_devuelve_la_cuenta_se_reintenta_con_las_cifras(client, auth_headers, situacion, ia):
    llamadas = ia(
        _turno("Toma tu disponible y divide entre las semanas que quedan."),
        _turno("Puedes gastar 120.000 por semana."),
    )
    assert _chat(client, auth_headers)["contenido"] == "Puedes gastar 120.000 por semana."
    assert len(llamadas) == 2
    assert "Cifras ya calculadas" in llamadas[1]["turnos"][-1]["content"]


def test_si_insiste_en_que_haga_la_cuenta_responde_el_backend_con_la_cifra(
    client, auth_headers, situacion, ia
):
    ia(_turno("Haz la cuenta: divide tu disponible entre 2."))
    contenido = _chat(client, auth_headers)["contenido"]

    assert "120.000 por semana" in contenido
    assert "divide" not in contenido.lower()


def test_con_groq_caido_la_pregunta_semanal_igual_recibe_la_cifra(client, auth_headers, situacion, ia):
    ia(GroqServiceError("caído"))
    mensaje = _chat(client, auth_headers)

    assert "120.000 por semana" in mensaje["contenido"]
    assert mensaje["id"] == coach_service.SIN_GUARDAR


def test_con_menos_de_una_semana_es_todo_lo_que_queda(client, auth_headers, categorias, presupuesto, fijar_hoy, ia):
    fijar_hoy(FIN - timedelta(days=4))  # quedan 5 días
    presupuesto(INICIO, FIN, monto="100000.00")
    llamadas = ia(GroqServiceError("caído"))
    contenido = _chat(client, auth_headers)["contenido"]

    assert "esta semana puedes gastar todo lo que queda: 100.000" in contenido
    assert llamadas  # sí intentó la IA


def test_sin_presupuesto_lo_dice_en_vez_de_inventar(client, auth_headers, fijar_hoy, ia):
    fijar_hoy(HOY)
    ia(GroqServiceError("caído"))
    assert "no tienes un presupuesto activo" in _chat(client, auth_headers)["contenido"]


def test_por_dia_y_en_total(client, auth_headers, situacion, ia):
    ia(GroqServiceError("caído"))
    assert "17.143 por día" in _chat(client, auth_headers, "¿Cuánto puedo gastar por día?")["contenido"]
    assert "Tienes 240.000 disponibles" in _chat(client, auth_headers, "¿Cuánto me queda?")["contenido"]


def test_el_contexto_trae_el_progreso_de_las_metas(client, auth_headers, situacion, ia):
    r = client.post("/goals", json={"nombre": "Celular", "monto_objetivo": "500000.00"}, headers=auth_headers)
    assert r.status_code == 201, r.text
    llamadas = ia(_turno("Vas bien con tu meta."))
    _chat(client, auth_headers, "¿Cómo va mi meta?")

    assert "Meta de ahorro activa: Celular: objetivo 500.000, ahorrado 0, falta 500.000." in llamadas[0]["prompt"]


def test_un_turno_redirigido_no_se_reenvia_como_historial(client, auth_headers, situacion, ia):
    llamadas = ia(_turno("Puedes gastar 120.000 por semana."))
    _chat(client, auth_headers, "dame un codigo de python que diga hola mundo")
    _chat(client, auth_headers)

    contenidos = [t["content"] for t in llamadas[-1]["turnos"]]
    assert not any("python" in c for c in contenidos)
    assert not any("Solo puedo ayudarte" in c for c in contenidos)


@pytest.mark.parametrize(
    "texto",
    [
        "Toma tu disponible y divide entre las semanas.",
        "Haz la cuenta con tu saldo.",
        "Divídelo entre 4 y listo.",
        "Just do the math: divide your balance by the weeks left.",
    ],
)
def test_pide_la_cuenta_detecta_respuestas_que_no_responden(texto):
    assert pide_la_cuenta(texto)


def test_pide_la_cuenta_no_marca_respuestas_concretas():
    assert not pide_la_cuenta("Puedes gastar 120.000 por semana; tus gastos se dividen sobre todo en comida.")
