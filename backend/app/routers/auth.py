from fastapi import APIRouter, Depends, HTTPException, status
from jose import JWTError
from sqlmodel import Session, delete, select

from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_refresh_token,
    hash_password,
    verify_password,
)
from app.db.session import get_session
from app.deps import get_current_user
from app.models.budget import Budget
from app.models.category import Category
from app.models.coach import CoachMessage, EmotionalCheckin
from app.models.expense import Expense
from app.models.gamification import Achievement, Challenge, PointEvent
from app.models.goal import Goal, GoalContribution
from app.models.income import Income
from app.models.recurring_expense import RecurringExpense
from app.models.user import User
from app.schemas.auth import (
    GoogleAuthRequest,
    LoginRequest,
    RefreshRequest,
    RegisterRequest,
    TokenResponse,
)
from app.schemas.user import UserResponse, UserUpdate
from app.services.google_auth import GoogleTokenError, verify_google_token

router = APIRouter(prefix="/auth", tags=["auth"])


def _tokens_for(user: User) -> TokenResponse:
    subject = str(user.id)
    return TokenResponse(
        access_token=create_access_token(subject=subject),
        refresh_token=create_refresh_token(subject=subject),
    )


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def register(payload: RegisterRequest, session: Session = Depends(get_session)) -> User:
    existing = session.exec(select(User).where(User.email == payload.email)).first()

    if existing is not None:
        if existing.hashed_password is not None:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Ese email ya está registrado.")
        # Tenía cuenta solo por Google (sin password) — le agregamos una en vez de fallar.
        existing.hashed_password = hash_password(payload.password)
        session.add(existing)
        session.commit()
        session.refresh(existing)
        return existing

    user = User(
        email=payload.email,
        hashed_password=hash_password(payload.password),
        nombre=payload.nombre,
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, session: Session = Depends(get_session)) -> TokenResponse:
    user = session.exec(select(User).where(User.email == payload.email)).first()

    if user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Credenciales inválidas.")
    if user.hashed_password is None:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, "Esta cuenta usa Google para iniciar sesión."
        )
    if not verify_password(payload.password, user.hashed_password):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Credenciales inválidas.")

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


@router.delete("/me", status_code=status.HTTP_204_NO_CONTENT)
def delete_me(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> None:
    """Borra la cuenta y todos sus datos. El orden respeta las llaves foráneas:
    los gastos apuntan a presupuestos, categorías y gastos fijos."""
    user_id = current_user.id
    for modelo in (GoalContribution, Goal, Challenge, Achievement, PointEvent, EmotionalCheckin, CoachMessage):
        session.exec(delete(modelo).where(modelo.user_id == user_id))
    session.exec(delete(Expense).where(Expense.user_id == user_id))
    session.exec(delete(Income).where(Income.user_id == user_id))
    session.exec(delete(RecurringExpense).where(RecurringExpense.user_id == user_id))
    session.exec(delete(Budget).where(Budget.owner_id == user_id))
    session.exec(delete(Category).where(Category.owner_id == user_id))
    session.delete(current_user)
    session.commit()
