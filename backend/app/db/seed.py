from sqlmodel import Session, select

from app.db.session import engine
from app.models.category import Category

# Fijo = gasto que ocurre sí o sí; opcional = discrecional. Los retos de "días sin gasto opcional"
# solo miran los opcionales: un pasaje de bus o una factura no rompen el día.
DEFAULT_CATEGORIES = {
    "comida": "opcional",
    "transporte": "fijo",
    "entretenimiento": "opcional",
    "salud": "fijo",
    "servicios": "fijo",
    "otros": "opcional",
}


def seed_default_categories(session: Session) -> None:
    """Inserta las categorías por defecto (owner_id nulo) si no existen ya."""
    existing = set(
        session.exec(select(Category.nombre).where(Category.owner_id.is_(None))).all()
    )
    for nombre, tipo in DEFAULT_CATEGORIES.items():
        if nombre not in existing:
            session.add(Category(nombre=nombre, owner_id=None, tipo=tipo))
    session.commit()


def main() -> None:
    with Session(engine) as session:
        seed_default_categories(session)
    print("Categorías por defecto sembradas.")


if __name__ == "__main__":
    main()
