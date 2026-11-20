from datetime import date

from sqlmodel import Session, select

from app.models.budget import Budget


def get_active_budget_for_user(session: Session, user_id: int, today: date) -> Budget | None:
    """El presupuesto del usuario cuyo rango de fechas incluye `today`.

    `today` es obligatorio y debe ser el "hoy" del usuario (`today_for(user)`):
    el reloj del servidor está en UTC y a las 7 p. m. en Bogotá ya es mañana."""
    return find_budget_for_date(session, user_id, today)


def find_budget_for_date(session: Session, user_id: int, fecha: date) -> Budget | None:
    """El presupuesto del usuario cuyo rango de fechas contiene `fecha` (no
    necesariamente hoy) — permite registrar gastos/ingresos atrasados dentro
    de un presupuesto histórico."""
    return session.exec(
        select(Budget)
        .where(Budget.owner_id == user_id)
        .where(Budget.fecha_inicio <= fecha)
        .where(Budget.fecha_fin >= fecha)
        .order_by(Budget.created_at.desc())
    ).first()
