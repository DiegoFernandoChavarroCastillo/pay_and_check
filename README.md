# pay_and_check

App de finanzas personales con coach: registra gastos e ingresos con muy poca fricción (texto, voz, foto de
un recibo o SMS del banco), dice cuánto se puede gastar hoy, y acompaña con un coach que no regaña y con
retos e insignias verificados con datos reales.

El repo contiene el **backend** (`backend/`) y la **app móvil** en Flutter (`mobile/`, ver `mobile/README.md`).

## Documentos

| Documento | Qué contiene |
|---|---|
| `mobile/README.md` | Cómo correr, probar y compilar la app; sistema de diseño; cómo simular SMS del banco |
| `notas-iteracion-app-movil.md` | Estado actual, pendientes, bugs encontrados y decisiones técnicas, iteración por iteración |
| `plan-app-movil.md` | Plan de la app Android fase por fase, con lo ya hecho marcado |
| `mejoras.md` | Visión del producto (coach, gamificación, automatización) y qué parte está implementada |
| `plan-backend-gestion-gastos.md` | Plan del backend original (terminado) |

## Qué hace hoy

- **Presupuesto del periodo** y el número central de la app: el disponible por día.
- **Registro de movimientos**: manual, por frase escrita o dictada, por foto de un recibo (el texto se reconoce
  en el teléfono) y desde SMS del banco. La IA distingue gastos de ingresos ("mis papás me dieron 200.000").
- **Gastos fijos** semanales o mensuales (arriendo, recibos): el día que vencen avisa una notificación y
  quedan por pagar hasta que la persona confirma; ahí se descuentan.
- **Notificaciones** dentro de la app: pagos por hacer y movimientos detectados en SMS, para aprobar u omitir.
- **Coach**: check-in emocional diario, consejos con una acción de un toque, chat, reacción al registrar y
  reporte semanal. Nunca regaña, no recomienda inversiones y no puede inventar cifras.
- **Progreso**: metas de ahorro con dinero realmente apartado, 6 tipos de reto, 23 insignias, puntos y niveles.
- **Reportes**: análisis por semana con gráficas, reporte semanal y resumen mensual.

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

La primera vez (y tras traer migraciones nuevas) hay que aplicar las migraciones y sembrar las categorías:

```bash
docker compose exec api sh -c "alembic upgrade head && python -m app.db.seed"
```

