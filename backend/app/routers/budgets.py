from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session, func, select

from app.db.session import get_session
from app.deps import get_current_user
from app.models.budget import Budget
from app.models.category import Category
from app.models.expense import Expense
from app.models.income import Income
from app.models.user import User
from app.schemas.budget import (
    BudgetCreate,
    BudgetResponse,
    BudgetSummaryResponse,
    BudgetUpdate,
    CategoriaDesgloseResponse,
)
from app.services.budget_calculator import calculate_budget_summary
from app.services.budget_lookup import get_active_budget_for_user
from app.services.recurring_expenses import sync_recurring_expenses

router = APIRouter(prefix="/budgets", tags=["budgets"])


def _desglose_por_categoria(session: Session, budget: Budget) -> list[CategoriaDesgloseResponse]:
    rows = session.exec(
        select(Category.nombre, Category.tipo, Category.limite, func.coalesce(func.sum(Expense.monto), 0))
        .join(Expense, Expense.category_id == Category.id)
        .where(Expense.budget_id == budget.id)
        .group_by(Category.nombre, Category.tipo, Category.limite)
    ).all()

    return [
        CategoriaDesgloseResponse(
            categoria=nombre,
            tipo=tipo,
            gastado=gastado,
            limite=limite,
            excedido=limite is not None and gastado > limite,
        )
        for nombre, tipo, limite, gastado in rows
    ]


@router.post("", response_model=BudgetResponse, status_code=status.HTTP_201_CREATED)
def create_budget(
    payload: BudgetCreate,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> Budget:
    budget = Budget(owner_id=current_user.id, **payload.model_dump())
    session.add(budget)
    session.commit()
    session.refresh(budget)
    return budget


@router.get("/active", response_model=BudgetResponse)
def get_active_budget(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> Budget:
    budget = get_active_budget_for_user(session, current_user.id)
    if budget is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No hay un presupuesto activo.")
    return budget


@router.get("/active/summary", response_model=BudgetSummaryResponse)
def get_active_budget_summary(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> BudgetSummaryResponse:
    sync_recurring_expenses(session, current_user.id)
    budget = get_active_budget_for_user(session, current_user.id)
    if budget is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No hay un presupuesto activo.")

    gastado_total = session.exec(
        select(func.coalesce(func.sum(Expense.monto), 0)).where(Expense.budget_id == budget.id)
    ).one()
    ingresos_total = session.exec(
        select(func.coalesce(func.sum(Income.monto), 0)).where(Income.budget_id == budget.id)
    ).one()

    summary = calculate_budget_summary(budget, gastado_total, ingresos_total)
    return BudgetSummaryResponse(
        budget=budget,
        desglose_por_categoria=_desglose_por_categoria(session, budget),
        **summary.__dict__,
    )


@router.patch("/{budget_id}", response_model=BudgetResponse)
def update_budget(
    budget_id: int,
    payload: BudgetUpdate,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> Budget:
    budget = session.get(Budget, budget_id)
    if budget is None or budget.owner_id != current_user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Presupuesto no encontrado.")

    updates = payload.model_dump(exclude_unset=True)
    for field, value in updates.items():
        setattr(budget, field, value)

    if budget.fecha_fin <= budget.fecha_inicio:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "fecha_fin debe ser posterior a fecha_inicio.")

    session.add(budget)
    session.commit()
    session.refresh(budget)
    return budget
