from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Configuración de la app, leída desde variables de entorno / .env."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    DATABASE_URL: str
    JWT_SECRET: str
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    REFRESH_TOKEN_EXPIRE_DAYS: int = 30
    # Opcionales para que el backend arranque sin ellas: sin GROQ_API_KEY el
    # parseo con IA responde 503 y el coach usa sus textos de respaldo; sin
    # GOOGLE_CLIENT_ID el login con Google queda deshabilitado (401).
    GROQ_API_KEY: str = ""
    # Proveedor de respaldo con el mismo modelo (gpt-oss-20b) y API compatible con OpenAI, para cuando Groq
    # falla o llega a su límite (docs/negocio/analisis-financiero.md). Vacío = sin respaldo: el coach usa sus
    # textos fijos. Ej.: DeepInfra, https://api.deepinfra.com/v1/openai con el modelo openai/gpt-oss-20b.
    AI_FALLBACK_URL: str = ""
    AI_FALLBACK_API_KEY: str = ""
    AI_FALLBACK_MODEL: str = "openai/gpt-oss-20b"
    # Uno o varios Client ID web de Google separados por coma (app Android y versión web).
    GOOGLE_CLIENT_ID: str = ""
    # Orígenes permitidos por CORS, separados por coma (ver .env.example).
    # No estaba contemplada en la Fase 0; se agregó al llegar a la Fase 1
    # porque el plan pedía CORS sin definir de dónde sale el origen.
    CORS_ORIGINS: str = "http://localhost:5173"

    @property
    def cors_origins_list(self) -> list[str]:
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",") if origin.strip()]


settings = Settings()

# Versión de la política de privacidad vigente (docs/privacidad.md). La app manda la que mostró al aceptarla; al
# publicar una nueva, se cambia aquí y en la app, y quien aceptó una anterior la vuelve a ver al entrar.
POLITICA_VERSION = "2026-11"
