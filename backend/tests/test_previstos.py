"""PS-122: gastos previstos acumulados (docs/reglas-calculo.md, "Gastos que vienen").

Con INICIO..FIN el presupuesto es de 280.000 y desde HOY quedan 14 días: 140.000 de disponible por semana."""

import json
import re
from datetime import date, timedelta
from decimal import Decimal
from types import SimpleNamespace

import pytest
from sqlmodel import Session, select

import app.services.groq_client as groq_client
from app.models.category import Category
from app.models.expense import Expense
from app.services.budget_lookup import get_active_budget_for_user
from app.services.budget_totals import summary_for

HOY = date(2026, 3, 30)
INICIO, FIN = date(2026, 3, 16), date(2026, 4, 12)
DISPONIBLE_SEMANA = Decimal("140000")


@pytest.fixture()
def con_presupuesto(categorias, presupuesto, fijar_hoy):
    fijar_hoy(HOY)
    presupuesto(INICIO, FIN, monto="280000.00")


def _prever(client, headers, descripcion, monto, dias):
    r = client.post(
        "/planned-expenses",
        json={"descripcion": descripcion, "monto": str(monto), "fecha": (HOY + timedelta(days=dias)).isoformat()},
        headers=headers,
    )
    assert r.status_code == 201, r.text
    return r.json()["id"]


def _lista(client, headers):
    return client.get("/planned-expenses", headers=headers).json()


def _margenes(lista):
    return [Decimal(p["margen_semanal"]) for p in lista]


# --- El acumulado ---------------------------------------------------------------


def test_dos_previstos_de_la_misma_fecha_se_acumulan_en_orden_de_creacion(client, auth_headers, con_presupuesto):
    _prever(client, auth_headers, "Libros", 140000, 28)  # 4 semanas: 35.000 por semana
    _prever(client, auth_headers, "Matrícula", 140000, 28)

    lista = _lista(client, auth_headers)

    assert [p["descripcion"] for p in lista] == ["Libros", "Matrícula"]
    assert [Decimal(p["por_semana"]) for p in lista] == [35000, 35000]
    assert _margenes(lista) == [105000, 70000]  # 140.000 − 35.000 y 140.000 − 70.000


def test_tres_previstos_de_fechas_distintas_se_acumulan_por_fecha(client, auth_headers, con_presupuesto):
    # Se crean fuera de orden: el acumulado sigue la fecha, no el orden de creación.
    _prever(client, auth_headers, "Pasajes", 350000, 35)  # 5 semanas: 70.000 por semana
    _prever(client, auth_headers, "Libros", 70000, 14)  # 2 semanas: 35.000 por semana
    _prever(client, auth_headers, "Matrícula", 140000, 28)  # 4 semanas: 35.000 por semana

    lista = _lista(client, auth_headers)

    assert [p["descripcion"] for p in lista] == ["Libros", "Matrícula", "Pasajes"]
    assert [Decimal(p["por_semana"]) for p in lista] == [35000, 35000, 70000]
    assert _margenes(lista) == [105000, 70000, 0]  # el último justo alcanza


def test_si_juntos_no_alcanzan_los_ultimos_quedan_en_negativo(client, auth_headers, con_presupuesto):
    _prever(client, auth_headers, "Matrícula", 700000, 35)  # 140.000 por semana: solo, justo alcanza
    _prever(client, auth_headers, "Libros", 70000, 14)  # 35.000 por semana

    lista = _lista(client, auth_headers)

    assert [p["descripcion"] for p in lista] == ["Libros", "Matrícula"]
    assert _margenes(lista) == [105000, -35000]  # el primero alcanza; con el segundo ya no


def test_un_previsto_solo_conserva_su_margen_de_siempre(client, auth_headers, con_presupuesto):
    _prever(client, auth_headers, "Matrícula", 700000, 35)
    assert _margenes(_lista(client, auth_headers)) == [0]


def test_total_por_semana_suma_y_dice_cuanto_queda(db_engine, client, auth_headers, con_presupuesto):
    from app.models.user import User
    from app.services import previstos

    _prever(client, auth_headers, "Libros", 70000, 14)
    _prever(client, auth_headers, "Matrícula", 210000, 28)
    with Session(db_engine) as session:
        proximos = previstos.proximos(session, session.exec(select(User)).one(), HOY)

    assert previstos.total_por_semana(proximos, DISPONIBLE_SEMANA) == (Decimal("87500"), Decimal("52500"))
    assert previstos.total_por_semana(proximos, None) == (Decimal("87500"), None)
    assert previstos.total_por_semana([], DISPONIBLE_SEMANA) == (Decimal("0"), DISPONIBLE_SEMANA)


# --- Sin presupuesto activo ----------------------------------------------------------


def test_sin_presupuesto_activo_no_se_promete_nada(client, auth_headers, fijar_hoy):
    fijar_hoy(HOY)
    _prever(client, auth_headers, "Matrícula", 700000, 35)

    [p] = _lista(client, auth_headers)

    assert (p["por_semana"], p["margen_semanal"]) == (None, None)  # la app oculta el recuadro
    assert p["dias"] == 35


