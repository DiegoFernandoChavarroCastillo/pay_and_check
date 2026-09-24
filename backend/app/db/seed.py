from sqlmodel import Session, select

from app.db.session import engine
from app.models.category import Category

DEFAULT_CATEGORIES = ["comida", "transporte", "entretenimiento", "salud", "servicios", "otros"]


def seed_default_categories(session: Session) -> None:
    """Inserta las categorías por defecto (owner_id nulo) si no existen ya."""
    existing = set(
        session.exec(select(Category.nombre).where(Category.owner_id.is_(None))).all()
    )
    for nombre in DEFAULT_CATEGORIES:
        if nombre not in existing:
            session.add(Category(nombre=nombre, owner_id=None))
    session.commit()


def main() -> None:
    with Session(engine) as session:
        seed_default_categories(session)
    print("Categorías por defecto sembradas.")


if __name__ == "__main__":
    main()
