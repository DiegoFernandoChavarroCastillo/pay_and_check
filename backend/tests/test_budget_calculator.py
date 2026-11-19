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


# --- Casos con cifras exactas (docs/reglas-calculo.md §4) -------------------
# Cada prueba compara TODAS las cifras del resumen con la fecha fija; si cambia
# una regla, hay que actualizar el documento y estas cifras a la vez.


def test_caso_1_normal_alcanza_hasta_el_fin():
    budget = _budget("1200000.00", inicio=date(2026, 11, 1), fin=date(2026, 11, 30))
    s = calculate_budget_summary(
        budget,
        Decimal("300000.00"),
        ingresos_total=Decimal("100000.00"),
        today=date(2026, 11, 11),
        apartado_total=Decimal("50000.00"),
    )
    assert s.gastado_total == Decimal("300000.00")
    assert s.ingresos_total == Decimal("100000.00")
    assert s.apartado_total == Decimal("50000.00")
    assert s.disponible_total == Decimal("950000.00")
    assert s.dias_restantes == 20
    assert s.semanas_restantes == Decimal("2.86")
    assert s.disponible_por_dia == Decimal("47500.00")
    assert s.disponible_por_semana == Decimal("332500.00")
    assert s.en_riesgo is False
    assert s.fecha_proyectada_agotamiento == date(2026, 12, 15)


def test_caso_2_se_agota_antes_del_fin():
    budget = _budget("600000.00", inicio=date(2026, 11, 1), fin=date(2026, 11, 30))
    s = calculate_budget_summary(budget, Decimal("400000.00"), today=date(2026, 11, 10))
    assert s.gastado_total == Decimal("400000.00")
    assert s.ingresos_total == Decimal("0.00")
    assert s.apartado_total == Decimal("0.00")
    assert s.disponible_total == Decimal("200000.00")
    assert s.dias_restantes == 21
    assert s.semanas_restantes == Decimal("3.00")
    assert s.disponible_por_dia == Decimal("9523.81")
    assert s.disponible_por_semana == Decimal("66666.67")
    assert s.en_riesgo is True
    assert s.fecha_proyectada_agotamiento == date(2026, 11, 15)


def test_caso_3_vencido():
    budget = _budget("500000.00", inicio=date(2026, 10, 1), fin=date(2026, 10, 31))
    s = calculate_budget_summary(
        budget, Decimal("520000.00"), ingresos_total=Decimal("30000.00"), today=date(2026, 11, 5)
    )
    assert s.gastado_total == Decimal("520000.00")
    assert s.ingresos_total == Decimal("30000.00")
    assert s.apartado_total == Decimal("0.00")
    assert s.disponible_total == Decimal("10000.00")
    assert s.dias_restantes == 0
    assert s.semanas_restantes == Decimal("0.00")
    assert s.disponible_por_dia == Decimal("0.00")
    assert s.disponible_por_semana == Decimal("0.00")
    assert s.en_riesgo is False
    # Decisión pendiente D1: hoy se devuelve una fecha aunque el periodo ya cerró.
    assert s.fecha_proyectada_agotamiento == date(2026, 11, 5)
