from datetime import date

from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session

from app.core.time import today_for
from app.db.session import get_session
from app.deps import get_current_user
from app.models.plan import Organization
from app.models.user import User
from app.schemas.extras import FamilyMemberProgress, ShareProgressRequest
from app.schemas.plan import (
    CambiarPlanRequest,
    CanjearRequest,
    FamiliaResponse,
    PlanResponse,
    SuscripcionResponse,
)
from app.services import familia, ia_uso, planes

router = APIRouter(tags=["plans"])

AVISO_SIMULADO = "Plan simulado: en el piloto no hay cobro real."


def _primer_dia_del_mes_siguiente(hoy: date) -> date:
    return date(hoy.year + (hoy.month == 12), hoy.month % 12 + 1, 1)


def _suscripcion(session: Session, user: User) -> SuscripcionResponse:
    suscripcion = planes.suscripcion_de(session, user)
    plan = planes.CATALOGO[suscripcion.plan if suscripcion is not None else "gratis"]
    usadas = ia_uso.usadas_en_el_mes(session, user)

    familia = None
    datos = planes.datos_de_familia(session, user) if plan.codigo == "familiar" else None
    if datos is not None:
        familia = FamiliaResponse(
            codigo=datos[0],
            integrantes=datos[1],
            max_integrantes=planes.MAX_INTEGRANTES_FAMILIA,
            es_titular=suscripcion.es_titular,
            comparte_progreso=suscripcion.comparte_progreso,
        )
    organizacion = None
    if suscripcion is not None and suscripcion.organization_id is not None:
        organizacion = session.get(Organization, suscripcion.organization_id).nombre

    return SuscripcionResponse(
        plan=plan.codigo,
        cupo_ia_mensual=plan.cupo_ia_mensual,
        usadas=usadas,
        restantes=max(plan.cupo_ia_mensual - usadas, 0),
        compartido=plan.compartido,
        reinicia_el=_primer_dia_del_mes_siguiente(today_for(user)),
        organizacion=organizacion,
        familia=familia,
        aviso=AVISO_SIMULADO if plan.estado_demo == "simulado" else None,
    )


@router.get("/plans", response_model=list[PlanResponse])
def listar_planes(_: User = Depends(get_current_user)) -> list[PlanResponse]:
    return [PlanResponse(**vars(plan)) for plan in planes.CATALOGO.values()]


@router.get("/me/subscription", response_model=SuscripcionResponse)
def mi_suscripcion(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> SuscripcionResponse:
    return _suscripcion(session, current_user)


@router.post("/me/subscription/redeem", response_model=SuscripcionResponse)
def canjear_codigo(
    payload: CanjearRequest,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> SuscripcionResponse:
    """Canjea un código de convenio (activa Institucional) o un código familiar (une a una familia)."""
    try:
        planes.canjear(session, current_user, payload.codigo, today_for(current_user))
    except planes.CodigoNoEncontrado as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from exc
    except planes.PlanError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(exc)) from exc
    session.commit()
    return _suscripcion(session, current_user)


@router.put("/me/subscription", response_model=SuscripcionResponse)
def cambiar_mi_plan(
    payload: CambiarPlanRequest,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> SuscripcionResponse:
    """Cambia de plan. Es una simulación: no hay pasarela de pago, solo cambian el plan y el cupo."""
    try:
        planes.cambiar_plan(session, current_user, payload.plan)
    except planes.PlanError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(exc)) from exc
    session.commit()
    return _suscripcion(session, current_user)


@router.put("/me/subscription/share-progress", status_code=status.HTTP_204_NO_CONTENT)
def compartir_progreso(
    payload: ShareProgressRequest,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> None:
    """En el plan Familiar, deja (o deja de dejar) que el titular vea el progreso agregado de la persona."""
    suscripcion = planes.suscripcion_de(session, current_user)
    if suscripcion is None or suscripcion.plan != "familiar":
        raise HTTPException(status.HTTP_409_CONFLICT, "Compartir el progreso es parte del plan Familiar.")
    suscripcion.comparte_progreso = payload.comparte
    session.add(suscripcion)
    session.commit()


@router.get("/me/family/progress", response_model=list[FamilyMemberProgress])
def progreso_familiar(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> list[FamilyMemberProgress]:
    """Para el titular de la familia: el progreso agregado de cada integrante que lo comparte. Nunca gastos,
    montos del presupuesto ni check-ins."""
    suscripcion = planes.suscripcion_de(session, current_user)
    if suscripcion is None or suscripcion.plan != "familiar" or not suscripcion.es_titular:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Solo el titular del plan Familiar ve este progreso.")
    return [
        FamilyMemberProgress(**vars(p))
        for p in familia.progreso_de_familia(session, current_user, today_for(current_user))
    ]
