"""Planes de las personas (docs/planes.md). Sin fila de suscripción equivale a Gratis. La familia vive en
`users.group_id`; quien la activó es el titular y, si se va, la familia se disuelve.

Las funciones no hacen commit: lo hace quien las llama."""

from sqlmodel import Session, select

from app.models.group import Group
from app.models.plan import LicenseCode, Subscription
from app.models.user import User


def suscripcion_de(session: Session, user: User) -> Subscription | None:
    return session.exec(select(Subscription).where(Subscription.user_id == user.id)).first()


def _disolver_familia(session: Session, group_id: int) -> None:
    """Todos los integrantes vuelven a Gratis y el grupo y sus códigos desaparecen. Los flush van en el orden
    de las llaves foráneas: integrantes, suscripciones, códigos y por último el grupo."""
    integrantes = session.exec(select(User).where(User.group_id == group_id)).all()
    for integrante in integrantes:
        integrante.group_id = None
        session.add(integrante)
    session.flush()

    ids = [integrante.id for integrante in integrantes]
    for suscripcion in session.exec(select(Subscription).where(Subscription.user_id.in_(ids))).all():
        session.delete(suscripcion)
    session.flush()

    for codigo in session.exec(select(LicenseCode).where(LicenseCode.group_id == group_id)).all():
        session.delete(codigo)
    session.flush()

    grupo = session.get(Group, group_id)
    if grupo is not None:
        session.delete(grupo)
    session.flush()


def salir_del_plan(session: Session, user: User) -> None:
    """Deja a la persona sin plan de pago (Gratis). Si es el titular de una familia, la disuelve; si es un
    integrante, solo sale. Sirve para cambiar de plan y para borrar la cuenta."""
    suscripcion = suscripcion_de(session, user)
    if suscripcion is not None and suscripcion.es_titular and user.group_id is not None:
        _disolver_familia(session, user.group_id)
        return

    if user.group_id is not None:
        user.group_id = None
        session.add(user)
    if suscripcion is not None:
        session.delete(suscripcion)
    session.flush()
