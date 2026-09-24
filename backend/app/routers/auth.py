from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session, select

from app.core.security import create_access_token, hash_password, verify_password
from app.db.session import get_session
from app.deps import get_current_user
from app.models.user import User
from app.schemas.auth import GoogleAuthRequest, LoginRequest, RegisterRequest, TokenResponse
from app.schemas.user import UserResponse
from app.services.google_auth import GoogleTokenError, verify_google_token

router = APIRouter(prefix="/auth", tags=["auth"])


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

    token = create_access_token(subject=str(user.id))
    return TokenResponse(access_token=token)


@router.post("/google", response_model=TokenResponse)
def google_login(payload: GoogleAuthRequest, session: Session = Depends(get_session)) -> TokenResponse:
    try:
        info = verify_google_token(payload.id_token)
    except GoogleTokenError as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, str(exc)) from exc

    user = session.exec(select(User).where(User.google_id == info["google_id"])).first()

    if user is None:
        user = session.exec(select(User).where(User.email == info["email"])).first()
        if user is not None:
            # Ya tenía cuenta por password — le asociamos el google_id, mismo usuario.
            user.google_id = info["google_id"]
        else:
            user = User(email=info["email"], google_id=info["google_id"], nombre=info["nombre"])
        session.add(user)
        session.commit()
        session.refresh(user)

    token = create_access_token(subject=str(user.id))
    return TokenResponse(access_token=token)


@router.get("/me", response_model=UserResponse)
def me(current_user: User = Depends(get_current_user)) -> User:
    return current_user
