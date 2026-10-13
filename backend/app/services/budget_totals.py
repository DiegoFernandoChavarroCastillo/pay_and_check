from datetime import date
from decimal import Decimal

from sqlmodel import Session, func, select

from app.models.budget import Budget
from app.models.expense import Expense
from app.models.goal import GoalContribution
from app.models.income import Income
from app.services.budget_calculator import BudgetSummary, calculate_budget_summary


def _suma(session: Session, columna, *condiciones) -> Decimal:
    return Decimal(session.exec(select(func.coalesce(func.sum(columna), 0)).where(*condiciones)).one())


def summary_for(session: Session, budget: Budget, today: date) -> BudgetSummary:
    """Resumen de un presupuesto con sus totales reales: gastado, ingresos y
    lo apartado hacia metas de ahorro."""
    return calculate_budget_summary(
        budget,
        gastado_total=_suma(session, Expense.monto, Expense.budget_id == budget.id),
        ingresos_total=_suma(session, Income.monto, Income.budget_id == budget.id),
        today=today,
        apartado_total=_suma(session, GoalContribution.monto, GoalContribution.budget_id == budget.id),
    )


def gasto_entre(
    session: Session, user_id: int, desde: date, hasta: date, category_id: int | None = None
) -> Decimal:
    """Total gastado por el usuario entre dos fechas (ambas incluidas)."""
    condiciones = [Expense.user_id == user_id, Expense.fecha >= desde, Expense.fecha <= hasta]
    if category_id is not None:
        condiciones.append(Expense.category_id == category_id)
    return _suma(session, Expense.monto, *condiciones)


def presupuesto_prorrateado(session: Session, user_id: int, desde: date, hasta: date) -> Decimal:
    """Cuánto dinero "le tocaba" al usuario entre dos fechas: la parte
    proporcional de cada presupuesto que se solapa con el rango, más los
    ingresos recibidos en él."""
    total = Decimal("0")
    budgets = session.exec(
        select(Budget)
        .where(Budget.owner_id == user_id)
        .where(Budget.fecha_inicio <= hasta)
        .where(Budget.fecha_fin >= desde)
    ).all()
    for budget in budgets:
        dias_solapados = (min(hasta, budget.fecha_fin) - max(desde, budget.fecha_inicio)).days + 1
        dias_presupuesto = (budget.fecha_fin - budget.fecha_inicio).days + 1
        total += budget.monto_total * dias_solapados / dias_presupuesto

    total += _suma(
        session, Income.monto, Income.user_id == user_id, Income.fecha >= desde, Income.fecha <= hasta
    )
    return total


def ratio_ahorro(session: Session, user_id: int, desde: date, hasta: date) -> Decimal | None:
    """`(ingresos - gastos) / ingresos` del rango, con el presupuesto
    prorrateado como ingreso. None si no hay presupuesto que cubra el rango o
    si no hubo ningún gasto: un periodo sin registros no es "ahorro del 100 %",
    es un periodo sin datos, y compararse contra él daría mejoras falsas."""
    disponible = presupuesto_prorrateado(session, user_id, desde, hasta)
    gastado = gasto_entre(session, user_id, desde, hasta)
    if disponible <= 0 or gastado <= 0:
        return None
    return ((disponible - gastado) / disponible).quantize(Decimal("0.0001"))
