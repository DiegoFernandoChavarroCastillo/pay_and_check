# API HTTP

FastAPI; documentación interactiva autogenerada en `/docs` (Swagger) y `/redoc`. Todos los routers se registran
en `backend/app/main.py`. JSON en español (`monto`, `fecha`, `categoria`…).

## Convenciones

- **Auth**: `Authorization: Bearer <access_token>` en todo salvo `/health`, `/auth/register`, `/auth/login`,
  `/auth/google`, `/auth/refresh`. Sin cabecera → 401 (`HTTPBearer(auto_error=False)`).
- **Aislamiento**: un recurso de otro usuario responde 404.
- **Errores**: 422 `{"error": "validation_error", "detail": [...]}`; 500 `{"error": "internal_server_error", "detail": ...}`;
  400 fecha fuera de todo presupuesto; 502 Groq no disponible; 422 si el texto no es interpretable.
- **CORS**: orígenes de `CORS_ORIGINS` (coma-separados).
- **Healthcheck**: `GET /health` ejecuta `SELECT 1` (lo usa Render).

## Endpoints

### Sesión — `routers/auth.py` (`/auth`)

| Método | Ruta | Descripción |
|---|---|---|
| POST | `/auth/register` | Crea cuenta (email, contraseña, nombre, idioma). 201 |
| POST | `/auth/login` | Devuelve `access_token` + `refresh_token` |
| POST | `/auth/google` | Intercambia un `id_token` de Google por tokens propios |
| POST | `/auth/refresh` | Renueva tokens con el refresh token |
| GET / PATCH | `/auth/me` | Perfil: `coach_tone`, `idioma`, `zona_horaria` |
| DELETE | `/auth/me` | Borra la cuenta y todos sus datos. 204 |

### Presupuesto — `routers/budgets.py` (`/budgets`)

| Método | Ruta | Descripción |
|---|---|---|
| POST / GET | `/budgets` | Crear / listar |
| GET | `/budgets/active` | Presupuesto vigente (según `today_for(user)`) |
| GET | `/budgets/active/summary` | `BudgetSummary`: gastado, ingresos, apartado, `disponible_total`, `disponible_por_dia/semana`, `en_riesgo`, `fecha_proyectada_agotamiento` |
| PATCH | `/budgets/{budget_id}` | Editar |

### Categorías — `routers/categories.py` (`/categories`)

`GET` (por defecto + propias), `POST` (propia), `PATCH /{category_id}` (en una por defecto solo se fija el
límite personal, vía `CategoryLimit`).

### Movimientos — `routers/expenses.py`, `routers/incomes.py`

| Método | Ruta | Descripción |
|---|---|---|
| POST | `/expenses` | Crea gasto (`source`: manual, texto, voz, ocr, sms) |
| GET | `/expenses` | Filtros `category_id`, `fecha_desde`, `fecha_hasta` |
| POST | `/expenses/parse` | IA: texto → borrador `{tipo, monto, categoria, descripcion, fecha}`; **no guarda** |
| POST | `/expenses/parse-receipt` | IA: texto OCR de recibo → borrador; **no guarda** |
| POST | `/expenses/from-text` | Parsea y guarda en un paso (rechaza ingresos) |
| PATCH / DELETE | `/expenses/{expense_id}` | Editar / borrar |
| POST / GET | `/incomes` | Ingresos que amplían el presupuesto |
| PATCH / DELETE | `/incomes/{income_id}` | Editar / borrar |

### Gastos fijos — `routers/recurring_expenses.py` (`/recurring-expenses`)

`POST`, `GET`, `PATCH /{id}`, `DELETE /{id}`, `GET /pending` (vencidos sin pagar), `POST /{id}/pay`
(crea el gasto, 201), `POST /{id}/skip` (204).

### Coach — `routers/checkins.py`, `routers/coach.py`

| Método | Ruta | Descripción |
|---|---|---|
| POST / GET | `/checkins` | Check-in emocional (uno por día; repetir reemplaza) |
| POST | `/coach/reaction` | Mensaje tras registrar un gasto (`expense_id`) |
| GET | `/coach/insights?refresh=` | Consejos del día con acción de un toque (cache diaria en `coach_messages`) |
| GET / POST | `/coach/chat` | Historial / enviar mensaje |

### Metas, retos y gamificación — `routers/goals.py`, `routers/gamification.py`

| Método | Ruta | Descripción |
|---|---|---|
| POST / GET | `/goals` | Metas de ahorro |
| PATCH / DELETE | `/goals/{goal_id}` | Editar / borrar |
| POST | `/goals/{goal_id}/contributions` | Aporte (solo si hay disponible) |
| DELETE | `/goals/{goal_id}/contributions/{contribution_id}` | Revertir aporte |
| GET | `/challenges/suggestions` | Retos sugeridos según patrones |
| POST / GET | `/challenges` | Crear / listar (ejecuta `sync_gamification`) |
| DELETE | `/challenges/{challenge_id}` | Abandonar |
| GET | `/gamification/profile` | Puntos, nivel, racha, insignias |

### Reportes — `routers/reports.py` (`/reports`)

| Método | Ruta | Descripción |
|---|---|---|
| GET | `/reports/weekly` | Resumen semanal + recomendaciones (respaldo determinista si Groq falla); 404 sin presupuesto activo |
| GET | `/reports/trends?semanas=8` | Gasto por semana (2–26) para las gráficas |
| GET | `/reports/monthly-wrapped?mes=YYYY-MM` | Resumen mensual |

## Consumidores de eventos / CLI

No hay colas ni consumidores. Comandos operativos:

- `alembic upgrade head` — migraciones.
- `python -m app.db.seed` — siembra categorías por defecto (idempotente).
- `sh start.sh` — migra, siembra y arranca uvicorn (entrypoint del contenedor).

## Cliente móvil

`mobile/lib/data/api.dart` (`Api`) expone un método por endpoint; `core/api/api_client.dart` añade el
`Authorization` y renueva el token. El canal nativo `pay_and_check/sms` (`MainActivity.kt`) lee la bandeja SMS
con `Telephony.Sms.Inbox`; `SmsInbox` filtra los que parecen movimientos y los envía a `/expenses/parse`
(`source="sms"`) para confirmación.
