"""¿Me conviene este crédito? Cuota fija (sistema francés) a partir de la tasa efectiva anual, costo total y
cómo cambia el número del día mientras dure. Es educación financiera con cuentas exactas: no recomienda ningún
producto ni entidad."""

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal, getcontext

getcontext().prec = 28


@dataclass
class Credito:
    monto: Decimal
    cuotas: int
    tasa_ea: Decimal  # en porcentaje, ej. 28.5
    tasa_mensual: Decimal  # en porcentaje
    cuota: Decimal
    total_pagado: Decimal
    intereses: Decimal
    por_dia: Decimal  # la cuota repartida en 30 días: cuánto baja el número del día


def mensual_desde_ea(tasa_ea: Decimal) -> Decimal:
    """Tasa mensual equivalente: (1 + EA)^(1/12) − 1, en fracción."""
    return Decimal(str((1 + float(tasa_ea) / 100) ** (1 / 12) - 1))


def simular(monto: Decimal, cuotas: int, tasa_ea: Decimal, cargo_mensual: Decimal = Decimal("0")) -> Credito:
    i = mensual_desde_ea(tasa_ea)
    if i == 0:
        cuota = monto / cuotas
    else:
        cuota = monto * i / (1 - (1 + i) ** -cuotas)
    cuota = (cuota + cargo_mensual).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
    total = cuota * cuotas
    return Credito(
        monto=monto,
        cuotas=cuotas,
        tasa_ea=tasa_ea,
        tasa_mensual=(i * 100).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP),
        cuota=cuota,
        total_pagado=total,
        intereses=total - monto,
        por_dia=(cuota / 30).quantize(Decimal("1"), rounding=ROUND_HALF_UP),
    )
