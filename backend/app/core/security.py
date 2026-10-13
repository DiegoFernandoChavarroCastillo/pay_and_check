from datetime import UTC, datetime, timedelta
from typing import Any

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.core.config import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

ACCESS_TOKEN_TYPE = "access"
REFRESH_TOKEN_TYPE = "refresh"


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def _create_token(subject: str, token_type: str, expires_delta: timedelta) -> str:
    to_encode = {"sub": subject, "type": token_type, "exp": datetime.now(UTC) + expires_delta}
    return jwt.encode(to_encode, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)


def _decode_token(token: str, expected_type: str) -> dict[str, Any]:
    payload = jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])
    if payload.get("type") != expected_type:
        raise JWTError("Tipo de token incorrecto.")
    return payload


def create_access_token(subject: str, expires_minutes: int | None = None) -> str:
    """`subject` es lo que va en el claim `sub` — usamos el id del usuario (como str)."""
    minutes = expires_minutes if expires_minutes is not None else settings.ACCESS_TOKEN_EXPIRE_MINUTES
    return _create_token(subject, ACCESS_TOKEN_TYPE, timedelta(minutes=minutes))


def decode_access_token(token: str) -> dict[str, Any]:
    """Lanza `jose.JWTError` si el token es inválido, está mal firmado, expiró
    o no es un access token (un refresh token no sirve para autenticarse)."""
    return _decode_token(token, ACCESS_TOKEN_TYPE)


def create_refresh_token(subject: str) -> str:
    """Token de larga duración que solo sirve para pedir un access token nuevo
    en `POST /auth/refresh`. Es stateless: no se puede revocar uno ya emitido."""
    return _create_token(subject, REFRESH_TOKEN_TYPE, timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS))


def decode_refresh_token(token: str) -> dict[str, Any]:
    """Lanza `jose.JWTError` si el token es inválido, expiró o no es un refresh token."""
    return _decode_token(token, REFRESH_TOKEN_TYPE)
