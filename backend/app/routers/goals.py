from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session, delete, select

from app.core.time import today_for
from app.db.session import get_session
from app.deps import get_current_user
from app.models.goal import Goal, GoalContribution
from app.models.user import User
from app.schemas.goal import ContributionCreate, GoalCreate, GoalResponse, GoalUpdate
from app.services.budget_lookup import get_active_budget_for_user
from app.services.budget_totals import summary_for

router = APIRouter(prefix="/goals", tags=["goals"])


def _get_owned_goal(session: Session, user_id: int, goal_id: int) -> Goal:
    goal = session.get(Goal, goal_id)
    if goal is None or goal.user_id != user_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Meta no encontrada.")
    return goal


def _aportes(session: Session, goal_id: int) -> list[GoalContribution]:
    return session.exec(
        select(GoalContribution).where(GoalContribution.goal_id == goal_id).order_by(GoalContribution.id)
    ).all()


def _a_respuesta(session: Session, goal: Goal) -> GoalResponse:
    aportes = _aportes(session, goal.id)
    aportado = sum((a.monto for a in aportes), Decimal("0"))
    progreso = min(aportado / goal.monto_objetivo, Decimal("1")).quantize(Decimal("0.0001"))
    return GoalResponse(
        id=goal.id,
        nombre=goal.nombre,
        monto_objetivo=goal.monto_objetivo,
        fecha_limite=goal.fecha_limite,
        estado=goal.estado,
        cumplida_en=goal.cumplida_en,
        aportado=aportado,
        progreso=progreso,
        aportes=aportes,
        created_at=goal.created_at,
    )


def _reevaluar_estado(session: Session, goal: Goal, today) -> None:
    """La meta está cumplida si, y solo si, lo realmente apartado alcanza el objetivo."""
    aportado = sum((a.monto for a in _aportes(session, goal.id)), Decimal("0"))
    cumplida = aportado >= goal.monto_objetivo
    if cumplida and goal.estado != "cumplida":
        goal.estado, goal.cumplida_en = "cumplida", today
    elif not cumplida and goal.estado == "cumplida":
        goal.estado, goal.cumplida_en = "activa", None
    session.add(goal)


@router.post("", response_model=GoalResponse, status_code=status.HTTP_201_CREATED)
def create_goal(
    payload: GoalCreate,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> GoalResponse:
    goal = Goal(user_id=current_user.id, **payload.model_dump())
    session.add(goal)
    session.commit()
    session.refresh(goal)
    return _a_respuesta(session, goal)


@router.get("", response_model=list[GoalResponse])
def list_goals(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> list[GoalResponse]:
    goals = session.exec(select(Goal).where(Goal.user_id == current_user.id).order_by(Goal.id)).all()
    return [_a_respuesta(session, goal) for goal in goals]


@router.patch("/{goal_id}", response_model=GoalResponse)
def update_goal(
    goal_id: int,
    payload: GoalUpdate,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> GoalResponse:
    goal = _get_owned_goal(session, current_user.id, goal_id)
    for campo, valor in payload.model_dump(exclude_unset=True).items():
        setattr(goal, campo, valor)

    # Cambiar el objetivo puede cumplir o "des-cumplir" la meta.
    _reevaluar_estado(session, goal, today_for(current_user))
    session.commit()
    session.refresh(goal)
    return _a_respuesta(session, goal)


@router.delete("/{goal_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_goal(
    goal_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> None:
    """Borra la meta y sus aportes: ese dinero vuelve a estar disponible."""
    goal = _get_owned_goal(session, current_user.id, goal_id)
    session.exec(delete(GoalContribution).where(GoalContribution.goal_id == goal.id))
    session.delete(goal)
    session.commit()


@router.post("/{goal_id}/contributions", response_model=GoalResponse, status_code=status.HTTP_201_CREATED)
def add_contribution(
    goal_id: int,
    payload: ContributionCreate,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> GoalResponse:
    """Aparta dinero del presupuesto activo hacia la meta. Solo se acepta si
    ese dinero existe: así el progreso de la meta es verificable."""
    goal = _get_owned_goal(session, current_user.id, goal_id)
    today = today_for(current_user)

    budget = get_active_budget_for_user(session, current_user.id, today)
    if budget is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Necesitas un presupuesto activo para apartar dinero.")

    disponible = summary_for(session, budget, today).disponible_total
    if payload.monto > disponible:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"Solo tienes {disponible} disponible para apartar.",
        )

    session.add(
        GoalContribution(
            goal_id=goal.id, user_id=current_user.id, budget_id=budget.id, monto=payload.monto, fecha=today
        )
    )
    session.flush()
    _reevaluar_estado(session, goal, today)
    session.commit()
    session.refresh(goal)
    return _a_respuesta(session, goal)


@router.delete("/{goal_id}/contributions/{contribution_id}", response_model=GoalResponse)
def delete_contribution(
    goal_id: int,
    contribution_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> GoalResponse:
    """Devuelve un aporte al disponible."""
    goal = _get_owned_goal(session, current_user.id, goal_id)
    aporte = session.get(GoalContribution, contribution_id)
    if aporte is None or aporte.goal_id != goal.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Aporte no encontrado.")

    session.delete(aporte)
    session.flush()
    _reevaluar_estado(session, goal, today_for(current_user))
    session.commit()
    session.refresh(goal)
    return _a_respuesta(session, goal)
