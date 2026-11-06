from dataclasses import dataclass, field
from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal

from sqlmodel import Session, func, select

from app.core.time import fmt_fecha
from app.models.budget import Budget
from app.models.category import Category
from app.models.expense import Expense

CENTAVOS = Decimal("0.01")


def _redondear(valor: Decimal) -> Decimal:
    return valor.quantize(CENTAVOS, rounding=ROUND_HALF_UP)


@dataclass
class CategoriaGasto:
    categoria: str
    monto: Decimal


@dataclass
class WeeklySummary:
    semana_inicio: date
    semana_fin: date
    gasto_total_semana: Decimal
    gasto_por_categoria: list[CategoriaGasto] = field(default_factory=list)
    ritmo_esperado_semanal: Decimal = Decimal("0.00")
    diferencia_vs_ritmo: Decimal = Decimal("0.00")


def build_weekly_summary(
    session: Session, user_id: int, budget: Budget, today: date | None = None
) -> WeeklySummary:
    """Agrega (no lista transacciones) el gasto de la semana calendario (lunes a
    domingo) que contiene `today`, y lo compara contra el ritmo esperado del
    presupuesto (monto_total repartido parejo entre todas las semanas del
    periodo — no el "disponible por semana" dinámico de budget_calculator,
    que mira hacia adelante desde hoy; este es un promedio fijo de referencia).
    """
    today = today or date.today()
    semana_inicio = today - timedelta(days=today.weekday())
    semana_fin = semana_inicio + timedelta(days=6)

    rows = session.exec(
        select(Category.nombre, func.coalesce(func.sum(Expense.monto), 0))
        .join(Expense, Expense.category_id == Category.id)
        .where(Expense.user_id == user_id)
        .where(Expense.budget_id == budget.id)
        .where(Expense.fecha >= semana_inicio)
        .where(Expense.fecha <= semana_fin)
        .group_by(Category.nombre)
    ).all()

    gasto_por_categoria = sorted(
        (CategoriaGasto(categoria=nombre, monto=_redondear(Decimal(monto))) for nombre, monto in rows),
        key=lambda c: c.monto,
        reverse=True,
    )
    gasto_total_semana = _redondear(sum((c.monto for c in gasto_por_categoria), Decimal("0.00")))

    duracion_total_dias = (budget.fecha_fin - budget.fecha_inicio).days + 1
    duracion_total_semanas = Decimal(duracion_total_dias) / Decimal(7)
    ritmo_esperado_semanal = (
        _redondear(budget.monto_total / duracion_total_semanas)
        if duracion_total_semanas > 0
        else Decimal("0.00")
    )

    return WeeklySummary(
        semana_inicio=semana_inicio,
        semana_fin=semana_fin,
        gasto_total_semana=gasto_total_semana,
        gasto_por_categoria=gasto_por_categoria,
        ritmo_esperado_semanal=ritmo_esperado_semanal,
        diferencia_vs_ritmo=_redondear(gasto_total_semana - ritmo_esperado_semanal),
    )


def fmt(valor: Decimal) -> str:
    """Monto sin decimales y con punto de miles (mismo formato que `patterns.fmt`)."""
    return f"{int(valor.to_integral_value()):,}".replace(",", ".")


def resumen_de_respaldo(summary: WeeklySummary) -> str:
    """Lo que se muestra si la IA no responde o lo que redacta rompe una regla del coach."""
    if summary.diferencia_vs_ritmo <= 0:
        return (
            f"Esta semana llevas {fmt(summary.gasto_total_semana)}, por debajo de tu ritmo semanal de "
            f"{fmt(summary.ritmo_esperado_semanal)}. Vas con margen: buen momento para apartar algo a una meta."
        )
    return (
        f"Esta semana llevas {fmt(summary.gasto_total_semana)}, por encima de tu ritmo semanal de "
        f"{fmt(summary.ritmo_esperado_semanal)}. Aún hay semana para equilibrar: elige un gasto pequeño que "
        "puedas posponer."
    )


def summary_to_text(summary: WeeklySummary) -> str:
    """Texto compacto y agregado para pasarle a la IA — nunca transacciones individuales."""
    # Montos sin decimales y con punto de miles: así los repite la IA, igual que el resto de la app.
    lineas = [
        f"Semana: {fmt_fecha(summary.semana_inicio)} a {fmt_fecha(summary.semana_fin)}",
        f"Gasto total de la semana: {fmt(summary.gasto_total_semana)}",
        f"Ritmo esperado semanal del presupuesto: {fmt(summary.ritmo_esperado_semanal)}",
        f"Diferencia (gasto de la semana - ritmo esperado): {fmt(summary.diferencia_vs_ritmo)}",
        "Gasto por categoría esta semana:",
    ]
    if summary.gasto_por_categoria:
        lineas.extend(f"  - {c.categoria}: {fmt(c.monto)}" for c in summary.gasto_por_categoria)
    else:
        lineas.append("  (sin gastos esta semana)")
    return "\n".join(lineas)
