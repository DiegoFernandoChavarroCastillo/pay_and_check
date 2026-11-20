"""Apoyos de la universidad: cerrar el ciclo entre "el panel ve estrés financiero" y "el estudiante recibe
ayuda". La app sugiere los apoyos cuando las cifras lo justifican; la universidad solo ve cuántos se
interesaron por cada apoyo (agregado, k ≥ 5), nunca quién."""

from dataclasses import dataclass
from datetime import date, timedelta

from sqlmodel import Session, func, select

from app.models.coach import EmotionalCheckin
from app.models.plan import Subscription
from app.models.support import SupportInterest, SupportResource
from app.models.user import User
from app.services.budget_lookup import get_active_budget_for_user
from app.services.budget_totals import summary_for

ANIMOS_DE_ESTRES = ("ansioso", "preocupado")
# Mismo umbral que "señales de estrés" del panel: 3 o más días de ansiedad o preocupación en 14 días.
DIAS_DE_ESTRES = 3


def organizacion_de(session: Session, user: User) -> int | None:
    """La universidad del convenio de la persona, si tiene plan Institucional."""
    return session.exec(
        select(Subscription.organization_id)
        .where(Subscription.user_id == user.id)
        .where(Subscription.plan == "institucional")
    ).first()


def motivo_para_sugerir(session: Session, user: User, today: date) -> str | None:
    """ "en_riesgo" si el presupuesto no alcanza al ritmo actual, "estres" si hay señales de estrés en los
    check-ins, o None. Con esto la app pone los apoyos a la vista sin que la persona tenga que buscarlos."""
    budget = get_active_budget_for_user(session, user.id, today)
    if budget is not None and summary_for(session, budget, today).en_riesgo:
        return "en_riesgo"
    dias = session.exec(
        select(func.count())
        .select_from(EmotionalCheckin)
        .where(EmotionalCheckin.user_id == user.id)
        .where(EmotionalCheckin.fecha >= today - timedelta(days=13))
        .where(EmotionalCheckin.animo.in_(ANIMOS_DE_ESTRES))
    ).one()
    return "estres" if dias >= DIAS_DE_ESTRES else None


@dataclass
class Apoyo:
    recurso: SupportResource
    me_interesa: bool


def apoyos_de(session: Session, user: User) -> list[Apoyo]:
    org_id = organizacion_de(session, user)
    if org_id is None:
        return []
    recursos = session.exec(
        select(SupportResource)
        .where(SupportResource.organization_id == org_id)
        .where(SupportResource.activo)
        .order_by(SupportResource.id)
    ).all()
    mios = set(
        session.exec(select(SupportInterest.resource_id).where(SupportInterest.user_id == user.id)).all()
    )
    return [Apoyo(r, r.id in mios) for r in recursos]
