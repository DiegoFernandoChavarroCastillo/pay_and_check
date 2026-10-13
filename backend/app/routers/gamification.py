from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session, func, select

from app.core.time import today_for
from app.db.session import get_session
from app.deps import get_current_user
from app.models.gamification import Achievement, Challenge, PointEvent
from app.models.user import User
from app.schemas.gamification import (
    BadgeResponse,
    ChallengeCreate,
    ChallengeResponse,
    ChallengeSuggestionResponse,
    GamificationProfileResponse,
)
from app.services import gamification as servicio

router = APIRouter(tags=["gamification"])


def _reto_a_respuesta(session: Session, reto: Challenge, today) -> ChallengeResponse:
    valor, estado = servicio.progreso_reto(session, reto, today)
    return ChallengeResponse(
        id=reto.id,
        tipo=reto.tipo,
        category_id=reto.category_id,
        descripcion=reto.descripcion,
        objetivo=reto.objetivo,
        linea_base=reto.linea_base,
        valor_actual=valor,
        fecha_inicio=reto.fecha_inicio,
        fecha_fin=reto.fecha_fin,
        estado=estado,
        puntos=reto.puntos,
    )


@router.get("/challenges/suggestions", response_model=list[ChallengeSuggestionResponse])
def challenge_suggestions(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> list[dict]:
    return servicio.sugerencias_de_retos(session, current_user, today_for(current_user))


@router.post("/challenges", response_model=ChallengeResponse, status_code=status.HTTP_201_CREATED)
def create_challenge(
    payload: ChallengeCreate,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ChallengeResponse:
    today = today_for(current_user)
    try:
        reto = servicio.crear_reto(
            session, current_user, payload.plantilla, today, payload.category_id, payload.porcentaje
        )
    except servicio.ChallengeError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc
    return _reto_a_respuesta(session, reto, today)


@router.get("/challenges", response_model=list[ChallengeResponse])
def list_challenges(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> list[ChallengeResponse]:
    today = today_for(current_user)
    # Cierra los retos vencidos y otorga sus puntos antes de listarlos.
    servicio.sync_gamification(session, current_user, today)
    retos = session.exec(
        select(Challenge).where(Challenge.user_id == current_user.id).order_by(Challenge.id.desc())
    ).all()
    return [_reto_a_respuesta(session, reto, today) for reto in retos]


@router.delete("/challenges/{challenge_id}", status_code=status.HTTP_204_NO_CONTENT)
def abandon_challenge(
    challenge_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> None:
    """Abandona un reto activo. Los ya cumplidos o fallidos quedan como historial."""
    reto = session.get(Challenge, challenge_id)
    if reto is None or reto.user_id != current_user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Reto no encontrado.")
    if reto.estado != "activo":
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Solo se puede abandonar un reto activo.")
    session.delete(reto)
    session.commit()


@router.get("/gamification/profile", response_model=GamificationProfileResponse)
def gamification_profile(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> GamificationProfileResponse:
    today = today_for(current_user)
    sync = servicio.sync_gamification(session, current_user, today)

    puntos = session.exec(
        select(func.coalesce(func.sum(PointEvent.puntos), 0)).where(PointEvent.user_id == current_user.id)
    ).one()
    actividad = servicio.dias_con_gasto(session, current_user.id, today) | servicio.dias_con_checkin(
        session, current_user.id, today
    )
    desbloqueadas = {
        a.codigo: a.unlocked_at
        for a in session.exec(select(Achievement).where(Achievement.user_id == current_user.id)).all()
    }
    recientes = session.exec(
        select(PointEvent)
        .where(PointEvent.user_id == current_user.id)
        .order_by(PointEvent.fecha.desc(), PointEvent.id.desc())
        .limit(20)
    ).all()

    insignias = []
    for codigo in servicio.INSIGNIAS:
        nombre, descripcion = servicio.insignia_texto(codigo, current_user.idioma)
        insignias.append(
            BadgeResponse(
                codigo=codigo,
                nombre=nombre,
                descripcion=descripcion,
                desbloqueada=codigo in desbloqueadas,
                unlocked_at=desbloqueadas.get(codigo),
            )
        )

    return GamificationProfileResponse(
        puntos=puntos,
        nivel=servicio.nivel_para(puntos, current_user.idioma),
        racha_actual=servicio.racha_actual(actividad, today),
        mejor_racha=max((longitud for _, longitud in servicio.rachas(actividad)), default=0),
        metricas=servicio.metricas(session, current_user, today, actividad),
        insignias=insignias,
        eventos_recientes=[{"tipo": e.tipo, "puntos": e.puntos, "fecha": e.fecha} for e in recientes],
        nuevos_puntos=sum(e.puntos for e in sync.eventos),
        nuevas_insignias=[servicio.insignia_texto(c, current_user.idioma)[0] for c in sync.insignias],
    )
