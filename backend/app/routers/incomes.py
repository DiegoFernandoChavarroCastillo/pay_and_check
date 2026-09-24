from datetime import date

from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session, select

from app.db.session import get_session
from app.deps import get_current_user
from app.models.income import Income
from app.models.user import User
from app.schemas.income import IncomeCreate, IncomeResponse, IncomeUpdate
from app.services.budget_lookup import find_budget_for_date

router = APIRouter(prefix="/incomes", tags=["incomes"])


def _get_owned_income(session: Session, user_id: int, income_id: int) -> Income:
    income = session.get(Income, income_id)
    if income is None or income.user_id != user_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Ingreso no encontrado.")
    return income


@router.post("", response_model=IncomeResponse, status_code=status.HTTP_201_CREATED)
def create_income(
    payload: IncomeCreate,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> Income:
    budget = find_budget_for_date(session, current_user.id, payload.fecha)
    if budget is None:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "La fecha del ingreso no cae dentro de ningún presupuesto tuyo.",
        )

    income = Income(
        user_id=current_user.id,
        budget_id=budget.id,
        monto=payload.monto,
        descripcion=payload.descripcion,
        fecha=payload.fecha,
    )
    session.add(income)
    session.commit()
    session.refresh(income)
    return income


@router.get("", response_model=list[IncomeResponse])
def list_incomes(
    fecha_desde: date | None = None,
    fecha_hasta: date | None = None,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> list[Income]:
    query = select(Income).where(Income.user_id == current_user.id)
    if fecha_desde is not None:
        query = query.where(Income.fecha >= fecha_desde)
    if fecha_hasta is not None:
        query = query.where(Income.fecha <= fecha_hasta)
    query = query.order_by(Income.fecha.desc())
    return session.exec(query).all()


@router.patch("/{income_id}", response_model=IncomeResponse)
def update_income(
    income_id: int,
    payload: IncomeUpdate,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> Income:
    income = _get_owned_income(session, current_user.id, income_id)
    updates = payload.model_dump(exclude_unset=True)

    nueva_fecha = updates.get("fecha", income.fecha)
    if "fecha" in updates:
        budget = find_budget_for_date(session, current_user.id, nueva_fecha)
        if budget is None:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                "La fecha del ingreso no cae dentro de ningún presupuesto tuyo.",
            )
        income.budget_id = budget.id

    for field, value in updates.items():
        setattr(income, field, value)

    session.add(income)
    session.commit()
    session.refresh(income)
    return income


@router.delete("/{income_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_income(
    income_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> None:
    income = _get_owned_income(session, current_user.id, income_id)
    session.delete(income)
    session.commit()
