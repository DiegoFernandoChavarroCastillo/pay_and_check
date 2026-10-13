# pay_and_check

Repositorio para aplicación de registro de gastos personales con integración de IA.

El repo contiene el **backend** (`backend/`) y la **app móvil** en Flutter (`mobile/`, ver `mobile/README.md`).

- `plan-backend-gestion-gastos.md`: plan del backend original, fase por fase (terminado).
- `mejoras.md`: visión del producto (coach financiero, gamificación, automatización).
- `plan-app-movil.md`: plan vigente para llevar esa visión a una app Android, fase por fase.
- `notas-iteracion-app-movil.md`: bugs, problemas y decisiones técnicas de la última iteración, y lo que falta.

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

### Qué expone la API

La documentación interactiva completa está en `/docs`. Resumen por módulo:

| Módulo | Endpoints | Para qué |
|---|---|---|
| Sesión | `/auth/register`, `/auth/login`, `/auth/google`, `/auth/refresh`, `/auth/me` (GET/PATCH/DELETE) | Cuenta, perfil (tono del coach, idioma, zona horaria) y borrado total de datos |
| Presupuesto | `/budgets`, `/budgets/active`, `/budgets/active/summary` | Presupuesto del periodo y el disponible por día |
| Movimientos | `/expenses` (+ `/parse`, `/parse-receipt`, `/from-text`), `/incomes`, `/recurring-expenses`, `/categories` | Gastos manuales o propuestos por IA desde texto, voz o recibo |
| Coach | `/checkins`, `/coach/reaction`, `/coach/insights`, `/coach/chat` | Check-in emocional, consejos accionables y chat |
| Gamificación | `/goals` (+ `/contributions`), `/challenges` (+ `/suggestions`), `/gamification/profile` | Metas con dinero realmente apartado, retos verificados, puntos, niveles e insignias |
| Reportes | `/reports/weekly`, `/reports/trends`, `/reports/monthly-wrapped` | Resumen semanal, gasto por semana para las gráficas y resumen mensual |

Dos reglas atraviesan todo el backend:

- **La IA redacta, no calcula.** Toda cifra sale de código determinista (`services/patterns.py`,
  `budget_totals.py`, `gamification.py`). Cada salida del modelo pasa por un filtro de guardrails y tiene un
  texto de respaldo, así que la app funciona igual aunque Groq no responda o falte `GROQ_API_KEY`.
- **Nada se auto-reporta.** Metas, retos, puntos e insignias se recalculan "al vuelo" a partir de los gastos y
  check-ins reales; el libro de puntos es idempotente.

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
| `REFRESH_TOKEN_EXPIRE_DAYS` | Días de vida del refresh token con el que la app móvil renueva el JWT (`POST /auth/refresh`). `30` por defecto. |
| `GROQ_API_KEY` | API key de [Groq](https://console.groq.com/keys) para el parseo de lenguaje natural, los recibos y el coach. Opcional para arrancar: sin ella el parseo responde 502 y el coach usa sus textos de respaldo. |
| `GOOGLE_CLIENT_ID` | Opcional: sin ella el login con Google queda deshabilitado. Client ID de "Google Identity Services" (ver [Google Cloud Console](https://console.cloud.google.com/), pantalla de consentimiento OAuth + credencial "ID de cliente OAuth" de tipo aplicación web). El mismo Client ID lo usa el frontend. |
| `CORS_ORIGINS` | Orígenes permitidos por CORS, separados por coma. Solo importa para clientes web: la app móvil no usa CORS. |

### Desplegar

**Render + Neon (camino previsto).** `render.yaml` en la raíz es un blueprint: en Render, *New → Blueprint*,
elegir este repo y completar `DATABASE_URL` (la cadena de conexión de Neon), `GROQ_API_KEY` y, si aplica,
`GOOGLE_CLIENT_ID`. El servicio aplica las migraciones y siembra las categorías en cada arranque. La URL que
entrega Render es el `API_BASE_URL` de la app móvil. En el plan gratuito el servicio se duerme tras un rato
sin uso y la primera petición tarda cerca de un minuto en responder.

**Cualquier otra plataforma con Docker.**

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
