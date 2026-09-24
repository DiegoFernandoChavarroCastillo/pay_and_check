from fastapi import HTTPException, status
from sqlmodel import Session

from app.models.category import Category


def validate_category_access(session: Session, user_id: int, category_id: int) -> None:
    """Lanza 404 si la categoría no existe o es privada de otro usuario."""
    category = session.get(Category, category_id)
    if category is None or (category.owner_id is not None and category.owner_id != user_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Categoría no encontrada.")
