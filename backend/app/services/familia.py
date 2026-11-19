"""Plan Familiar con sentido para quien paga: el titular (normalmente la mamá o el papá) ve el progreso
agregado de cada integrante que decidió compartirlo: constancia, racha, metas y si el presupuesto le alcanza.
Nunca ve gastos, montos del presupuesto ni check-ins."""

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from sqlmodel import Session, func, select

from app.models.goal import Goal, GoalContribution
from app.models.plan import Subscription
from app.models.user import User
from app.services import gamification
from app.services.budget_lookup import get_active_budget_for_user
from app.services.budget_totals import summary_for


@dataclass
class ProgresoIntegrante:
    nombre: str
    comparte: bool
    racha: int | None = None
    constancia: Decimal | None = None
    metas_activas: int | None = None
    progreso_metas: Decimal | None = None  # ahorrado / objetivo de sus metas activas, de 0 a 1
    presupuesto_alcanza: bool | None = None  # None si no tiene presupuesto activo


def progreso_de_familia(session: Session, titular: User, today: date) -> list[ProgresoIntegrante]:
    if titular.group_id is None:
        return []
    integrantes = session.exec(
        select(User, Subscription)
        .join(Subscription, Subscription.user_id == User.id)
        .where(User.group_id == titular.group_id)
        .where(User.id != titular.id)
        .order_by(User.id)
    ).all()
    resultado = []
    for user, suscripcion in integrantes:
        nombre = user.nombre.split(" ")[0]
        if not suscripcion.comparte_progreso:
            resultado.append(ProgresoIntegrante(nombre=nombre, comparte=False))
            continue
        actividad = gamification.dias_con_gasto(session, user.id, today) | gamification.dias_con_checkin(
            session, user.id, today
        )
        metricas = gamification.metricas(session, user, today, actividad)
        metas = session.exec(select(Goal).where(Goal.user_id == user.id, Goal.estado == "activa")).all()
        objetivo = sum((m.monto_objetivo for m in metas), Decimal("0"))
        ahorrado = (
            Decimal(
                session.exec(
                    select(func.coalesce(func.sum(GoalContribution.monto), 0)).where(
                        GoalContribution.goal_id.in_([m.id for m in metas])
                    )
                ).one()
            )
            if metas
            else Decimal("0")
        )
        budget = get_active_budget_for_user(session, user.id, today)
        resultado.append(
            ProgresoIntegrante(
                nombre=nombre,
                comparte=True,
                racha=gamification.racha_actual(actividad, today),
                constancia=metricas["consistencia"],
                metas_activas=len(metas),
                progreso_metas=(min(ahorrado / objetivo, Decimal(1))).quantize(Decimal("0.01")) if objetivo else None,
                presupuesto_alcanza=None if budget is None else not summary_for(session, budget, today).en_riesgo,
            )
        )
    return resultado
