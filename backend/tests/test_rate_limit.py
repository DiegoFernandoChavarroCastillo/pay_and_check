"""PS-103: límite de tasa por usuario en la IA y por IP/email en el login."""

import pytest
from fastapi.testclient import TestClient

import app.services.groq_client as groq_client
from app.core import rate_limit
from app.core.rate_limit import LimiteDeTasa
from app.main import app
from tests.test_ia_uso import CHAT_OK, _GroqFalso


class _Reloj:
    def __init__(self):
        self.t = 1000.0


@pytest.fixture()
def reloj(monkeypatch):
    falso = _Reloj()
    monkeypatch.setattr(rate_limit, "_reloj", lambda: falso.t)
    return falso


@pytest.fixture()
def groq(monkeypatch):
    falso = _GroqFalso(CHAT_OK)
    monkeypatch.setattr(groq_client, "_get_client", lambda: falso)
    return falso


def _chat(client, headers):
    return client.post("/coach/chat", json={"mensaje": "hola"}, headers=headers)


# --- La ventana -----------------------------------------------------------------


def test_la_ventana_se_desliza_y_dice_cuanto_falta(reloj):
    limite = LimiteDeTasa(maximo=3, ventana_s=10)
    assert [limite.consumir("a") for _ in range(3)] == [0, 0, 0]

    assert limite.consumir("a") == 10  # recién llenada: hay que esperar toda la ventana
    reloj.t += 4
    assert limite.consumir("a") == 6  # ceil(10 - 4)
    reloj.t += 5.5
    assert limite.consumir("a") == 1  # ceil(0.5)

    # Lo rechazado no se registró: pasada la ventana entran de nuevo los tres.
    reloj.t += 0.5
    assert [limite.consumir("a") for _ in range(3)] == [0, 0, 0]
    assert limite.consumir("b") == 0  # cada clave lleva su cuenta


def test_los_eventos_viejos_salen_de_a_uno(reloj):
    limite = LimiteDeTasa(maximo=2, ventana_s=10)
    limite.consumir("a")
    reloj.t += 6
    limite.consumir("a")
    assert limite.consumir("a") == 4  # espera a que salga el primero, no los dos

    reloj.t += 4
    assert limite.consumir("a") == 0
    assert limite.consumir("a") == 6


def test_espera_toma_la_clave_mas_ocupada_y_olvidar_la_libera(reloj):
    limite = LimiteDeTasa(maximo=1, ventana_s=10)
    limite.registrar("x")
    reloj.t += 3
    limite.registrar("y")
    assert limite.espera("x", "y") == 10  # "x" espera 7 y "y" espera 10: manda la mayor
    assert limite.espera("z") == 0
    limite.olvidar("y")
    assert limite.espera("x", "y") == 7  # queda solo "x"
    limite.olvidar("x")
    assert limite.espera("x", "y") == 0


def test_las_claves_vencidas_no_se_acumulan(reloj):
    limite = LimiteDeTasa(maximo=1, ventana_s=10)
    for i in range(50):
        limite.registrar(f"k{i}")
    reloj.t += 11
    assert [limite.espera(f"k{i}") for i in range(50)] == [0] * 50
    assert limite._eventos == {}


# --- La IA ----------------------------------------------------------------------


def test_la_solicitud_21_de_ia_en_un_minuto_da_429_con_retry_after(client, auth_headers, groq, reloj):
    for _ in range(20):
        assert _chat(client, auth_headers).status_code == 200

    r = _chat(client, auth_headers)
    assert r.status_code == 429
    assert r.headers["Retry-After"] == "60"
    assert r.json()["detail"] == "Demasiadas solicitudes de IA seguidas. Intenta de nuevo en 60 segundos."
    assert groq.llamadas == 20  # la rechazada ni llegó a Groq

    reloj.t += 25
    assert _chat(client, auth_headers).headers.get("Retry-After") == "35"
    reloj.t += 35
    assert _chat(client, auth_headers).status_code == 200  # pasado el tiempo que dijo, vuelve


def test_el_limite_es_por_persona(client, make_user, groq):
    uno, _ = make_user("uno@t.com")
    dos, _ = make_user("dos@t.com")
    for _ in range(20):
        _chat(client, uno)

    assert _chat(client, uno).status_code == 429
    assert _chat(client, dos).status_code == 200


