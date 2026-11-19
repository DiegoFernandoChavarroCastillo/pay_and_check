from decimal import ROUND_DOWN, Decimal

from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session, select

from app.core.time import today_for
from app.db.session import get_session
from app.deps import get_current_user
from app.models.expense import Expense
from app.models.receivable import Receivable
from app.models.user import User
from app.schemas.extras import ReceivableResponse, ReceivableSummary, SplitCreate, SplitResponse
from app.services.budget_lookup import find_budget_for_date
from app.services.category_lookup import validate_category_access

router = APIRouter(tags=["receivables"])


@router.post("/expenses/split", response_model=SplitResponse, status_code=status.HTTP_201_CREATED)
def dividir_gasto(
    payload: SplitCreate, session: Session = Depends(get_session), current_user: User = Depends(get_current_user)
) -> SplitResponse:
    """Una vaca: quien pagó registra como gasto solo su parte, y la de cada uno de los demás queda por cobrar.
    Las partes de los demás se redondean al peso hacia abajo; lo que sobra por redondeo va en la parte propia."""
    validate_category_access(session, current_user.id, payload.category_id)
    budget = find_budget_for_date(session, current_user.id, payload.fecha)
    if budget is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "La fecha del gasto no cae dentro de ningún presupuesto tuyo.")

    parte = (payload.monto_total / (len(payload.personas) + 1)).quantize(Decimal("1"), rounding=ROUND_DOWN)
    mi_parte = payload.monto_total - parte * len(payload.personas)
    gasto = Expense(
        user_id=current_user.id, budget_id=budget.id, category_id=payload.category_id, monto=mi_parte,
        descripcion=payload.descripcion, source="manual", fecha=payload.fecha,
    )
    session.add(gasto)
    session.flush()
    cobros = [
        Receivable(user_id=current_user.id, expense_id=gasto.id, persona=persona, descripcion=payload.descripcion,
                   monto=parte, fecha=payload.fecha)
        for persona in payload.personas
    ]
    session.add_all(cobros)
    session.commit()
    for c in cobros:
        session.refresh(c)
    return SplitResponse(
        expense_id=gasto.id, mi_parte=mi_parte, por_cobrar=[ReceivableResponse.model_validate(c) for c in cobros]
    )


@router.get("/receivables", response_model=ReceivableSummary)
def por_cobrar(
    session: Session = Depends(get_session), current_user: User = Depends(get_current_user)
) -> ReceivableSummary:
    pendientes = session.exec(
        select(Receivable)
        .where(Receivable.user_id == current_user.id, Receivable.pagado.is_(False))
        .order_by(Receivable.fecha.desc(), Receivable.id)
    ).all()
    return ReceivableSummary(
        total_pendiente=sum((r.monto for r in pendientes), Decimal("0")),
        pendientes=[ReceivableResponse.model_validate(r) for r in pendientes],
    )


@router.post("/receivables/{receivable_id}/paid", response_model=ReceivableResponse)
def marcar_pagado(
    receivable_id: int, session: Session = Depends(get_session), current_user: User = Depends(get_current_user)
) -> Receivable:
    cobro = session.get(Receivable, receivable_id)
    if cobro is None or cobro.user_id != current_user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Cobro no encontrado.")
    cobro.pagado = True
    cobro.pagado_en = today_for(current_user) if not cobro.pagado_en else cobro.pagado_en
    session.add(cobro)
    session.commit()
    session.refresh(cobro)
    return cobro


