"""Planes de las personas (docs/planes.md). Sin fila de suscripción equivale a Gratis. La familia vive en
`users.group_id`; quien la activó es el titular y, si se va, la familia se disuelve.

Las funciones no hacen commit: lo hace quien las llama."""

import secrets
from dataclasses import dataclass
from datetime import date

from sqlmodel import Session, func, select

from app.models.group import Group
from app.models.plan import LicenseCode, Organization, Subscription
from app.models.user import User

MAX_INTEGRANTES_FAMILIA = 3


@dataclass(frozen=True)
class Plan:
    codigo: str
    precio_cop: int  # con IVA, por mes; el institucional es por estudiante activo
    cupo_ia_mensual: int
    compartido: bool  # el cupo se reparte entre los integrantes
    paga: str  # nadie | universidad | persona | familia
    estado_demo: str  # real | codigo (se activa con un código) | simulado (sin cobro real)
    max_integrantes: int | None = None


CATALOGO = {
    plan.codigo: plan
    for plan in (
        Plan("gratis", 0, 50, False, "nadie", "real"),
        Plan("institucional", 4_998, 300, False, "universidad", "codigo"),
        Plan("premium", 9_990, 300, False, "persona", "simulado"),
        Plan("familiar", 19_990, 390, True, "familia", "simulado", MAX_INTEGRANTES_FAMILIA),
    )
}
CUPOS = {codigo: plan.cupo_ia_mensual for codigo, plan in CATALOGO.items()}


class PlanError(Exception):
    """Un cambio de plan o un canje que no se puede hacer; el mensaje es para la persona."""


class CodigoNoEncontrado(PlanError):
    pass


def suscripcion_de(session: Session, user: User) -> Subscription | None:
    return session.exec(select(Subscription).where(Subscription.user_id == user.id)).first()


def plan_de(session: Session, user: User) -> str:
    """El plan de la persona; sin suscripción es Gratis."""
    suscripcion = suscripcion_de(session, user)
    return suscripcion.plan if suscripcion is not None else "gratis"


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


def _codigo_familiar(session: Session) -> str:
    while True:
        codigo = "FAM-" + secrets.token_hex(3).upper()
        if session.exec(select(LicenseCode).where(LicenseCode.codigo == codigo)).first() is None:
            return codigo


def _integrantes(session: Session, group_id: int) -> int:
    return session.exec(select(func.count()).select_from(User).where(User.group_id == group_id)).one()


def datos_de_familia(session: Session, user: User) -> tuple[str, int] | None:
    """(código familiar, integrantes) de la familia de la persona, o None si no está en una."""
    if user.group_id is None:
        return None
    codigo = session.exec(
        select(LicenseCode).where(LicenseCode.group_id == user.group_id).where(LicenseCode.tipo == "familiar")
    ).first()
    return (codigo.codigo, _integrantes(session, user.group_id)) if codigo is not None else None


def cambiar_plan(session: Session, user: User, plan: str) -> None:
    """Cambio simulado, sin pasarela de pago. Institucional no se pide: se activa con un código de convenio."""
    if plan == "institucional":
        raise PlanError("El plan Institucional se activa con un código de convenio.")

    suscripcion = suscripcion_de(session, user)
    actual = suscripcion.plan if suscripcion is not None else "gratis"
    if plan == actual:
        if plan == "familiar" and not suscripcion.es_titular:
            raise PlanError("Ya perteneces a una familia: para crear la tuya, sal primero de esa.")
        return

    salir_del_plan(session, user)
    if plan == "premium":
        session.add(Subscription(user_id=user.id, plan="premium"))
    elif plan == "familiar":
        grupo = Group(nombre=f"Familia de {user.nombre}"[:80])
        session.add(grupo)
        session.flush()
        user.group_id = grupo.id
        session.add(user)
        session.add(Subscription(user_id=user.id, plan="familiar", es_titular=True))
        session.add(LicenseCode(codigo=_codigo_familiar(session), tipo="familiar", group_id=grupo.id))
    session.flush()


def canjear(session: Session, user: User, codigo: str, hoy: date) -> None:
    """Canjea un código: uno de convenio activa Institucional y uno familiar une a la persona a esa familia.
    `hoy` es el de la persona; un código vale hasta su fecha de vencimiento inclusive."""
    encontrado = session.exec(
        select(LicenseCode).where(LicenseCode.codigo == codigo.strip().upper())
    ).first()
    if encontrado is None:
        raise CodigoNoEncontrado("Ese código no existe.")

    if encontrado.tipo == "convenio":
        suscripcion = suscripcion_de(session, user)
        if suscripcion is not None and suscripcion.license_code_id == encontrado.id:
            return  # ya lo canjeó
        organizacion = session.get(Organization, encontrado.organization_id)
        if not organizacion.activa:
            raise PlanError("Ese convenio ya no está activo.")
        if encontrado.vence_en is not None and hoy > encontrado.vence_en:
            raise PlanError("Ese código venció.")
        if encontrado.max_usos is not None and encontrado.usos >= encontrado.max_usos:
            raise PlanError("Ese código ya alcanzó su límite de usos.")

        salir_del_plan(session, user)
        encontrado.usos += 1
        session.add(encontrado)
        session.add(
            Subscription(
                user_id=user.id,
                plan="institucional",
                organization_id=encontrado.organization_id,
                license_code_id=encontrado.id,
            )
        )
    else:
        if user.group_id == encontrado.group_id:
            return  # ya está en esa familia
        if _integrantes(session, encontrado.group_id) >= MAX_INTEGRANTES_FAMILIA:
            raise PlanError(f"Esa familia ya tiene {MAX_INTEGRANTES_FAMILIA} integrantes.")

        salir_del_plan(session, user)
        user.group_id = encontrado.group_id
        session.add(user)
        session.add(Subscription(user_id=user.id, plan="familiar", license_code_id=encontrado.id))
    session.flush()
