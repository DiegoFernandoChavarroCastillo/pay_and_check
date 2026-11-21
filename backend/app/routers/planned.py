from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session, select

from app.core.time import today_for
from app.db.session import get_session
from app.deps import get_current_user
from app.models.category import Category
from app.models.expense import Expense
from app.models.planned_expense import PlannedExpense
from app.models.user import User
from app.schemas.extras import PlannedExpenseCreate, PlannedExpenseResponse
from app.services import previstos
from app.services.budget_lookup import get_active_budget_for_user

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
    más de 120 días salen sin ese cálculo, y sin un presupuesto activo hoy tampoco hay con qué compararlo: la app
    oculta el recuadro en lugar de prometer que "llegas con el dinero"."""
    today = today_for(current_user)
    con_presupuesto = get_active_budget_for_user(session, current_user.id, today) is not None
    calculados = {p.gasto.id: p for p in previstos.proximos(session, current_user, today)}
    gastos = session.exec(
        select(PlannedExpense)
        .where(PlannedExpense.user_id == current_user.id, PlannedExpense.hecho.is_(False))
        .order_by(PlannedExpense.fecha)
    ).all()
    resultado = []
    for g in gastos:
        p = calculados.get(g.id) if con_presupuesto else None
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
    """"Ya lo pagué": lo marca hecho y, si hay un presupuesto activo hoy, registra el gasto (fecha de hoy,
    categoría "otros") para que descuente del disponible. Sin presupuesto solo lo marca. Marcarlo otra vez no
    duplica el gasto."""
    gasto = _propio(session, current_user, planned_id)
    if gasto.hecho:
        return
    gasto.hecho = True
    session.add(gasto)

    today = today_for(current_user)
    budget = get_active_budget_for_user(session, current_user.id, today)
    otros = session.exec(select(Category).where(Category.owner_id.is_(None), Category.nombre == "otros")).first()
    if budget is not None and otros is not None:
        session.add(
            Expense(
                user_id=current_user.id, budget_id=budget.id, category_id=otros.id, monto=gasto.monto,
                descripcion=gasto.descripcion, source="manual", fecha=today,
            )
        )  # fmt: skip
    session.commit()


@router.delete("/{planned_id}", status_code=status.HTTP_204_NO_CONTENT)
def borrar(
    planned_id: int, session: Session = Depends(get_session), current_user: User = Depends(get_current_user)
) -> None:
    session.delete(_propio(session, current_user, planned_id))
    session.commit()
