"""Simulaciones deterministas del chat y del botón "¿Me alcanza?"."""

from datetime import date
from decimal import Decimal

from app.services import simulador as sim

HOY = date(2026, 11, 18)


def test_lee_montos_en_lenguaje_natural():
    assert sim.monto_en("quiero ahorrar 2 millones para un viaje") == Decimal("2000000")
    assert sim.monto_en("2,5 millones") == Decimal("2500000")
    assert sim.monto_en("si compro 350 mil en ropa") == Decimal("350000")
    assert sim.monto_en("un uber de 12.500") == Decimal("12500")
    assert sim.monto_en("$ 1.600.000") == Decimal("1600000")
    assert sim.monto_en("tengo que comprar 350000 hoy") == Decimal("350000")
    assert sim.monto_en("en 3 días") is None


def test_lee_fechas_limite():
    assert sim.fecha_limite_en("para un viaje en marzo", HOY) == date(2027, 3, 31)
    assert sim.fecha_limite_en("antes del 15 de diciembre", HOY) == date(2026, 12, 15)
    assert sim.fecha_limite_en("en 3 meses", HOY) == date(2027, 2, 18)
    assert sim.fecha_limite_en("en 6 semanas", HOY) == date(2026, 12, 30)
    assert sim.fecha_limite_en("lo antes posible", HOY) is None


def test_nombre_de_la_meta():
    assert sim.nombre_de_meta("quiero ahorrar 2 millones para un viaje en marzo") == "Viaje"
    assert sim.nombre_de_meta("ahorrar 2 millones para marzo") is None


def test_plan_de_meta_reparte_lo_que_falta():
    plan = sim.plan_de_meta(Decimal("2000000"), Decimal("200000"), date(2026, 12, 30), HOY)
    assert plan.falta == Decimal("1800000")
    assert plan.dias == 42
    assert plan.por_semana == Decimal("300000")
    assert plan.por_dia == Decimal("42858")  # redondeado hacia arriba: mejor sobrar que faltar


def test_plan_sin_fecha_no_inventa_ritmo():
    plan = sim.plan_de_meta(Decimal("2000000"), Decimal("0"), None, HOY)
    assert plan.por_semana is None and plan.por_dia is None


def test_intencion():
    assert sim.intencion("quiero ahorrar 2 millones para un viaje en marzo") == "meta"
    assert sim.intencion("si compro 350000 en ropa, me alcanza?") == "compra"
    assert sim.intencion("cuanto puedo gastar por semana?") is None
