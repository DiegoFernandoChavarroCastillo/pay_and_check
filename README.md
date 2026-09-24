# pay_and_check

Repositorio para aplicación de registro de gastos personales con integración de IA.

Este repo por ahora contiene solo el **backend** (`backend/`). El frontend se planea en un documento aparte
(ver `plan-backend-gestion-gastos.md` para el plan de construcción completo del backend, fase por fase).

## Backend

- Python 3.12 + FastAPI + SQLModel/Alembic + PostgreSQL.
- Gestor de dependencias: [`uv`](https://docs.astral.sh/uv/).
- IA: [Groq](https://console.groq.com/) para parsear gastos en lenguaje natural y generar recomendaciones.

### Correr en local

```bash
cd backend
cp .env.example .env   # completar con tus propios valores
docker compose up --build
```

La API queda en `http://localhost:8000` (docs interactivas en `/docs`). También se puede correr sin Docker
con `uv sync && uv run uvicorn app.main:app --reload`, apuntando `DATABASE_URL` a cualquier Postgres accesible
(local, Docker, o uno gestionado como [Neon](https://neon.tech/)).

### Tests

```bash
cd backend
uv run pytest
```

La suite es hermética: no necesita `GROQ_API_KEY` real, `DATABASE_URL` real, ni conexión a internet
(`tests/conftest.py` usa SQLite en memoria y mockea las llamadas a Groq).

### Variables de entorno

Ver `backend/.env.example` para la lista completa con comentarios. Resumen para desplegar en un servicio
gestionado (Railway, Render, Fly.io, etc.):

| Variable | Descripción |
|---|---|
| `DATABASE_URL` | Cadena de conexión a Postgres, formato `postgresql://usuario:password@host:puerto/db`. Un Postgres gestionado (el propio del servicio, o Neon/Supabase) funciona igual que uno local. |
| `JWT_SECRET` | Secreto para firmar los JWT propios de la app. Generar uno largo y aleatorio en producción (nunca reusar `change-me`). |
| `JWT_ALGORITHM` | Algoritmo de firma del JWT. `HS256` por defecto. |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | Minutos de expiración del JWT. `60` por defecto. |
| `GROQ_API_KEY` | API key de [Groq](https://console.groq.com/keys) para el parseo de lenguaje natural y las recomendaciones. |
| `GOOGLE_CLIENT_ID` | Client ID de "Google Identity Services" (ver [Google Cloud Console](https://console.cloud.google.com/), pantalla de consentimiento OAuth + credencial "ID de cliente OAuth" de tipo aplicación web). El mismo Client ID lo usa el frontend. |
| `CORS_ORIGINS` | Orígenes permitidos por CORS, separados por coma — el/los dominio(s) donde corre el frontend en producción. |

### Desplegar

El `Dockerfile` es multi-stage y produce una imagen liviana lista para producción (corre como usuario no-root,
sin herramientas de build). Cualquier plataforma que despliegue desde un `Dockerfile` (Railway, Render, Fly.io,
Google Cloud Run, etc.) puede usarlo directamente:

```bash
docker build -t pay-and-check-backend ./backend
docker run -p 8000:8000 --env-file backend/.env pay-and-check-backend
```

Antes del primer despliegue (o tras cambiar los modelos), aplicar las migraciones contra la base de datos de
producción:

```bash
cd backend
DATABASE_URL="<url de producción>" uv run alembic upgrade head
DATABASE_URL="<url de producción>" uv run python -m app.db.seed
```

### CI

`.github/workflows/backend-ci.yml` corre `ruff check` y `pytest` en cada push/PR que toque `backend/`.
