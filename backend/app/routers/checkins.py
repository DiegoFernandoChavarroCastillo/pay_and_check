from datetime import date

from fastapi import APIRouter, Depends
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select

from app.core.time import today_for
from app.db.session import get_session
from app.deps import get_current_user
from app.models.coach import EmotionalCheckin
from app.models.user import User
from app.schemas.coach import CheckinCreate, CheckinResponse

router = APIRouter(prefix="/checkins", tags=["checkins"])


@router.post("", response_model=CheckinResponse)
def registrar_checkin(
    payload: CheckinCreate,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> EmotionalCheckin:
    """Check-in emocional de hoy. Hay uno por día: repetirlo reemplaza el anterior."""
    today = today_for(current_user)
    user_id = current_user.id

    def _guardar() -> EmotionalCheckin:
        checkin = session.exec(
            select(EmotionalCheckin)
            .where(EmotionalCheckin.user_id == user_id)
            .where(EmotionalCheckin.fecha == today)
        ).first()
        if checkin is None:
            checkin = EmotionalCheckin(user_id=user_id, fecha=today, animo=payload.animo)
        checkin.animo = payload.animo
        checkin.nota = payload.nota
        session.add(checkin)
        session.commit()
        session.refresh(checkin)
        return checkin

    try:
        return _guardar()
    except IntegrityError:
        # Dos toques casi simultáneos: el otro ya creó el check-in de hoy.
        # Se reintenta, y esta vez lo encuentra y lo actualiza.
        session.rollback()
        return _guardar()


@router.get("", response_model=list[CheckinResponse])
def listar_checkins(
    fecha_desde: date | None = None,
    fecha_hasta: date | None = None,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> list[EmotionalCheckin]:
    query = select(EmotionalCheckin).where(EmotionalCheckin.user_id == current_user.id)
    if fecha_desde is not None:
        query = query.where(EmotionalCheckin.fecha >= fecha_desde)
    if fecha_hasta is not None:
        query = query.where(EmotionalCheckin.fecha <= fecha_hasta)
    return session.exec(query.order_by(EmotionalCheckin.fecha.desc())).all()
