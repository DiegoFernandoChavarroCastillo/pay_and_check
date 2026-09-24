from datetime import date
from decimal import Decimal

from app.models.budget import Budget
from app.services.budget_calculator import calculate_budget_summary


def _budget(monto_total="100000.00", inicio=date(2026, 1, 1), fin=date(2026, 1, 10)) -> Budget:
    return Budget(id=1, owner_id=1, monto_total=Decimal(monto_total), fecha_inicio=inicio, fecha_fin=fin)


def test_presupuesto_recien_iniciado():
    budget = _budget()
    s = calculate_budget_summary(budget, Decimal("20000.00"), today=date(2026, 1, 1))
    assert s.dias_restantes == 10
    assert s.disponible_total == Decimal("80000.00")
    assert s.disponible_por_dia == Decimal("8000.00")
    assert s.disponible_por_semana == Decimal("56000.00")  # 80000 * 7 / 10


def test_presupuesto_vencido_no_divide_entre_cero():
    budget = _budget()
    s = calculate_budget_summary(budget, Decimal("20000.00"), today=date(2026, 1, 15))
    assert s.dias_restantes == 0
    assert s.disponible_por_dia == Decimal("0.00")
    assert s.disponible_por_semana == Decimal("0.00")
    # El saldo real no depende de la fecha, solo el "restante por día/semana".
    assert s.disponible_total == Decimal("80000.00")


def test_presupuesto_sin_gastos_aun():
    budget = _budget()
    s = calculate_budget_summary(budget, Decimal("0.00"), today=date(2026, 1, 5))
    assert s.gastado_total == Decimal("0.00")
    assert s.disponible_total == budget.monto_total
    assert s.dias_restantes == 6  # Jan5..Jan10 inclusive


def test_presupuesto_a_mitad_de_periodo():
    budget = _budget()
    s = calculate_budget_summary(budget, Decimal("50000.00"), today=date(2026, 1, 6))
    assert s.dias_restantes == 5  # Jan6..Jan10 inclusive
    assert s.disponible_total == Decimal("50000.00")
    assert s.disponible_por_dia == Decimal("10000.00")


def test_presupuesto_aun_no_empieza_cuenta_periodo_completo():
    budget = _budget()
    s = calculate_budget_summary(budget, Decimal("0.00"), today=date(2025, 12, 25))
    assert s.dias_restantes == 10


def test_ingresos_amplian_disponible_sin_tocar_monto_total():
    budget = _budget()
    s = calculate_budget_summary(
        budget, Decimal("20000.00"), ingresos_total=Decimal("30000.00"), today=date(2026, 1, 1)
    )
    assert s.ingresos_total == Decimal("30000.00")
    # 100000 (monto_total) + 30000 (ingresos) - 20000 (gastado) = 110000
    assert s.disponible_total == Decimal("110000.00")


def test_sin_gasto_no_hay_riesgo_ni_proyeccion():
    budget = _budget(monto_total="100000.00", inicio=date(2026, 1, 1), fin=date(2026, 3, 31))
    s = calculate_budget_summary(budget, Decimal("0.00"), today=date(2026, 1, 15))
    assert s.en_riesgo is False
    assert s.fecha_proyectada_agotamiento is None


def test_ritmo_alto_dispara_en_riesgo_con_fecha_proyectada_antes_del_fin():
    # Periodo de 90 días, pero gastando la mitad del presupuesto en los primeros 10 días.
    budget = _budget(monto_total="100000.00", inicio=date(2026, 1, 1), fin=date(2026, 3, 31))
    s = calculate_budget_summary(budget, Decimal("50000.00"), today=date(2026, 1, 10))
    assert s.en_riesgo is True
    assert s.fecha_proyectada_agotamiento is not None
    assert s.fecha_proyectada_agotamiento < budget.fecha_fin


def test_ritmo_bajo_no_dispara_en_riesgo():
    # Mismo periodo largo, pero gastando muy poco -> alcanza de sobra.
    budget = _budget(monto_total="1000000.00", inicio=date(2026, 1, 1), fin=date(2026, 3, 31))
    s = calculate_budget_summary(budget, Decimal("1000.00"), today=date(2026, 1, 10))
    assert s.en_riesgo is False
