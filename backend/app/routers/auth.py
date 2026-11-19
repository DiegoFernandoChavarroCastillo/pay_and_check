from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Request, status
from jose import JWTError
from sqlmodel import Session, delete, select

from app.core import rate_limit
from app.core.config import POLITICA_VERSION
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_refresh_token,
    hash_password,
    verify_password,
)
from app.db.session import get_session
from app.deps import get_current_user
from app.models.ai_usage import AiUsage
from app.models.budget import Budget
from app.models.category import Category, CategoryLimit
from app.models.coach import CoachMessage, EmotionalCheckin
from app.models.expense import Expense
from app.models.gamification import Achievement, Challenge, PointEvent
from app.models.goal import Goal, GoalContribution
from app.models.income import Income
from app.models.recurring_expense import RecurringExpense
from app.models.user import User
from app.schemas.auth import (
    ConsentimientoRequest,
    ConsentimientoSmsRequest,
    GoogleAuthRequest,
    LoginRequest,
    RefreshRequest,
    RegisterRequest,
    TokenResponse,
)
from app.schemas.user import UserResponse, UserUpdate
from app.services.google_auth import GoogleTokenError, verify_google_token
from app.services.planes import salir_del_plan

router = APIRouter(prefix="/auth", tags=["auth"])


def _tokens_for(user: User) -> TokenResponse:
    subject = str(user.id)
    return TokenResponse(
        access_token=create_access_token(subject=subject),
        refresh_token=create_refresh_token(subject=subject),
    )


def _validar_politica(version: str) -> None:
    if version != POLITICA_VERSION:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT, "La política de privacidad cambió: vuelve a leerla y aceptarla."
        )


def _aceptar_politica(user: User) -> None:
    user.politica_version = POLITICA_VERSION
    user.politica_aceptada_at = datetime.now(UTC)


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def register(payload: RegisterRequest, session: Session = Depends(get_session)) -> User:
    if not payload.acepta_politica:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            "Para crear la cuenta debes aceptar la política de privacidad y el tratamiento de tus datos.",
        )
    _validar_politica(payload.politica_version)
    existing = session.exec(select(User).where(User.email == payload.email)).first()

    if existing is not None:
        if existing.hashed_password is not None:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Ese email ya está registrado.")
        # Tenía cuenta solo por Google (sin password) — le agregamos una en vez de fallar.
        existing.hashed_password = hash_password(payload.password)
        _aceptar_politica(existing)
        session.add(existing)
        session.commit()
        session.refresh(existing)
        return existing

    user = User(
        email=payload.email,
        hashed_password=hash_password(payload.password),
        nombre=payload.nombre,
        # La app manda el idioma del teléfono: la cuenta nace hablando como el dispositivo.
        idioma=payload.idioma or "es",
    )
    _aceptar_politica(user)
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


@router.post("/login", response_model=TokenResponse)
def login(
    payload: LoginRequest, request: Request, session: Session = Depends(get_session)
) -> TokenResponse:
    ip = rate_limit.ip_del_cliente(request)
    rate_limit.revisar_login(ip, payload.email)  # bloqueado: ni se mira la contraseña
    user = session.exec(select(User).where(User.email == payload.email)).first()

    fallo = None
    if user is None:
        fallo = HTTPException(status.HTTP_401_UNAUTHORIZED, "Credenciales inválidas.")
    elif user.hashed_password is None:
        fallo = HTTPException(status.HTTP_400_BAD_REQUEST, "Esta cuenta usa Google para iniciar sesión.")
    elif not verify_password(payload.password, user.hashed_password):
        fallo = HTTPException(status.HTTP_401_UNAUTHORIZED, "Credenciales inválidas.")
    if fallo is not None:
        rate_limit.registrar_fallo_de_login(ip, payload.email)
        raise fallo

    rate_limit.limpiar_fallos_de_login(payload.email)
    return _tokens_for(user)


@router.post("/google", response_model=TokenResponse)
def google_login(payload: GoogleAuthRequest, session: Session = Depends(get_session)) -> TokenResponse:
    try:
        info = verify_google_token(payload.id_token)
    except GoogleTokenError as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, str(exc)) from exc

    user = session.exec(select(User).where(User.google_id == info["google_id"])).first()

    if user is None:
        info["email"] = info["email"].lower()
        user = session.exec(select(User).where(User.email == info["email"])).first()
        if user is not None:
            # Ya tenía cuenta por password — le asociamos el google_id, mismo usuario.
            user.google_id = info["google_id"]
        else:
            user = User(email=info["email"], google_id=info["google_id"], nombre=info["nombre"])
        session.add(user)
        session.commit()
        session.refresh(user)

    return _tokens_for(user)


@router.post("/refresh", response_model=TokenResponse)
def refresh(payload: RefreshRequest, session: Session = Depends(get_session)) -> TokenResponse:
    """Cambia un refresh token válido por un par nuevo (access + refresh)."""
    try:
        user_id = int(decode_refresh_token(payload.refresh_token)["sub"])
    except (JWTError, KeyError, ValueError) as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Refresh token inválido o expirado.") from exc

    user = session.get(User, user_id)
    if user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Usuario no encontrado.")
    return _tokens_for(user)


@router.get("/me", response_model=UserResponse)
def me(current_user: User = Depends(get_current_user)) -> User:
    return current_user


@router.patch("/me", response_model=UserResponse)
def update_me(
    payload: UserUpdate,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> User:
    for field, value in payload.model_dump(exclude_unset=True, exclude_none=True).items():
        setattr(current_user, field, value)

    session.add(current_user)
    session.commit()
    session.refresh(current_user)
    return current_user


@router.put("/me/consent", response_model=UserResponse)
def aceptar_politica(
    payload: ConsentimientoRequest,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> User:
    """Acepta la política vigente. Lo usan las cuentas creadas con Google (que no pasan por el registro) y
    quien aceptó una versión anterior."""
    _validar_politica(payload.politica_version)
    _aceptar_politica(current_user)
    session.add(current_user)
    session.commit()
    session.refresh(current_user)
    return current_user


@router.put("/me/consent/sms", response_model=UserResponse)
def consentimiento_sms(
    payload: ConsentimientoSmsRequest,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> User:
    """Registra (o revoca) el permiso para leer los SMS bancarios. Los SMS se leen en el teléfono; aquí solo
    queda la fecha en que la persona aceptó."""
    current_user.sms_consent_at = datetime.now(UTC) if payload.acepta else None
    session.add(current_user)
    session.commit()
    session.refresh(current_user)
    return current_user


@router.delete("/me", status_code=status.HTTP_204_NO_CONTENT)
def delete_me(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> None:
    """Borra la cuenta y todos sus datos. El orden respeta las llaves foráneas:
    los gastos apuntan a presupuestos, categorías y gastos fijos."""
    user_id = current_user.id
    # Antes que todo lo demás: si era el titular de una familia, esta se disuelve y todos vuelven a Gratis.
    salir_del_plan(session, current_user)
    for modelo in (
        GoalContribution, Goal, Challenge, Achievement, PointEvent, EmotionalCheckin, CoachMessage, CategoryLimit,
        AiUsage,
    ):  # fmt: skip
        session.exec(delete(modelo).where(modelo.user_id == user_id))
    session.exec(delete(Expense).where(Expense.user_id == user_id))
    session.exec(delete(Income).where(Income.user_id == user_id))
    session.exec(delete(RecurringExpense).where(RecurringExpense.user_id == user_id))
    session.exec(delete(Budget).where(Budget.owner_id == user_id))
    session.exec(delete(Category).where(Category.owner_id == user_id))
    session.delete(current_user)
    session.commit()
