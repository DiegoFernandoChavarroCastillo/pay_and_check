"""PS-96: el cupo mensual de IA sale del plan (Gratis 50, Premium 300, Institucional 300, Familiar 390 compartidas)."""

from datetime import UTC, date, datetime
from zoneinfo import ZoneInfo

import pytest
from sqlmodel import Session

import app.services.groq_client as groq_client
from app.db.crear_convenio import crear_convenio
from app.models.ai_usage import AiUsage
from tests.test_ia_uso import CHAT_OK, _GroqFalso

pytestmark = pytest.mark.usefixtures("llaves_foraneas")

MARZO = date(2026, 3, 15)


@pytest.fixture(autouse=True)
def _hoy(fijar_hoy):
    fijar_hoy(MARZO)


@pytest.fixture()
def groq(monkeypatch):
    falso = _GroqFalso(CHAT_OK)
    monkeypatch.setattr(groq_client, "_get_client", lambda: falso)
    return falso


def _persona(client, make_user, email):
    headers, _ = make_user(email)
    return headers, client.get("/auth/me", headers=headers).json()["id"]


def _gastar(db_engine, user_id, n):
    """Siembra `n` solicitudes de IA exitosas de este mes a nombre de `user_id`."""
    with Session(db_engine) as session:
        session.add_all(AiUsage(user_id=user_id, tarea="chat", modelo="m", mes="2026-03", exito=True) for _ in range(n))
        session.commit()


def _chatear(client, headers):
    """True si la IA contestó; False si el cupo estaba agotado y salió el texto de respaldo."""
    r = client.post("/coach/chat", json={"mensaje": "hola"}, headers=headers)
    assert r.status_code == 200
    return r.json()["contenido"] == CHAT_OK["respuesta"]


def _plan(client, headers):
    return client.get("/me/subscription", headers=headers).json()


def _pasar_a(plan):
    def _activar(client, headers, db_engine):
        if plan == "institucional":
            with Session(db_engine) as session:
                crear_convenio(session, "ECI", "ECI-2026")
            r = client.post("/me/subscription/redeem", json={"codigo": "ECI-2026"}, headers=headers)
            assert r.status_code == 200
        elif plan != "gratis":
            assert client.put("/me/subscription", json={"plan": plan}, headers=headers).status_code == 200

    return _activar


@pytest.mark.parametrize(
    ("plan", "cupo"), [("gratis", 50), ("premium", 300), ("institucional", 300), ("familiar", 390)]
)
def test_cada_plan_se_agota_en_su_cupo(client, make_user, db_engine, groq, plan, cupo):
    headers, user_id = _persona(client, make_user, "a@t.com")
    _pasar_a(plan)(client, headers, db_engine)
    assert _plan(client, headers)["cupo_ia_mensual"] == cupo

    _gastar(db_engine, user_id, cupo - 1)
    assert _chatear(client, headers)  # la última del cupo todavía pasa
    assert not _chatear(client, headers)  # la siguiente no
    assert groq.llamadas == 1
    plan_actual = _plan(client, headers)
    assert (plan_actual["usadas"], plan_actual["restantes"]) == (cupo, 0)


def test_subir_de_plan_libera_el_cupo_al_instante(client, make_user, db_engine, groq):
    headers, user_id = _persona(client, make_user, "a@t.com")
    _gastar(db_engine, user_id, 50)
    assert not _chatear(client, headers)

    client.put("/me/subscription", json={"plan": "premium"}, headers=headers)
    assert _chatear(client, headers)


