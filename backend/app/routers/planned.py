from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session, select

from app.core.time import today_for
from app.db.session import get_session
from app.deps import get_current_user
from app.models.planned_expense import PlannedExpense
from app.models.user import User
from app.schemas.extras import PlannedExpenseCreate, PlannedExpenseResponse
from app.services import previstos

router = APIRouter(prefix="/planned-expenses", tags=["planned-expenses"])


def _propio(session: Session, user: User, planned_id: int) -> PlannedExpense:
    gasto = session.get(PlannedExpense, planned_id)
    if gasto is None or gasto.user_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Gasto previsto no encontrado.")
    return gasto


@router.get("", response_model=list[PlannedExpenseResponse])
def listar(
    session: Session = Depends(get_session), current_user: User = Depends(get_current_user)
) -> list[PlannedExpenseResponse]:
    """Los gastos previstos pendientes, del más cercano al más lejano, con cuánto apartar por semana. Los de
    más de 120 días salen sin ese cálculo."""
    today = today_for(current_user)
    calculados = {p.gasto.id: p for p in previstos.proximos(session, current_user, today)}
    gastos = session.exec(
        select(PlannedExpense)
        .where(PlannedExpense.user_id == current_user.id, PlannedExpense.hecho.is_(False))
        .order_by(PlannedExpense.fecha)
    ).all()
    resultado = []
    for g in gastos:
        p = calculados.get(g.id)
        resultado.append(
            PlannedExpenseResponse(
                id=g.id, descripcion=g.descripcion, monto=g.monto, fecha=g.fecha, hecho=g.hecho,
                dias=p.dias if p else (g.fecha - today).days,
                por_semana=p.por_semana if p else None,
                margen_semanal=p.margen_semanal if p else None,
            )
        )
    return resultado


@router.post("", response_model=PlannedExpenseResponse, status_code=status.HTTP_201_CREATED)
def crear(
    payload: PlannedExpenseCreate,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> PlannedExpenseResponse:
    if payload.fecha < today_for(current_user):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "La fecha del gasto previsto ya pasó.")
    gasto = PlannedExpense(user_id=current_user.id, **payload.model_dump())
    session.add(gasto)
    session.commit()
    session.refresh(gasto)
    return PlannedExpenseResponse(**gasto.model_dump(exclude={"user_id", "created_at"}))


@router.post("/{planned_id}/done", status_code=status.HTTP_204_NO_CONTENT)
def marcar_hecho(
    planned_id: int, session: Session = Depends(get_session), current_user: User = Depends(get_current_user)
) -> None:
    gasto = _propio(session, current_user, planned_id)
    gasto.hecho = True
    session.add(gasto)
    session.commit()


@router.delete("/{planned_id}", status_code=status.HTTP_204_NO_CONTENT)
def borrar(
    planned_id: int, session: Session = Depends(get_session), current_user: User = Depends(get_current_user)
) -> None:
    session.delete(_propio(session, current_user, planned_id))
    session.commit()
