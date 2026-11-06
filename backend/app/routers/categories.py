from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session, or_, select

from app.db.session import get_session
from app.deps import get_current_user
from app.models.category import Category, CategoryLimit
from app.models.user import User
from app.schemas.category import CategoryCreate, CategoryResponse, CategoryUpdate
from app.services.category_lookup import limite_de, limites_propios

router = APIRouter(prefix="/categories", tags=["categories"])


def _respuesta(categoria: Category, propios: dict) -> CategoryResponse:
    return CategoryResponse(
        id=categoria.id,
        nombre=categoria.nombre,
        owner_id=categoria.owner_id,
        tipo=categoria.tipo,
        limite=limite_de(categoria, propios),
    )


@router.get("", response_model=list[CategoryResponse])
def list_categories(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> list[CategoryResponse]:
    """Categorías por defecto (owner_id nulo) + las personalizadas del usuario,
    cada una con el límite que esa persona le puso."""
    categorias = session.exec(
        select(Category).where(
            or_(Category.owner_id.is_(None), Category.owner_id == current_user.id)
        )
    ).all()
    propios = limites_propios(session, current_user.id)
    return [_respuesta(c, propios) for c in categorias]


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
) -> Category | CategoryResponse:
    """Las categorías propias se editan completas. Las por defecto (owner_id nulo) son un único registro
    compartido por TODOS los usuarios: de ellas cada persona solo puede fijar su propio límite."""
    category = session.get(Category, category_id)
    if category is None or (category.owner_id is not None and category.owner_id != current_user.id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Categoría no encontrada.")

    cambios = payload.model_dump(exclude_unset=True)
    if category.owner_id is None:
        # Por defecto: lo único personal es el límite, y se guarda aparte para no cambiárselo a todos.
        # Reenviar el nombre o el tipo que ya tiene no es un cambio.
        ajenos = {k: v for k, v in cambios.items() if k != "limite" and v != getattr(category, k)}
        if ajenos:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST, "De una categoría por defecto solo puedes cambiar su límite."
            )
        if "limite" in cambios:
            propio = session.exec(
                select(CategoryLimit).where(
                    CategoryLimit.user_id == current_user.id, CategoryLimit.category_id == category.id
                )
            ).first()
            if cambios["limite"] is None:
                if propio is not None:
                    session.delete(propio)
            elif propio is None:
                session.add(CategoryLimit(user_id=current_user.id, category_id=category.id, limite=cambios["limite"]))
            else:
                propio.limite = cambios["limite"]
                session.add(propio)
            session.commit()
        return _respuesta(category, limites_propios(session, current_user.id))

    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(category, field, value)

    session.add(category)
    session.commit()
    session.refresh(category)
    return category
