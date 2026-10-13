from datetime import date

from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session, or_, select

from app.core.time import today_for
from app.db.session import get_session
from app.deps import get_current_user
from app.models.category import Category
from app.models.expense import Expense
from app.models.user import User
from app.schemas.expense import (
    ExpenseCreate,
    ExpenseParseRequest,
    ExpenseParseResponse,
    ExpenseResponse,
    ExpenseUpdate,
    ReceiptParseRequest,
    ReceiptParseResponse,
)
from app.services.budget_lookup import find_budget_for_date
from app.services.category_lookup import validate_category_access
from app.services.groq_client import (
    ExpenseParseError,
    GroqServiceError,
    parse_expense_text,
    parse_receipt_text,
)

router = APIRouter(prefix="/expenses", tags=["expenses"])


def _categorias_disponibles(session: Session, user_id: int) -> list[Category]:
    """Mismo criterio que GET /categories: por defecto + personalizadas del usuario."""
    return session.exec(
        select(Category).where(or_(Category.owner_id.is_(None), Category.owner_id == user_id))
    ).all()


def _get_owned_expense(session: Session, user_id: int, expense_id: int) -> Expense:
    expense = session.get(Expense, expense_id)
    if expense is None or expense.user_id != user_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Gasto no encontrado.")
    return expense


@router.post("", response_model=ExpenseResponse, status_code=status.HTTP_201_CREATED)
def create_expense(
    payload: ExpenseCreate,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> Expense:
    validate_category_access(session, current_user.id, payload.category_id)

    budget = find_budget_for_date(session, current_user.id, payload.fecha)
    if budget is None:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "La fecha del gasto no cae dentro de ningún presupuesto tuyo.",
        )

    expense = Expense(
        user_id=current_user.id,
        budget_id=budget.id,
        category_id=payload.category_id,
        monto=payload.monto,
        descripcion=payload.descripcion,
        texto_original=payload.texto_original,
        source=payload.source,
        comercio=payload.comercio,
        fecha=payload.fecha,
    )
    session.add(expense)
    session.commit()
    session.refresh(expense)
    return expense


@router.get("", response_model=list[ExpenseResponse])
def list_expenses(
    category_id: int | None = None,
    fecha_desde: date | None = None,
    fecha_hasta: date | None = None,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> list[Expense]:
    query = select(Expense).where(Expense.user_id == current_user.id)
    if category_id is not None:
        query = query.where(Expense.category_id == category_id)
    if fecha_desde is not None:
        query = query.where(Expense.fecha >= fecha_desde)
    if fecha_hasta is not None:
        query = query.where(Expense.fecha <= fecha_hasta)
    query = query.order_by(Expense.fecha.desc())
    return session.exec(query).all()


@router.post("/parse", response_model=ExpenseParseResponse)
def parse_expense(
    payload: ExpenseParseRequest,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ExpenseParseResponse:
    """Parsea el texto con IA y devuelve el JSON estructurado SIN guardar el gasto."""
    categorias = _categorias_disponibles(session, current_user.id)
    try:
        data = parse_expense_text(payload.texto, [c.nombre for c in categorias], today_for(current_user))
    except ExpenseParseError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(exc)) from exc
    except GroqServiceError as exc:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, str(exc)) from exc
    return ExpenseParseResponse(**data)


@router.post("/parse-receipt", response_model=ReceiptParseResponse)
def parse_receipt(
    payload: ReceiptParseRequest,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ReceiptParseResponse:
    """Estructura el texto de un recibo (OCR hecho en el teléfono) SIN guardar
    el gasto: la app lo muestra para confirmar y luego usa POST /expenses."""
    categorias = _categorias_disponibles(session, current_user.id)
    try:
        data = parse_receipt_text(payload.texto_ocr, [c.nombre for c in categorias], today_for(current_user))
    except ExpenseParseError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(exc)) from exc
    except GroqServiceError as exc:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, str(exc)) from exc
    return ReceiptParseResponse(**data)


@router.post("/from-text", response_model=ExpenseResponse, status_code=status.HTTP_201_CREATED)
def create_expense_from_text(
    payload: ExpenseParseRequest,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> Expense:
    """Parsea el texto con IA y guarda el gasto directamente en un solo paso."""
    categorias = _categorias_disponibles(session, current_user.id)
    try:
        data = parse_expense_text(payload.texto, [c.nombre for c in categorias], today_for(current_user))
    except ExpenseParseError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(exc)) from exc
    except GroqServiceError as exc:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, str(exc)) from exc

    if data.get("tipo") == "ingreso":
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            "El texto describe un ingreso, no un gasto: regístralo como ingreso.",
        )

    budget = find_budget_for_date(session, current_user.id, data["fecha"])
    if budget is None:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "La fecha del gasto no cae dentro de ningún presupuesto tuyo.",
        )

    categoria = next(c for c in categorias if c.nombre == data["categoria"])

    expense = Expense(
        user_id=current_user.id,
        budget_id=budget.id,
        category_id=categoria.id,
        monto=data["monto"],
        descripcion=data["descripcion"],
        texto_original=payload.texto,
        source="texto",
        fecha=data["fecha"],
    )
    session.add(expense)
    session.commit()
    session.refresh(expense)
    return expense


@router.patch("/{expense_id}", response_model=ExpenseResponse)
def update_expense(
    expense_id: int,
    payload: ExpenseUpdate,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> Expense:
    expense = _get_owned_expense(session, current_user.id, expense_id)
    updates = payload.model_dump(exclude_unset=True)

    if "category_id" in updates:
        validate_category_access(session, current_user.id, updates["category_id"])

    nueva_fecha = updates.get("fecha", expense.fecha)
    if "fecha" in updates:
        # La fecha cambió: hay que re-derivar (y validar) su presupuesto.
        budget = find_budget_for_date(session, current_user.id, nueva_fecha)
        if budget is None:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                "La fecha del gasto no cae dentro de ningún presupuesto tuyo.",
            )
        expense.budget_id = budget.id

    for field, value in updates.items():
        setattr(expense, field, value)

    session.add(expense)
    session.commit()
    session.refresh(expense)
    return expense


@router.delete("/{expense_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_expense(
    expense_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> None:
    expense = _get_owned_expense(session, current_user.id, expense_id)
    session.delete(expense)
    session.commit()
