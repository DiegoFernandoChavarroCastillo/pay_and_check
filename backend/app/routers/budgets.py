from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session, func, select

from app.core.time import fmt_fecha, today_for
from app.db.session import get_session
from app.deps import get_current_user
from app.models.budget import Budget
from app.models.category import Category
from app.models.expense import Expense
from app.models.goal import Goal, GoalContribution
from app.models.user import User
from app.schemas.budget import (
    BudgetCreate,
    BudgetResponse,
    BudgetSummaryResponse,
    BudgetUpdate,
    CategoriaDesgloseResponse,
    SimulateGoalImpact,
    SimulateRequest,
    SimulateResponse,
)
from app.schemas.extras import CreditRequest, CreditResponse
from app.services import credito, simulador
from app.services.budget_lookup import get_active_budget_for_user
from app.services.budget_totals import summary_for
from app.services.category_lookup import limite_de, limites_propios

router = APIRouter(prefix="/budgets", tags=["budgets"])


def _desglose_por_categoria(session: Session, budget: Budget) -> list[CategoriaDesgloseResponse]:
    rows = session.exec(
        select(Category, func.coalesce(func.sum(Expense.monto), 0))
        .join(Expense, Expense.category_id == Category.id)
        .where(Expense.budget_id == budget.id)
        .group_by(Category.id)
    ).all()
    propios = limites_propios(session, budget.owner_id)

    desglose = []
    for categoria, gastado in rows:
        limite = limite_de(categoria, propios)
        desglose.append(
            CategoriaDesgloseResponse(
                categoria=categoria.nombre,
                tipo=categoria.tipo,
                gastado=gastado,
                limite=limite,
                excedido=limite is not None and gastado > limite,
            )
        )
    return desglose


def _validar_sin_solape(session: Session, user: User, budget: Budget) -> None:
    """Dos presupuestos con días en común dejaban ambiguo a cuál va un gasto y cuál es el "activo"
    (`find_budget_for_date` toma el más reciente). Los rangos son inclusivos en ambos extremos."""
    query = (
        select(Budget)
        .where(Budget.owner_id == user.id)
        .where(Budget.fecha_inicio <= budget.fecha_fin)
        .where(Budget.fecha_fin >= budget.fecha_inicio)
    )
    if budget.id is not None:
        query = query.where(Budget.id != budget.id)
    otro = session.exec(query).first()
    if otro is not None:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"Ya tienes un presupuesto del {fmt_fecha(otro.fecha_inicio, user.idioma, True)} al "
            f"{fmt_fecha(otro.fecha_fin, user.idioma, True)}. Edítalo o elige fechas que no se crucen con él.",
        )


@router.post("", response_model=BudgetResponse, status_code=status.HTTP_201_CREATED)
def create_budget(
    payload: BudgetCreate,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> Budget:
    _validar_sin_solape(session, current_user, Budget(owner_id=current_user.id, **payload.model_dump()))
    budget = Budget(owner_id=current_user.id, **payload.model_dump())
    session.add(budget)
    session.commit()
    session.refresh(budget)
    return budget


@router.get("", response_model=list[BudgetResponse])
def list_budgets(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> list[Budget]:
    return session.exec(
        select(Budget).where(Budget.owner_id == current_user.id).order_by(Budget.fecha_inicio.desc())
    ).all()


@router.get("/active", response_model=BudgetResponse)
def get_active_budget(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> Budget:
    budget = get_active_budget_for_user(session, current_user.id, today_for(current_user))
    if budget is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No hay un presupuesto activo.")
    return budget


@router.get("/active/summary", response_model=BudgetSummaryResponse)
def get_active_budget_summary(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> BudgetSummaryResponse:
    today = today_for(current_user)
    budget = get_active_budget_for_user(session, current_user.id, today)
    if budget is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No hay un presupuesto activo.")

    summary = summary_for(session, budget, today)
    return BudgetSummaryResponse(
        budget=budget,
        desglose_por_categoria=_desglose_por_categoria(session, budget),
        **summary.__dict__,
    )


@router.post("/active/simulate", response_model=SimulateResponse)
def simulate_purchase(
    payload: SimulateRequest,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> SimulateResponse:
    """ "¿Me alcanza?": el presupuesto como quedaría si hoy se gastara `monto`, y a cuántos días de ahorro de la
    meta activa (la primera con fecha límite) equivale. Cuenta determinista: no usa IA ni gasta cupo."""
    today = today_for(current_user)
    budget = get_active_budget_for_user(session, current_user.id, today)
    if budget is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No hay un presupuesto activo.")
    resumen = summary_for(session, budget, today)

    plan = nombre = None
    metas = session.exec(
        select(Goal)
        .where(Goal.user_id == current_user.id, Goal.estado == "activa", Goal.fecha_limite.is_not(None))
        .order_by(Goal.fecha_limite)
    ).all()
    for meta in metas:
        ahorrado = session.exec(
            select(func.coalesce(func.sum(GoalContribution.monto), 0)).where(GoalContribution.goal_id == meta.id)
        ).one()
        candidato = simulador.plan_de_meta(meta.monto_objetivo, ahorrado, meta.fecha_limite, today)
        if candidato.por_dia:
            plan, nombre = candidato, meta.nombre
            break

    sim = simulador.simular_compra(budget, resumen, payload.monto, today, plan, nombre)
    d = sim.despues
    return SimulateResponse(
        monto=sim.monto,
        alcanza=sim.alcanza,
        disponible_por_dia_antes=resumen.disponible_por_dia,
        disponible_por_dia_despues=d.disponible_por_dia,
        disponible_total_despues=d.disponible_total,
        dias_restantes=d.dias_restantes,
        en_riesgo_despues=d.en_riesgo,
        fecha_agotamiento_despues=d.fecha_proyectada_agotamiento,
        meta=SimulateGoalImpact(
            nombre=nombre, dias_equivalentes=sim.meta_dias_equivalentes, aporte_por_dia=plan.por_dia
        )
        if sim.meta_dias_equivalentes
        else None,
    )


@router.post("/simulate-credit", response_model=CreditResponse)
def simulate_credit(
    payload: CreditRequest,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> CreditResponse:
    """ "¿Me conviene este crédito?": cuota fija, costo total e intereses a partir de la tasa efectiva anual, y
    cuánto bajaría el número del día pagando la cuota. Educación con cuentas exactas: no recomienda productos."""
    c = credito.simular(payload.monto, payload.cuotas, payload.tasa_ea, payload.cargo_mensual)
    respuesta = CreditResponse(
        cuota=c.cuota, cuotas=c.cuotas, tasa_mensual=c.tasa_mensual, total_pagado=c.total_pagado,
        intereses=c.intereses, por_dia=c.por_dia,
    )
    today = today_for(current_user)
    budget = get_active_budget_for_user(session, current_user.id, today)
    if budget is not None:
        resumen = summary_for(session, budget, today)
        respuesta.disponible_por_dia = resumen.disponible_por_dia
        respuesta.disponible_por_dia_con_cuota = resumen.disponible_por_dia - c.por_dia
    return respuesta


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
    with session.no_autoflush:
        _validar_sin_solape(session, current_user, budget)

    session.add(budget)
    session.commit()
    session.refresh(budget)
    return budget
