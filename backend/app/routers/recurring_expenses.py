from datetime import date

from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session, select

from app.db.session import get_session
from app.deps import get_current_user
from app.models.recurring_expense import RecurringExpense
from app.models.user import User
from app.schemas.recurring_expense import (
    RecurringExpenseCreate,
    RecurringExpenseResponse,
    RecurringExpenseUpdate,
)
from app.services.category_lookup import validate_category_access
from app.services.recurring_expenses import sync_recurring_expenses

router = APIRouter(prefix="/recurring-expenses", tags=["recurring-expenses"])


def _get_owned_recurring(session: Session, user_id: int, recurring_id: int) -> RecurringExpense:
    recurrente = session.get(RecurringExpense, recurring_id)
    if recurrente is None or recurrente.user_id != user_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Gasto fijo no encontrado.")
    return recurrente


@router.post("", response_model=RecurringExpenseResponse, status_code=status.HTTP_201_CREATED)
def create_recurring_expense(
    payload: RecurringExpenseCreate,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> RecurringExpense:
    validate_category_access(session, current_user.id, payload.category_id)

    recurrente = RecurringExpense(
        user_id=current_user.id,
        category_id=payload.category_id,
        monto=payload.monto,
        descripcion=payload.descripcion,
        dia_semana=payload.dia_semana,
        fecha_inicio=payload.fecha_inicio or date.today(),
    )
    session.add(recurrente)
    session.commit()
    session.refresh(recurrente)

    sync_recurring_expenses(session, current_user.id)
    return recurrente


@router.get("", response_model=list[RecurringExpenseResponse])
def list_recurring_expenses(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> list[RecurringExpense]:
    return session.exec(
        select(RecurringExpense).where(RecurringExpense.user_id == current_user.id)
    ).all()


@router.patch("/{recurring_id}", response_model=RecurringExpenseResponse)
def update_recurring_expense(
    recurring_id: int,
    payload: RecurringExpenseUpdate,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> RecurringExpense:
    recurrente = _get_owned_recurring(session, current_user.id, recurring_id)
    updates = payload.model_dump(exclude_unset=True)

    if "category_id" in updates:
        validate_category_access(session, current_user.id, updates["category_id"])

    for field, value in updates.items():
        setattr(recurrente, field, value)

    session.add(recurrente)
    session.commit()
    session.refresh(recurrente)
    return recurrente


@router.delete("/{recurring_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_recurring_expense(
    recurring_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> None:
    recurrente = _get_owned_recurring(session, current_user.id, recurring_id)
    session.delete(recurrente)
    session.commit()
