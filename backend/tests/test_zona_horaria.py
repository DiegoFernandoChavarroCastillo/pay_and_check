"""PS-46: el "hoy" sale de la zona horaria del usuario, nunca del reloj del servidor.

El servidor corre en UTC. A las 8 p. m. del 18 de noviembre en Bogotá ya son
la 1 a. m. del 19 en UTC: si algo usara `date.today()` del servidor, el
presupuesto que termina el 18 aparecería vencido y el cupo de hoy en 0.
"""

import inspect
from datetime import UTC, date, datetime
from zoneinfo import ZoneInfo

import pytest

from app.services import budget_calculator, budget_lookup, groq_client, weekly_report

# 2026-11-19 01:00 UTC == 2026-11-18 20:00 en Bogotá
RELOJ_SERVIDOR_UTC = datetime(2026, 11, 19, 1, 0, tzinfo=UTC)


@pytest.fixture()
def reloj_8pm_bogota(monkeypatch):
    monkeypatch.setattr(
        "app.core.time._now",
        lambda zona_horaria: RELOJ_SERVIDOR_UTC.astimezone(ZoneInfo(zona_horaria)),
    )


def test_today_for_usa_la_zona_del_usuario(reloj_8pm_bogota):
    from app.core.time import today_for
    from app.models.user import User

    assert today_for(User(zona_horaria="America/Bogota")) == date(2026, 11, 18)
    assert today_for(User(zona_horaria="UTC")) == date(2026, 11, 19)


def test_resumen_no_marca_vencido_el_ultimo_dia_a_las_8pm(client, auth_headers, reloj_8pm_bogota):
    r = client.post(
        "/budgets",
        json={"monto_total": "100000.00", "fecha_inicio": "2026-11-01", "fecha_fin": "2026-11-18"},
        headers=auth_headers,
    )
    assert r.status_code == 201, r.text

    r = client.get("/budgets/active/summary", headers=auth_headers)
    assert r.status_code == 200, r.text
    body = r.json()
    # Para la persona sigue siendo el 18: queda 1 día y todo el disponible es de hoy.
    assert body["dias_restantes"] == 1
    assert body["disponible_por_dia"] == "100000.00"


@pytest.mark.parametrize(
    ("funcion", "parametro"),
    [
        (budget_lookup.get_active_budget_for_user, "today"),
        (budget_calculator.calculate_budget_summary, "today"),
        (weekly_report.build_weekly_summary, "today"),
        (groq_client.parse_expense_text, "hoy"),
        (groq_client.parse_receipt_text, "hoy"),
    ],
)
def test_el_hoy_es_obligatorio(funcion, parametro):
    """Ningún servicio puede caer en silencio al reloj del servidor."""
    assert inspect.signature(funcion).parameters[parametro].default is inspect.Parameter.empty