def test_todos_los_endpoints_con_ia_comparten_el_mismo_contador(client, auth_headers, groq):
    con_ia = [
        ("post", "/expenses/parse", {"texto": "café 5000"}),
        ("post", "/expenses/parse-receipt", {"texto_ocr": "TOTAL 5.000"}),
        ("post", "/expenses/from-text", {"texto": "café 5000"}),
        ("post", "/coach/reaction", {"expense_id": 1}),
        ("get", "/coach/insights", None),
        ("post", "/coach/chat", {"mensaje": "hola"}),
        ("get", "/reports/weekly", None),
        ("get", "/reports/monthly-wrapped", None),
    ]

    def llamar(metodo, ruta, cuerpo):
        return getattr(client, metodo)(ruta, headers=auth_headers, **({"json": cuerpo} if cuerpo else {}))

    # El resultado de cada una da igual (404, 422...): lo que cuenta es que pasó el límite.
    for i in range(20):
        assert llamar(*con_ia[i % len(con_ia)]).status_code != 429
    for endpoint in con_ia:
        assert llamar(*endpoint).status_code == 429, endpoint[1]


def test_lo_que_no_usa_ia_no_se_limita_y_sin_sesion_no_hay_contador(client, auth_headers, groq):
    for _ in range(25):
        assert client.get("/coach/chat", headers=auth_headers).status_code == 200  # historial
        assert client.get("/me/subscription", headers=auth_headers).status_code == 200
        assert client.get("/expenses", headers=auth_headers).status_code == 200

    assert client.post("/coach/chat", json={"mensaje": "hola"}).status_code == 401
    assert _chat(client, auth_headers).status_code == 200


# --- El login -------------------------------------------------------------------


def _desde(ip):
    """Un cliente que llega desde otra IP."""
    return TestClient(app, client=(ip, 50000))


def _login(cliente, email="a@t.com", password="secret123"):
    return cliente.post("/auth/login", json={"email": email, "password": password})


def test_diez_fallos_bloquean_el_login_aun_con_la_clave_correcta(client, make_user, reloj):
    make_user("a@t.com")
    for _ in range(10):
        assert _login(client, password="mala").status_code == 401

    r = _login(client)  # la clave correcta, pero ya está bloqueado
    assert r.status_code == 429
    assert r.headers["Retry-After"] == "300"
    assert r.json()["detail"] == "Demasiados intentos fallidos. Intenta de nuevo en 300 segundos."

    reloj.t += 301
    assert _login(client).status_code == 200


def test_los_logins_correctos_no_cuentan(client, make_user):
    make_user("a@t.com")
    for _ in range(25):
        assert _login(client).status_code == 200
    # Y entre medio, cinco fallos no acumulan con los éxitos.
    for _ in range(5):
        _login(client, password="mala")
    assert _login(client).status_code == 200


def test_la_ip_se_bloquea_por_fallos_en_cualquier_cuenta_y_otra_ip_no(client, make_user):
    make_user("a@t.com")
    for i in range(10):
        assert _login(client, email=f"nadie{i}@t.com", password="x").status_code == 401

    assert _login(client).status_code == 429  # esa IP ya no puede ni entrar a su propia cuenta
    assert _login(_desde("10.0.0.9")).status_code == 200  # otra IP sí


def test_el_email_se_bloquea_aunque_los_fallos_vengan_de_ips_distintas(client, make_user):
    make_user("a@t.com")
    make_user("b@t.com")
    for i in range(10):
        assert _login(_desde(f"10.0.1.{i}"), password="mala").status_code == 401

    assert _login(_desde("10.0.2.1")).status_code == 429  # nueva IP, pero la cuenta está bloqueada
    assert _login(_desde("10.0.2.1"), email="b@t.com").status_code == 200  # otra cuenta, no


def test_entrar_bien_perdona_los_fallos_de_esa_cuenta(client, make_user):
    make_user("a@t.com")
    for i in range(5):
        _login(_desde(f"10.0.3.{i}"), password="mala")
    assert _login(_desde("10.0.3.9")).status_code == 200

    # Si no se hubieran perdonado, 5 + 9 fallos ya la habrían bloqueado.
    for i in range(9):
        assert _login(_desde(f"10.0.4.{i}"), password="mala").status_code == 401


def test_una_cuenta_de_google_sin_password_tambien_cuenta_como_fallo(client, db_engine):
    from sqlmodel import Session

    from app.models.user import User

    with Session(db_engine) as session:
        session.add(User(email="g@t.com", google_id="g-1", nombre="G"))
        session.commit()
    for _ in range(10):
        assert _login(client, email="g@t.com").status_code == 400

    assert _login(client, email="g@t.com").status_code == 429
