from dataclasses import dataclass
from datetime import date, timedelta
from decimal import ROUND_DOWN, ROUND_HALF_UP, Decimal

from app.models.budget import Budget

CENTAVOS = Decimal("0.01")
# Días mínimos sobre los que se mide el ritmo de gasto para proyectar el agotamiento.
VENTANA_MINIMA_RITMO = 7


@dataclass
class BudgetSummary:
    gastado_total: Decimal
    ingresos_total: Decimal
    apartado_total: Decimal
    disponible_total: Decimal
    dias_restantes: int
    semanas_restantes: Decimal
    disponible_por_dia: Decimal
    disponible_por_semana: Decimal
    en_riesgo: bool
    fecha_proyectada_agotamiento: date | None


def _redondear(valor: Decimal) -> Decimal:
    return valor.quantize(CENTAVOS, rounding=ROUND_HALF_UP)


def calculate_budget_summary(
    budget: Budget,
    gastado_total: Decimal,
    ingresos_total: Decimal = Decimal("0"),
    *,
    today: date,
    apartado_total: Decimal = Decimal("0"),
    gasto_fijo_total: Decimal = Decimal("0"),
) -> BudgetSummary:
    """Calcula gastado/disponible total y por día/semana para un presupuesto.

    - `disponible_total` = monto_total + ingresos_total - gastado_total - apartado_total
      (los ingresos amplían el disponible sin tocar el monto_total original; lo
      apartado hacia metas de ahorro deja de estar disponible para gastar).
    - Si `today` es posterior a `fecha_fin`, el presupuesto está vencido:
      0 días/semanas restantes y 0 disponible por día/semana (para no dividir
      entre cero), pero `disponible_total` sigue reflejando el saldo real.
    - Si `today` es anterior a `fecha_inicio` (aún no empieza), se cuenta el
      periodo completo como restante.
    - `en_riesgo`/`fecha_proyectada_agotamiento` (Fase 11): proyecta, al ritmo
      real de gasto desde `fecha_inicio` hasta hoy, si el dinero alcanza hasta
      `fecha_fin`.
    """
    disponible_total = budget.monto_total + ingresos_total - gastado_total - apartado_total

    if today > budget.fecha_fin:
        dias_restantes = 0
    else:
        inicio_efectivo = max(today, budget.fecha_inicio)
        dias_restantes = (budget.fecha_fin - inicio_efectivo).days + 1

    semanas_restantes = Decimal(dias_restantes) / Decimal(7)

    disponible_por_dia = (
        _redondear(disponible_total / dias_restantes) if dias_restantes > 0 else Decimal("0.00")
    )
    disponible_por_semana = (
        _redondear(disponible_total / semanas_restantes)
        if semanas_restantes > 0
        else Decimal("0.00")
    )

    # Los gastos fijos programados (arriendo, celular) se pagan una vez: no son ritmo diario. Sin esto, el
    # arriendo del día 1 hacía creer que el dinero se acababa en una semana.
    en_riesgo, fecha_proyectada = _proyectar_agotamiento(
        budget, max(gastado_total - gasto_fijo_total, Decimal("0")), disponible_total, today
    )

    return BudgetSummary(
        gastado_total=_redondear(gastado_total),
        ingresos_total=_redondear(ingresos_total),
        apartado_total=_redondear(apartado_total),
        disponible_total=_redondear(disponible_total),
        dias_restantes=dias_restantes,
        semanas_restantes=semanas_restantes.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP),
        disponible_por_dia=disponible_por_dia,
        disponible_por_semana=disponible_por_semana,
        en_riesgo=en_riesgo,
        fecha_proyectada_agotamiento=fecha_proyectada,
    )


def _proyectar_agotamiento(
    budget: Budget, gastado_total: Decimal, disponible_total: Decimal, today: date
) -> tuple[bool, date | None]:
    referencia = min(today, budget.fecha_fin)
    if referencia < budget.fecha_inicio:
        return False, None  # el presupuesto aún no empieza

    dias_transcurridos = max((referencia - budget.fecha_inicio).days + 1, 1)
    # Con uno o dos días de datos, una sola compra grande se extrapola a todo el periodo y dispara una alarma
    # falsa ("se acaba el 28 nov" el día que empezó el presupuesto). El ritmo se mide sobre al menos una
    # semana (o el periodo entero si es más corto). Si el gasto ya pasó del total, igual sale en riesgo
    # porque el disponible es negativo.
    periodo = (budget.fecha_fin - budget.fecha_inicio).days + 1
    ventana = max(dias_transcurridos, min(VENTANA_MINIMA_RITMO, periodo))
    ritmo_diario_real = gastado_total / ventana

    if ritmo_diario_real <= 0:
        return False, None  # sin gasto no hay ritmo que proyectar

    dias_que_alcanza = disponible_total / ritmo_diario_real
    dias_que_alcanza_int = int(dias_que_alcanza.to_integral_value(rounding=ROUND_DOWN))
    fecha_proyectada = today + timedelta(days=dias_que_alcanza_int)

    return fecha_proyectada < budget.fecha_fin, fecha_proyectada
