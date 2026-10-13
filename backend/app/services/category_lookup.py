from decimal import Decimal

from fastapi import HTTPException, status
from sqlmodel import Session, select

from app.models.category import Category, CategoryLimit


def validate_category_access(session: Session, user_id: int, category_id: int) -> None:
    """Lanza 404 si la categoría no existe o es privada de otro usuario."""
    category = session.get(Category, category_id)
    if category is None or (category.owner_id is not None and category.owner_id != user_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Categoría no encontrada.")


def limites_propios(session: Session, user_id: int) -> dict[int, Decimal]:
    """Límites que la persona puso a categorías por defecto: {category_id: límite}."""
    filas = session.exec(select(CategoryLimit).where(CategoryLimit.user_id == user_id)).all()
    return {f.category_id: f.limite for f in filas}


def limite_de(categoria: Category, propios: dict[int, Decimal]) -> Decimal | None:
    """El límite que aplica a esta persona: el suyo si la categoría es por defecto, el de la categoría si es propia."""
    return propios.get(categoria.id) if categoria.owner_id is None else categoria.limite

