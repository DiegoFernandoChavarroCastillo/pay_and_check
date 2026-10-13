from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session

from app.core.time import today_for
from app.db.session import get_session
from app.deps import get_current_user
from app.models.coach import CoachMessage
from app.models.expense import Expense
from app.models.user import User
from app.schemas.coach import (
    ChatMessageResponse,
    ChatRequest,
    CoachTextResponse,
    InsightResponse,
    ReactionRequest,
)
from app.services import coach as coach_service
from app.services.groq_client import GroqServiceError

router = APIRouter(prefix="/coach", tags=["coach"])


def _a_respuesta(mensaje: CoachMessage) -> ChatMessageResponse:
    return ChatMessageResponse(
        id=mensaje.id,
        rol="usuario" if mensaje.tipo == "chat_user" else "coach",
        contenido=mensaje.contenido,
        created_at=mensaje.created_at,
    )


@router.post("/reaction", response_model=CoachTextResponse)
def reaccion(
    payload: ReactionRequest,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> CoachTextResponse:
    """Mensaje del coach tras registrar un gasto. La app lo pide en segundo
    plano: nunca bloquea ni condiciona el registro."""
    expense = session.get(Expense, payload.expense_id)
    if expense is None or expense.user_id != current_user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Gasto no encontrado.")
    mensaje = coach_service.reaccion_a_gasto(session, current_user, expense, today_for(current_user))
    return CoachTextResponse(mensaje=mensaje)


@router.get("/insights", response_model=list[InsightResponse])
def insights(
    refresh: bool = False,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> list[dict]:
    """Consejos del día, cada uno con una acción de un tap. `refresh=true`
    los recalcula con los datos más recientes."""
    return coach_service.insights_del_dia(session, current_user, today_for(current_user), refresh)


@router.get("/chat", response_model=list[ChatMessageResponse])
def historial(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> list[ChatMessageResponse]:
    return [_a_respuesta(m) for m in coach_service.historial_chat(session, current_user.id)]


@router.post("/chat", response_model=ChatMessageResponse)
def chat(
    payload: ChatRequest,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ChatMessageResponse:
    try:
        respuesta = coach_service.responder_chat(
            session, current_user, payload.mensaje, today_for(current_user)
        )
    except GroqServiceError as exc:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, "El coach no está disponible en este momento.") from exc
    return _a_respuesta(respuesta)
