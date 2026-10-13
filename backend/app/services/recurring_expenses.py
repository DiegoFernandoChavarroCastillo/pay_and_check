"""Gastos fijos: cuándo vencen, cuáles están por pagar y cómo se registran al confirmarlos.

No hay scheduler ni se registra nada solo. "Por pagar" se calcula al vuelo: el vencimiento más reciente
de cada gasto fijo que aún no tiene su gasto ni fue omitido. El recordatorio del día lo programa la app
en el teléfono.
"""

import calendar
from datetime import date, timedelta

from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select

from app.models.expense import Expense
from app.models.recurring_expense import RecurringExpense
from app.services.budget_lookup import find_budget_for_date


class RecurringError(Exception):
    """El pago no se puede registrar (no hay nada pendiente, o no hay presupuesto para esa fecha)."""


def _dia_del_mes(anio: int, mes: int, dia: int) -> date:
    """El día pedido de ese mes, o el último si el mes es más corto (el 31 en febrero es el 28 o 29)."""
    return date(anio, mes, min(dia, calendar.monthrange(anio, mes)[1]))


def vencimiento_vigente(recurrente: RecurringExpense, today: date) -> date | None:
    """El vencimiento más reciente que ya llegó (hoy incluido), o None si todavía no ha vencido ninguno
    desde `fecha_inicio`."""
    if recurrente.frecuencia == "mensual":
        dia = recurrente.dia_mes or 1
        vence = _dia_del_mes(today.year, today.month, dia)
        if vence > today:
            anio, mes = (today.year - 1, 12) if today.month == 1 else (today.year, today.month - 1)
            vence = _dia_del_mes(anio, mes, dia)
    else:
        vence = today - timedelta(days=(today.weekday() - recurrente.dia_semana) % 7)
    return vence if vence >= recurrente.fecha_inicio else None


def proximo_vencimiento(recurrente: RecurringExpense, today: date) -> date:
    """El siguiente vencimiento a partir de hoy (hoy incluido)."""
    desde = max(today, recurrente.fecha_inicio)
    if recurrente.frecuencia == "mensual":
        dia = recurrente.dia_mes or 1
        vence = _dia_del_mes(desde.year, desde.month, dia)
        if vence < desde:
            anio, mes = (desde.year + 1, 1) if desde.month == 12 else (desde.year, desde.month + 1)
            vence = _dia_del_mes(anio, mes, dia)
        return vence
    return desde + timedelta(days=(recurrente.dia_semana - desde.weekday()) % 7)


def _ya_pagado(session: Session, recurrente: RecurringExpense, fecha: date) -> bool:
    pagado = select(Expense.id).where(Expense.recurring_expense_id == recurrente.id, Expense.fecha == fecha)
    return session.exec(pagado.limit(1)).first() is not None


def vencimiento_pendiente(session: Session, recurrente: RecurringExpense, today: date) -> date | None:
    """La fecha que está por pagar, si la hay: ya venció, no se ha pagado y no se omitió."""
    if not recurrente.activo:
        return None
    fecha = vencimiento_vigente(recurrente, today)
    if fecha is None:
        return None
    if recurrente.omitido_hasta is not None and fecha <= recurrente.omitido_hasta:
        return None
    return None if _ya_pagado(session, recurrente, fecha) else fecha


def pendientes(session: Session, user_id: int, today: date) -> list[tuple[RecurringExpense, date]]:
    """Gastos fijos por pagar del usuario, del vencimiento más antiguo al más reciente."""
    recurrentes = session.exec(select(RecurringExpense).where(RecurringExpense.user_id == user_id)).all()
    por_pagar = [(r, vencimiento_pendiente(session, r, today)) for r in recurrentes]
    return sorted(((r, f) for r, f in por_pagar if f is not None), key=lambda par: par[1])


def pagar(session: Session, recurrente: RecurringExpense, today: date) -> Expense:
    """Registra como gasto el vencimiento pendiente: es lo que lo descuenta del disponible."""
    fecha = vencimiento_pendiente(session, recurrente, today)
    if fecha is None:
        raise RecurringError("Este gasto fijo no tiene un pago pendiente.")
    # El gasto va con la fecha en que tocaba; si ese día no hay presupuesto, con la de hoy.
    budget = find_budget_for_date(session, recurrente.user_id, fecha) or find_budget_for_date(
        session, recurrente.user_id, today
    )
    if budget is None:
        raise RecurringError("No tienes un presupuesto activo donde registrar este pago.")

    gasto = Expense(
        user_id=recurrente.user_id,
        budget_id=budget.id,
        category_id=recurrente.category_id,
        monto=recurrente.monto,
        descripcion=recurrente.descripcion,
        recurring_expense_id=recurrente.id,
        source="recurrente",
        fecha=fecha,
    )
    session.add(gasto)
    try:
        session.commit()
    except IntegrityError as exc:
        # Dos toques seguidos en "ya lo pagué": el primero ya lo registró.
        session.rollback()
        raise RecurringError("Este pago ya estaba registrado.") from exc
    session.refresh(gasto)
    return gasto


def omitir(session: Session, recurrente: RecurringExpense, today: date) -> None:
    """Salta el vencimiento pendiente sin registrar gasto; el siguiente volverá a avisar."""
    fecha = vencimiento_pendiente(session, recurrente, today)
    if fecha is None:
        return
    recurrente.omitido_hasta = fecha
    session.add(recurrente)
    session.commit()
