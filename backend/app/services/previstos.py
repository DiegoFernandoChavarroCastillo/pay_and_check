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
    # Lo que se puede gastar por semana hoy menos lo que hay que apartar: si es negativo, al ritmo actual no
    # alcanza para separar ese dinero.
    margen_semanal: Decimal | None


def _por_semana(monto: Decimal, dias: int) -> Decimal:
    semanas = max(Decimal(dias) / Decimal(7), Decimal(1))
    return (monto / semanas).quantize(Decimal("1"), rounding=ROUND_CEILING)


def proximos(session: Session, user: User, today: date) -> list[Previsto]:
    gastos = session.exec(
        select(PlannedExpense)
        .where(PlannedExpense.user_id == user.id)
        .where(PlannedExpense.hecho.is_(False))
        .where(PlannedExpense.fecha >= today)
        .order_by(PlannedExpense.fecha)
    ).all()
    budget = get_active_budget_for_user(session, user.id, today)
    disponible_semana = summary_for(session, budget, today).disponible_por_semana if budget else None
    resultado = []
    for g in gastos:
        dias = (g.fecha - today).days
        if dias > HORIZONTE_DIAS:
            continue
        por_semana = _por_semana(g.monto, dias)
        margen = disponible_semana - por_semana if disponible_semana is not None else None
        resultado.append(Previsto(g, dias, por_semana, margen))
    return resultado
