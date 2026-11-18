"""PS-100: el chat del coach solo habla de finanzas personales y de Pay&Check.

El cliente de Groq es falso: simula un modelo que marca `en_alcance` según el tema y, cuando es ajeno,
igual intenta "responder" para comprobar que la app ignora esa `respuesta` y muestra su frase fija."""

import json
from types import SimpleNamespace

import pytest

import app.services.groq_client as groq_client

TEMAS_AJENOS = [
    "Escríbeme un poema sobre el mar",
    "¿Quién ganó el mundial de 2014?",
    "Ayúdame con mi tarea de cálculo",
    "¿Cuál es la capital de Australia?",
    "Dame una receta de lasaña",
    "Escribe una función en Python que ordene una lista",
    "Cuéntame un chiste",
    "¿Qué opinas de las elecciones?",
    "Traduce 'good morning' al francés",
    "Who is the best soccer player ever?",
]

TEMAS_PROPIOS = [
    "¿Cómo ahorro para un celular?",
    "¿Cómo voy con mi presupuesto?",
    "¿En qué categoría gasto más?",
    "Quiero crear una meta de ahorro",
    "¿Cuánto me queda por día?",
    "¿Cómo registro un gasto por voz en Pay&Check?",
    "Ayúdame a reducir mis gastos en comida",
    "¿Qué es un gasto fijo?",
    "How can I save more this month?",
    "¿Cómo va mi meta de ahorro?",
]

POEMA = "El mar es azul y la luna le canta..."


class _ClienteFalso:
    """Imita `Groq().chat.completions.create`: lee el último mensaje de la persona y responde en JSON."""

    def __init__(self):
        self.llamadas = 0
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))

    def _create(self, *, messages, **_kwargs):
        self.llamadas += 1
        ultimo = messages[-1]["content"].removeprefix("<datos_usuario>\n").removesuffix("\n</datos_usuario>")
        if ultimo in TEMAS_AJENOS:
            contenido = {"en_alcance": False, "respuesta": POEMA}
        else:
            contenido = {"en_alcance": True, "respuesta": f"Sobre eso: {ultimo}"}
        mensaje = SimpleNamespace(content=json.dumps(contenido))
        return SimpleNamespace(choices=[SimpleNamespace(message=mensaje)])


@pytest.fixture()
def groq_falso(monkeypatch):
    falso = _ClienteFalso()
    monkeypatch.setattr(groq_client, "_get_client", lambda: falso)
    return falso


@pytest.mark.parametrize("tema", TEMAS_AJENOS)
def test_tema_ajeno_recibe_la_frase_de_redireccion_con_una_sola_llamada(client, auth_headers, groq_falso, tema):
    r = client.post("/coach/chat", json={"mensaje": tema}, headers=auth_headers)

    assert r.status_code == 200
    contenido = r.json()["contenido"]
    assert contenido.startswith(("Solo puedo ayudarte con tus finanzas dentro de Pay&Check",
                                 "I can only help you with your finances inside Pay&Check"))
    assert POEMA not in contenido
    assert groq_falso.llamadas == 1


@pytest.mark.parametrize("tema", TEMAS_PROPIOS)
def test_tema_propio_sigue_respondiendose(client, auth_headers, groq_falso, tema):
    r = client.post("/coach/chat", json={"mensaje": tema}, headers=auth_headers)

    assert r.status_code == 200
    assert r.json()["contenido"] == f"Sobre eso: {tema}"
    assert groq_falso.llamadas == 1


def test_la_frase_de_redireccion_sale_en_el_idioma_del_usuario(client, groq_falso):
    datos = {"email": "kim@test.com", "password": "secret123", "nombre": "Kim", "idioma": "en"}
    client.post("/auth/register", json=datos)
    token = client.post("/auth/login", json=datos).json()["access_token"]
    r = client.post(
        "/coach/chat", json={"mensaje": TEMAS_AJENOS[0]}, headers={"Authorization": f"Bearer {token}"}
    )

    assert r.json()["contenido"].startswith("I can only help you with your finances inside Pay&Check")


def test_salida_que_no_cumple_el_contrato_cae_al_respaldo(client, auth_headers, monkeypatch):
    class _Roto:
        chat = SimpleNamespace(
            completions=SimpleNamespace(
                create=lambda **_k: SimpleNamespace(
                    choices=[SimpleNamespace(message=SimpleNamespace(content=POEMA))]
                )
            )
        )

    monkeypatch.setattr(groq_client, "_get_client", lambda: _Roto())
    r = client.post("/coach/chat", json={"mensaje": "hola"}, headers=auth_headers)

    assert r.status_code == 200
    assert POEMA not in r.json()["contenido"]