def test_un_presupuesto_vencido_tampoco_cuenta_como_activo(client, auth_headers, categorias, presupuesto, fijar_hoy):
    fijar_hoy(HOY)
    presupuesto(date(2026, 2, 1), date(2026, 2, 28))
    _prever(client, auth_headers, "Matrícula", 700000, 35)

    [p] = _lista(client, auth_headers)

    assert (p["por_semana"], p["margen_semanal"]) == (None, None)


# --- "Ya lo pagué" ---------------------------------------------------------------------


def _gastos(db_engine):
    with Session(db_engine) as session:
        otros = session.exec(select(Category.id).where(Category.nombre == "otros")).one()
        return otros, list(session.exec(select(Expense)).all())


def test_ya_lo_pague_solo_lo_marca_y_no_registra_ningun_gasto(client, auth_headers, db_engine, con_presupuesto):
    """El gasto lo confirma la persona en la app (formulario prellenado): si el backend lo creaba solo y ya estaba
    registrado a mano, quedaba contado dos veces."""
    planned_id = _prever(client, auth_headers, "Libros", 70000, 14)

    for _ in range(2):  # marcarlo dos veces tampoco hace nada raro
        assert client.post(f"/planned-expenses/{planned_id}/done", headers=auth_headers).status_code == 204

    assert _gastos(db_engine)[1] == []
    assert _lista(client, auth_headers) == []  # ya no está pendiente
    with Session(db_engine) as session:
        from app.models.user import User

        user = session.exec(select(User)).one()
        presupuesto = get_active_budget_for_user(session, user.id, HOY)
        assert summary_for(session, presupuesto, HOY).disponible_total == Decimal("280000")


def test_ya_lo_pague_de_otra_persona_es_404(client, make_user, db_engine, con_presupuesto):
    ajeno, _ = make_user("ajeno@t.com")
    planned_id = _prever(client, ajeno, "Libros", 70000, 14)
    otro, _ = make_user("otro@t.com")

    assert client.post(f"/planned-expenses/{planned_id}/done", headers=otro).status_code == 404
    assert _gastos(db_engine)[1] == []


# --- El chat --------------------------------------------------------------------------


class _Groq:
    """Un "modelo" que responde con la cifra que encuentra en las "Cifras ya calculadas" del prompt."""

    def __init__(self):
        self.sistema = ""
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))

    def _create(self, *, messages, **_kwargs):
        self.sistema = messages[0]["content"]
        total = re.search(r"Total a apartar por semana para gastos que vienen: ([\d.]+)\.", self.sistema)
        respuesta = f"En total debes apartar {total.group(1)} por semana." if total else "No tengo esa cifra."
        contenido = json.dumps({"en_alcance": True, "respuesta": respuesta})
        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content=contenido))], usage=None
        )


@pytest.fixture()
def groq(monkeypatch):
    falso = _Groq()
    monkeypatch.setattr(groq_client, "_get_client", lambda: falso)
    return falso


PREGUNTA = "¿Cuánto debo apartar en total por semana?"


def test_el_chat_responde_con_la_cifra_exacta_del_total_a_apartar(client, auth_headers, con_presupuesto, groq):
    _prever(client, auth_headers, "Libros", 70000, 14)  # 35.000 por semana
    _prever(client, auth_headers, "Matrícula", 210000, 28)  # 52.500 por semana

    r = client.post("/coach/chat", json={"mensaje": PREGUNTA}, headers=auth_headers)

    assert r.status_code == 200
    assert "87.500" in r.json()["contenido"]  # 35.000 + 52.500
    assert "Total a apartar por semana para gastos que vienen: 87.500." in groq.sistema
    assert "Te queda por semana después de apartarlo: 52.500." in groq.sistema  # 140.000 − 87.500


def test_el_chat_dice_cuanto_falta_cuando_no_alcanza_sin_numeros_negativos(
    client, auth_headers, con_presupuesto, groq
):
    _prever(client, auth_headers, "Matrícula", 700000, 35)  # 140.000 por semana
    _prever(client, auth_headers, "Libros", 70000, 14)  # 35.000 por semana

    client.post("/coach/chat", json={"mensaje": PREGUNTA}, headers=auth_headers)

    assert "Total a apartar por semana para gastos que vienen: 175.000." in groq.sistema
    assert "Con tu ritmo actual te faltan 35.000 por semana para poder apartarlo todo." in groq.sistema
    assert "Te queda por semana después de apartarlo" not in groq.sistema
    assert "-35.000" not in groq.sistema


def test_el_chat_no_menciona_el_total_sin_previstos_ni_sin_presupuesto(client, auth_headers, fijar_hoy, groq):
    fijar_hoy(HOY)
    client.post("/coach/chat", json={"mensaje": PREGUNTA}, headers=auth_headers)
    assert "Total a apartar" not in groq.sistema  # ni previstos ni presupuesto

    _prever(client, auth_headers, "Matrícula", 700000, 35)
    client.post("/coach/chat", json={"mensaje": PREGUNTA}, headers=auth_headers)
    assert "Total a apartar" not in groq.sistema  # previstos, pero sin presupuesto activo


def test_el_prompt_del_chat_pide_las_cifras_mas_cercanas_si_falta_la_exacta():
    from app.services.prompts import COACH_CHAT_PROMPT

    assert "cifras más cercanas" in " ".join(COACH_CHAT_PROMPT.split())
    assert "dilo y sugiere dónde verla" not in COACH_CHAT_PROMPT