La API queda en `http://localhost:8000` (docs interactivas en `/docs`). También se puede correr sin Docker
con `uv sync && uv run uvicorn app.main:app --reload`, apuntando `DATABASE_URL` a cualquier Postgres accesible
(local, Docker, o uno gestionado como [Neon](https://neon.tech/)).

### Qué expone la API

La documentación interactiva completa está en `/docs`. Resumen por módulo:

| Módulo | Endpoints | Para qué |
|---|---|---|
| Sesión | `/auth/register`, `/auth/login`, `/auth/google`, `/auth/refresh`, `/auth/me` (GET/PATCH/DELETE) | Cuenta, perfil (tono del coach, idioma, zona horaria) y borrado total de datos. El correo no distingue mayúsculas y la cuenta nace en el idioma que envía la app |
| Presupuesto | `/budgets`, `/budgets/active`, `/budgets/active/summary` | Presupuesto del periodo y el disponible por día |
| Movimientos | `/expenses` (+ `/parse`, `/parse-receipt`, `/from-text`), `/incomes` | Gastos e ingresos manuales o propuestos por IA desde texto, voz, recibo o SMS. `/parse` devuelve `tipo` (`gasto` o `ingreso`) |
| Categorías | `/categories` | Por defecto (compartidas) y propias. A una por defecto cada persona solo le puede fijar su propio límite |
| Gastos fijos | `/recurring-expenses` (+ `/pending`, `/{id}/pay`, `/{id}/skip`) | Pagos semanales o mensuales. No se registran solos: `/pending` lista los vencidos y `/pay` crea el gasto |
| Coach | `/checkins`, `/coach/reaction`, `/coach/insights`, `/coach/chat` | Check-in emocional, consejos accionables y chat |
| Gamificación | `/goals` (+ `/contributions`), `/challenges` (+ `/suggestions`), `/gamification/profile` | Metas con dinero realmente apartado, retos verificados, puntos, niveles e insignias |
| Reportes | `/reports/weekly`, `/reports/trends`, `/reports/monthly-wrapped` | Resumen semanal, gasto por semana para las gráficas y resumen mensual |

Dos reglas atraviesan todo el backend:

- **La IA redacta, no calcula.** Toda cifra sale de código determinista (`services/patterns.py`,
  `budget_totals.py`, `gamification.py`). Cada salida del modelo pasa por un filtro de guardrails y tiene un
  texto de respaldo, así que la app funciona igual aunque Groq no responda o falte `GROQ_API_KEY`. Los
  guardrails descartan el texto si trae lenguaje culposo, asesoría de inversión o **cifras que no estaban en
  el dato de origen** (`inventa_cifras` en `services/coach.py`). En el chat el filtro de cifras es más suave:
  pide una vez que la respuesta se rehaga, porque ahí la persona puede pedir una cuenta de verdad.
- **Nada se auto-reporta.** Metas, retos, puntos e insignias se recalculan "al vuelo" a partir de los gastos y
  check-ins reales; el libro de puntos es idempotente. No hay tareas programadas en el servidor: un reto
  vencido o un pago fijo pendiente se resuelve la próxima vez que la app consulta.

### La IA (Groq)

Todo pasa por `services/groq_client.py` y los prompts viven solo en `services/prompts.py`.

- Modelo: `openai/gpt-oss-20b` para extraer movimientos y para el coach (`MODEL` y `COACH_MODEL`).
- **Sin el modo JSON de Groq.** Con este modelo devolvía respuestas vacías de forma intermitente (error 400
  `json_validate_failed`). El JSON se pide en el prompt y lo extrae el backend, tolerando texto alrededor.
- **Razonamiento distinto según la tarea.** Mínimo (`low`) para extraer un movimiento, que es mecánico;
  `medium` para redactar (`COACH_REASONING`), porque con el mínimo el modelo copiaba el dato en vez de
  escribir el consejo.
- El plan gratuito de Groq limita a 8.000 tokens por minuto: alcanza para desarrollo, no para usuarios reales.

### Retos, insignias y puntos

Catálogo y reglas en `services/gamification.py`.

| Reto (7 días) | Se cumple cuando | Puntos |
|---|---|---|
| Reducir una categoría | Termina la semana gastando un porcentaje menos que la semana anterior | 50 |
| Una semana a tu ritmo | Termina la semana sin pasar del ritmo semanal del presupuesto | 50 |
| Días sin gasto opcional | Se acumulan 3 días sin gasto en categorías opcionales | 40 |
| Días registrando | Hay gasto registrado en 5 días distintos | 35 |
| Check-ins | Se hacen 5 check-ins | 30 |
| Aporte a una meta | Se aparta dinero para una meta | 30 |

Las categorías por defecto `transporte`, `salud` y `servicios` son de tipo fijo y no cuentan como gasto
opcional. Las 23 insignias premian constancia y uso real (rachas, check-ins, metas, retos, semanas en ritmo,
terminar un presupuesto sin pasarse, registrar por voz, recibo o SMS), nunca montos absolutos.

Para añadir una insignia: su texto en `INSIGNIAS` y su condición en `_desbloquear_insignias`; la app la
muestra sola. Un tipo de reto nuevo necesita además su medición en `_valor_reto`, sus textos y una migración
que amplíe la restricción `ck_challenges_tipo_valido`.

### Tests

```bash
cd backend
uv run pytest
```

La suite es hermética: no necesita `GROQ_API_KEY` real, `DATABASE_URL` real, ni conexión a internet
(`tests/conftest.py` usa SQLite en memoria y mockea las llamadas a Groq).

Son 108 tests. Como corren sobre SQLite, las migraciones de Alembic no se ejercitan ahí: se comprueban
aplicándolas en el Postgres de Docker (`docker compose exec api alembic upgrade head`).

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