def test_el_cupo_familiar_se_comparte_entre_los_integrantes(client, make_user, db_engine, groq):
    titular, id_titular = _persona(client, make_user, "titular@t.com")
    codigo = client.put("/me/subscription", json={"plan": "familiar"}, headers=titular).json()["familia"]["codigo"]
    integrante, id_integrante = _persona(client, make_user, "integrante@t.com")
    client.post("/me/subscription/redeem", json={"codigo": codigo}, headers=integrante)
    _, id_ajeno = _persona(client, make_user, "ajeno@t.com")

    _gastar(db_engine, id_titular, 200)
    _gastar(db_engine, id_integrante, 189)  # 389 entre los dos: cada uno por separado iría de sobra
    _gastar(db_engine, id_ajeno, 500)  # quien no es de la familia no gasta de su cupo

    # Los dos ven el mismo consumo de la familia.
    assert [_plan(client, h)["usadas"] for h in (titular, integrante)] == [389, 389]
    assert _chatear(client, integrante)  # la 390
    assert not _chatear(client, titular)  # la 391: se acabó para todos
    assert not _chatear(client, integrante)
    assert groq.llamadas == 1


def test_quien_sale_de_la_familia_deja_su_consumo_y_vuelve_a_su_propio_cupo(client, make_user, db_engine, groq):
    titular, id_titular = _persona(client, make_user, "titular@t.com")
    codigo = client.put("/me/subscription", json={"plan": "familiar"}, headers=titular).json()["familia"]["codigo"]
    saliente, id_saliente = _persona(client, make_user, "saliente@t.com")
    client.post("/me/subscription/redeem", json={"codigo": codigo}, headers=saliente)
    _gastar(db_engine, id_titular, 200)
    _gastar(db_engine, id_saliente, 190)
    assert not _chatear(client, titular)  # la familia ya gastó 390

    client.put("/me/subscription", json={"plan": "premium"}, headers=saliente)

    assert _chatear(client, titular)  # sin las 190 del que se fue, a la familia le sobra cupo
    assert _plan(client, saliente)["usadas"] == 190 and _chatear(client, saliente)  # y él tiene su propio 300


def test_al_disolverse_la_familia_cada_uno_vuelve_al_cupo_de_gratis(client, make_user, db_engine, groq):
    titular, id_titular = _persona(client, make_user, "titular@t.com")
    codigo = client.put("/me/subscription", json={"plan": "familiar"}, headers=titular).json()["familia"]["codigo"]
    integrante, id_integrante = _persona(client, make_user, "integrante@t.com")
    client.post("/me/subscription/redeem", json={"codigo": codigo}, headers=integrante)
    _gastar(db_engine, id_integrante, 60)
    assert _chatear(client, integrante)  # con la familia le sobra cupo

    client.put("/me/subscription", json={"plan": "gratis"}, headers=titular)  # el titular disuelve la familia

    assert _plan(client, integrante)["plan"] == "gratis"
    assert not _chatear(client, integrante)  # 61 solicitudes y su cupo ahora es de 50


def test_el_cupo_se_reinicia_el_dia_1_a_las_0000_de_bogota(client, make_user, db_engine, groq, monkeypatch):
    """El servidor corre en UTC (Bogotá es UTC-5): el mes cambia a las 05:00 UTC, no a medianoche UTC."""
    headers, user_id = _persona(client, make_user, "a@t.com")
    _gastar(db_engine, user_id, 50)

    def fijar_reloj_utc(instante):
        monkeypatch.setattr("app.core.time._now", lambda zona: instante.astimezone(ZoneInfo(zona)))

    fijar_reloj_utc(datetime(2026, 4, 1, 4, 59, 59, tzinfo=UTC))  # 31 de marzo, 23:59:59 en Bogotá
    assert not _chatear(client, headers)
    plan = _plan(client, headers)
    assert (plan["usadas"], plan["restantes"], plan["reinicia_el"]) == (50, 0, "2026-04-01")

    fijar_reloj_utc(datetime(2026, 4, 1, 5, 0, tzinfo=UTC))  # 1 de abril, 00:00 en Bogotá
    plan = _plan(client, headers)
    assert (plan["usadas"], plan["restantes"], plan["reinicia_el"]) == (0, 50, "2026-05-01")
    assert _chatear(client, headers)
    assert groq.llamadas == 1
