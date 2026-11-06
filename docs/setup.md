# Configuración local, pruebas y despliegue

## Requisitos

- Backend: Docker + Docker Compose, **o** Python 3.12 + [`uv`](https://docs.astral.sh/uv/) y un PostgreSQL accesible.
- Móvil: Flutter 3.47.7 (stable), JDK 17, Android SDK (plataforma 36, build-tools 36.0.0, `ANDROID_HOME`).

## Variables de entorno (backend)

Definidas en `backend/app/core/config.py`; plantilla en `backend/.env.example`.

| Variable | Obligatoria | Descripción |
|---|---|---|
| `DATABASE_URL` | sí | p. ej. `postgresql+psycopg2://postgres:postgres@localhost:5432/pay_and_check` |
| `JWT_SECRET` | sí | Clave de firma de los JWT |
| `JWT_ALGORITHM` | no | `HS256` |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | no | `60` |
| `REFRESH_TOKEN_EXPIRE_DAYS` | no | `30` |
| `GROQ_API_KEY` | no | Sin ella, el parseo con IA responde 502 y el coach usa textos de respaldo |
| `GOOGLE_CLIENT_ID` | no | Client ID *web*; sin él, `/auth/google` responde 401 |
| `CORS_ORIGINS` | no | Orígenes separados por coma (`http://localhost:5173`) |

## Backend con Docker

```bash
cd backend
cp .env.example .env        # completar JWT_SECRET, GROQ_API_KEY, ...
docker compose up --build   # api en :8000, postgres:16 en :5432
docker compose exec api sh -c "alembic upgrade head && python -m app.db.seed"
```

`docker-compose.yml` sobrescribe `DATABASE_URL` para apuntar al servicio `db` y arranca uvicorn con `--reload`.
API en `http://localhost:8000`, docs en `/docs`, salud en `/health`.

## Backend sin Docker

```bash
cd backend
cp .env.example .env        # DATABASE_URL a un Postgres accesible (local o Neon)
uv sync
uv run alembic upgrade head
uv run python -m app.db.seed
uv run uvicorn app.main:app --reload
```

## Tests y lint

```bash
cd backend
uv run ruff check .
uv run pytest -v            # herméticos: SQLite en memoria, sin .env ni red (tests/conftest.py)

cd ../mobile
flutter pub get
flutter analyze
flutter test
```

## App móvil

La configuración se fija al compilar (`mobile/lib/core/config/app_config.dart`):

| `--dart-define` | Defecto | Uso |
|---|---|---|
| `API_BASE_URL` | `http://10.0.2.2:8000` | URL del backend (localhost del PC desde el emulador) |
| `GOOGLE_SERVER_CLIENT_ID` | vacío | Client ID web de Google; vacío oculta el botón de Google |

```bash
cd mobile
flutter run                                           # emulador, backend local
# teléfono físico por USB:
adb reverse tcp:8000 tcp:8000
flutter run --dart-define=API_BASE_URL=http://localhost:8000
```

Más detalle (SMS simulados, sistema de diseño, APK): `mobile/README.md`.

## CI/CD y despliegue

| Pieza | Descripción |
|---|---|
| `.github/workflows/backend-ci.yml` | En cambios de `backend/**`: `uv sync --frozen`, `ruff check`, `pytest` |
| `.github/workflows/mobile-ci.yml` | CI de la app Flutter |
| `.github/workflows/mobile-release.yml` | Al empujar un tag `v*` compila el APK firmado y lo adjunta a un GitHub Release. Requiere secretos `ANDROID_KEYSTORE_BASE64`, `ANDROID_KEYSTORE_PASSWORD`, `ANDROID_KEY_ALIAS`, `ANDROID_KEY_PASSWORD` y variable `API_BASE_URL` (opcional `GOOGLE_SERVER_CLIENT_ID`) |
| `backend/Dockerfile` | Multi-stage (`uv sync --frozen --no-dev`), usuario no root, `CMD sh /app/start.sh` |
| `backend/start.sh` | `alembic upgrade head` → `python -m app.db.seed` → `uvicorn` en `$PORT` (def. 8000) |
| `render.yaml` | Blueprint de Render: servicio web Docker, plan free, región `ohio`, `healthCheckPath: /health`, `JWT_SECRET` autogenerado; `DATABASE_URL`, `GROQ_API_KEY`, `GOOGLE_CLIENT_ID` se cargan a mano. La base es externa (Neon) |
