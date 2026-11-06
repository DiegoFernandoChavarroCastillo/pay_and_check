from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session, select

from app.core.time import today_for
from app.db.session import get_session
from app.deps import get_current_user
from app.models.expense import Expense
from app.models.recurring_expense import RecurringExpense
from app.models.user import User
from app.schemas.expense import ExpenseResponse
from app.schemas.recurring_expense import (
    PendingPaymentResponse,
    RecurringExpenseCreate,
    RecurringExpenseResponse,
    RecurringExpenseUpdate,
)
from app.services import recurring_expenses as servicio
from app.services.category_lookup import validate_category_access

router = APIRouter(prefix="/recurring-expenses", tags=["recurring-expenses"])


def _get_owned_recurring(session: Session, user_id: int, recurring_id: int) -> RecurringExpense:
    recurrente = session.get(RecurringExpense, recurring_id)
    if recurrente is None or recurrente.user_id != user_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Gasto fijo no encontrado.")
    return recurrente


def _respuesta(session: Session, recurrente: RecurringExpense, today) -> RecurringExpenseResponse:
    pendiente = servicio.vencimiento_pendiente(session, recurrente, today)
    proximo = servicio.proximo_vencimiento(recurrente, today)
    # Si el de hoy ya quedó resuelto (pagado u omitido), el próximo es el del siguiente ciclo.
    if proximo == today and pendiente is None and servicio.vencimiento_vigente(recurrente, today) == today:
        proximo = servicio.proximo_vencimiento(recurrente, today + timedelta(days=1))
    return RecurringExpenseResponse(
        **recurrente.model_dump(exclude={"user_id", "omitido_hasta"}),
        proximo_vencimiento=proximo,
        pendiente_desde=pendiente,
    )


@router.post("", response_model=RecurringExpenseResponse, status_code=status.HTTP_201_CREATED)
def create_recurring_expense(
    payload: RecurringExpenseCreate,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> RecurringExpenseResponse:
    validate_category_access(session, current_user.id, payload.category_id)
    today = today_for(current_user)

    recurrente = RecurringExpense(
        user_id=current_user.id,
        category_id=payload.category_id,
        monto=payload.monto,
        descripcion=payload.descripcion,
        frecuencia=payload.frecuencia,
        dia_semana=payload.dia_semana or 0,
        dia_mes=payload.dia_mes if payload.frecuencia == "mensual" else None,
        fecha_inicio=payload.fecha_inicio or today,
    )
    session.add(recurrente)
    session.commit()
    session.refresh(recurrente)
    return _respuesta(session, recurrente, today)


@router.get("", response_model=list[RecurringExpenseResponse])
def list_recurring_expenses(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> list[RecurringExpenseResponse]:
    today = today_for(current_user)
    recurrentes = session.exec(select(RecurringExpense).where(RecurringExpense.user_id == current_user.id)).all()
    return [_respuesta(session, r, today) for r in recurrentes]


@router.get("/pending", response_model=list[PendingPaymentResponse])
def list_pending_payments(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> list[PendingPaymentResponse]:
    """Gastos fijos que ya vencieron y esperan confirmación."""
    return [
        PendingPaymentResponse(
            recurring_id=r.id, category_id=r.category_id, descripcion=r.descripcion, monto=r.monto, fecha=fecha
        )
        for r, fecha in servicio.pendientes(session, current_user.id, today_for(current_user))
    ]


@router.post("/{recurring_id}/pay", response_model=ExpenseResponse, status_code=status.HTTP_201_CREATED)
def pay_recurring_expense(
    recurring_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> Expense:
    """"Ya lo pagué": registra el gasto del vencimiento pendiente y lo descuenta del disponible."""
    recurrente = _get_owned_recurring(session, current_user.id, recurring_id)
    try:
        return servicio.pagar(session, recurrente, today_for(current_user))
    except servicio.RecurringError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc


@router.post("/{recurring_id}/skip", status_code=status.HTTP_204_NO_CONTENT)
def skip_recurring_expense(
    recurring_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> None:
    """Salta este vencimiento sin registrar gasto (este mes no hubo que pagarlo)."""
    recurrente = _get_owned_recurring(session, current_user.id, recurring_id)
    servicio.omitir(session, recurrente, today_for(current_user))


@router.patch("/{recurring_id}", response_model=RecurringExpenseResponse)
def update_recurring_expense(
    recurring_id: int,
    payload: RecurringExpenseUpdate,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> RecurringExpenseResponse:
    recurrente = _get_owned_recurring(session, current_user.id, recurring_id)
    updates = payload.model_dump(exclude_unset=True)

    if "category_id" in updates:
        validate_category_access(session, current_user.id, updates["category_id"])

    for field, value in updates.items():
        setattr(recurrente, field, value)

    session.add(recurrente)
    session.commit()
    session.refresh(recurrente)
    return _respuesta(session, recurrente, today_for(current_user))


@router.delete("/{recurring_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_recurring_expense(
    recurring_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> None:
    recurrente = _get_owned_recurring(session, current_user.id, recurring_id)
    session.delete(recurrente)
    session.commit()
