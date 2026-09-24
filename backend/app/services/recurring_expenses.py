from datetime import date, timedelta

from sqlmodel import Session, select

from app.models.expense import Expense
from app.models.recurring_expense import RecurringExpense
from app.services.budget_lookup import find_budget_for_date


def sync_recurring_expenses(session: Session, user_id: int, today: date | None = None) -> None:
    """Genera los `Expense` de las semanas ya transcurridas para cada gasto
    fijo recurrente activo del usuario, sin duplicar los que ya existan.
    Pensado para llamarse "al vuelo" en cada lectura (GET /expenses,
    /budgets/active/summary) — no requiere un scheduler aparte."""
    today = today or date.today()
    recurrentes = session.exec(
        select(RecurringExpense)
        .where(RecurringExpense.user_id == user_id)
        .where(RecurringExpense.activo)
    ).all()

    for recurrente in recurrentes:
        _sync_una_recurrencia(session, recurrente, today)


def _sync_una_recurrencia(session: Session, recurrente: RecurringExpense, today: date) -> None:
    semana = recurrente.fecha_inicio - timedelta(days=recurrente.fecha_inicio.weekday())

    while True:
        objetivo = semana + timedelta(days=recurrente.dia_semana)
        if objetivo > today:
            break

        ya_generado = session.exec(
            select(Expense)
            .where(Expense.recurring_expense_id == recurrente.id)
            .where(Expense.fecha >= semana)
            .where(Expense.fecha < semana + timedelta(days=7))
        ).first()

        if ya_generado is None:
            budget = find_budget_for_date(session, recurrente.user_id, objetivo)
            if budget is not None:
                session.add(
                    Expense(
                        user_id=recurrente.user_id,
                        budget_id=budget.id,
                        category_id=recurrente.category_id,
                        monto=recurrente.monto,
                        descripcion=recurrente.descripcion,
                        recurring_expense_id=recurrente.id,
                        fecha=objetivo,
                    )
                )
                session.commit()
            # Si no hay presupuesto para esa semana, se omite (no se puede
            # asociar un gasto a nada) — se reintentará en el próximo sync
            # por si luego se crea un presupuesto que la cubra.

        semana += timedelta(days=7)
