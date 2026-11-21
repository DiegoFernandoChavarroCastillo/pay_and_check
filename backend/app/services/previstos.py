"""Gastos grandes previstos (matrícula, libros, pasajes de vacaciones…): "decidir antes" llevado al semestre.
Todo es determinista: cuánto apartar por semana para llegar con el dinero y si el ritmo actual lo deja."""

from dataclasses import dataclass
from datetime import date
from decimal import ROUND_CEILING, Decimal

from sqlmodel import Session, select

from app.models.planned_expense import PlannedExpense
from app.models.user import User
from app.services.budget_lookup import get_active_budget_for_user
from app.services.budget_totals import summary_for

# Hasta cuántos días hacia adelante se avisa.
HORIZONTE_DIAS = 120


@dataclass
class Previsto:
    gasto: PlannedExpense
    dias: int
    por_semana: Decimal
    # Lo que se puede gastar por semana hoy menos lo que hay que apartar para ESTE gasto y los que vienen antes
    # (acumulado por fecha). Si es negativo, al ritmo actual no alcanza para separar todo ese dinero; los últimos
    # de la lista son los que quedan en negativo.
    margen_semanal: Decimal | None


def _por_semana(monto: Decimal, dias: int) -> Decimal:
    semanas = max(Decimal(dias) / Decimal(7), Decimal(1))
    return (monto / semanas).quantize(Decimal("1"), rounding=ROUND_CEILING)


def proximos(session: Session, user: User, today: date) -> list[Previsto]:
    """Los previstos pendientes dentro del horizonte, por fecha (y, a igual fecha, en el orden en que se
    crearon). Cada margen descuenta lo acumulado: se supone que todos se van apartando a la vez, así que para
    los últimos es una cota conservadora (docs/reglas-calculo.md, "Gastos que vienen")."""
    gastos = session.exec(
        select(PlannedExpense)
        .where(PlannedExpense.user_id == user.id)
        .where(PlannedExpense.hecho.is_(False))
        .where(PlannedExpense.fecha >= today)
        .order_by(PlannedExpense.fecha, PlannedExpense.id)
    ).all()
    budget = get_active_budget_for_user(session, user.id, today)
    disponible_semana = summary_for(session, budget, today).disponible_por_semana if budget else None
    resultado = []
    acumulado = Decimal("0")
    for g in gastos:
        dias = (g.fecha - today).days
        if dias > HORIZONTE_DIAS:
            continue
        por_semana = _por_semana(g.monto, dias)
        acumulado += por_semana
        margen = disponible_semana - acumulado if disponible_semana is not None else None
        resultado.append(Previsto(g, dias, por_semana, margen))
    return resultado


def total_por_semana(
    previstos: list[Previsto], disponible_semana: Decimal | None
) -> tuple[Decimal, Decimal | None]:
    """Cuánto apartar por semana para todos los previstos juntos, y lo que queda por semana después de apartarlo
    (None si no hay un disponible con el que compararlo). Negativo: no alcanza."""
    total = sum((p.por_semana for p in previstos), Decimal("0"))
    return total, (disponible_semana - total if disponible_semana is not None else None)
