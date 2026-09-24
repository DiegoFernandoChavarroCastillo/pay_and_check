from google.auth.transport import requests as google_requests
from google.oauth2 import id_token as google_id_token

from app.core.config import settings


class GoogleTokenError(Exception):
    """El id_token de Google es inválido, expiró, o no corresponde a nuestro Client ID."""


def verify_google_token(token: str) -> dict[str, str]:
    """Verifica la firma de un id_token de Google Identity Services.

    Devuelve {google_id, email, nombre} si es válido; lanza GoogleTokenError si no.
    """
    try:
        idinfo = google_id_token.verify_oauth2_token(
            token, google_requests.Request(), settings.GOOGLE_CLIENT_ID
        )
    except ValueError as exc:
        raise GoogleTokenError("Token de Google inválido o expirado.") from exc

    return {
        "google_id": idinfo["sub"],
        "email": idinfo["email"],
        "nombre": idinfo.get("name", idinfo["email"]),
    }
