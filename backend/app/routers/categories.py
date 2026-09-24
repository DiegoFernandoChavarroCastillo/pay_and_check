from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session, or_, select

from app.db.session import get_session
from app.deps import get_current_user
from app.models.category import Category
from app.models.user import User
from app.schemas.category import CategoryCreate, CategoryResponse, CategoryUpdate

router = APIRouter(prefix="/categories", tags=["categories"])


@router.get("", response_model=list[CategoryResponse])
def list_categories(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> list[Category]:
    """Categorías por defecto (owner_id nulo) + las personalizadas del usuario."""
    return session.exec(
        select(Category).where(
            or_(Category.owner_id.is_(None), Category.owner_id == current_user.id)
        )
    ).all()


@router.post("", response_model=CategoryResponse, status_code=status.HTTP_201_CREATED)
def create_category(
    payload: CategoryCreate,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> Category:
    category = Category(
        nombre=payload.nombre, owner_id=current_user.id, tipo=payload.tipo, limite=payload.limite
    )
    session.add(category)
    session.commit()
    session.refresh(category)
    return category


@router.patch("/{category_id}", response_model=CategoryResponse)
def update_category(
    category_id: int,
    payload: CategoryUpdate,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> Category:
    """Solo se pueden editar categorías propias — las por defecto (owner_id
    nulo) son un único registro compartido por TODOS los usuarios: editarlas
    cambiaría el tipo/límite para todo el mundo, no solo para quien lo pide."""
    category = session.get(Category, category_id)
    if category is None or category.owner_id != current_user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Categoría no encontrada.")

    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(category, field, value)

    session.add(category)
    session.commit()
    session.refresh(category)
    return category
