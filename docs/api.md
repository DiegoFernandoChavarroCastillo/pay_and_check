# API HTTP

FastAPI; documentación interactiva autogenerada en `/docs` (Swagger) y `/redoc`. Todos los routers se registran
en `backend/app/main.py`. JSON en español (`monto`, `fecha`, `categoria`…).

## Convenciones

- **Auth**: `Authorization: Bearer <access_token>` en todo salvo `/health`, `/auth/register`, `/auth/login`,
  `/auth/google`, `/auth/refresh`. Sin cabecera → 401 (`HTTPBearer(auto_error=False)`).
- **Aislamiento**: un recurso de otro usuario responde 404.
- **Errores**: 422 `{"error": "validation_error", "detail": [...]}`; 500 `{"error": "internal_server_error", "detail": ...}`;
  400 fecha fuera de todo presupuesto; 422 si el texto no es interpretable; 503 si Groq no está disponible
  (el registro con IA lleva al formulario manual; el chat responde su texto de respaldo, sin guardar el turno);
  402 si se agotó el cupo mensual de IA; 429 con `Retry-After` si se pasan 20 solicitudes de IA por minuto o 10
  intentos de login fallidos en 5 minutos.
- **Códigos de éxito**: los `POST` que crean un recurso responden 201 (`/auth/register`, `/budgets`,
  `/categories`, `/expenses`, `/expenses/from-text`, `/incomes`, `/recurring-expenses`,
  `/recurring-expenses/{id}/pay`, `/goals`, `/goals/{goal_id}/contributions`, `/challenges`); los `DELETE` y
  `POST /recurring-expenses/{id}/skip` responden 204 sin cuerpo. El resto responde 200, incluidos
  `POST /checkins` y `DELETE /goals/{goal_id}/contributions/{contribution_id}` (devuelve la meta actualizada).
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
| POST | `/budgets/active/simulate` | «¿Me alcanza?» de contado (`monto`, `categoria_id?`): número del día antes y después, nueva fecha de agotamiento e impacto en la meta activa. Sin IA ni cupo |
| POST | `/budgets/simulate-credit` | «¿Me alcanza?» a cuotas (`monto`, `cuotas`, `tasa_ea`): cuota fija (sistema francés), total, intereses, tasa mensual y cómo baja el número del día. Sin IA |

### Gastos que vienen — `routers/planned.py` (`/planned-expenses`)

`GET`, `POST` (descripción, monto, fecha; 201), `POST /{id}/done` y `DELETE /{id}`. Cada uno trae cuánto apartar
por semana y si el ritmo de hoy lo permite; el coach lo menciona a 45 días (patrón `gasto_previsto`).

### Categorías — `routers/categories.py` (`/categories`)

`GET` (por defecto + propias), `POST` (propia), `PATCH /{category_id}` (en una por defecto solo se fija el
límite personal, vía `CategoryLimit`).

### Movimientos — `routers/expenses.py`, `routers/incomes.py`

| Método | Ruta | Descripción |
|---|---|---|
| POST | `/expenses` | Crea gasto (`source`: manual, texto, voz, ocr, sms) |
| GET | `/expenses` | Filtros `category_id`, `fecha_desde`, `fecha_hasta` |
| POST | `/expenses/parse` | IA: texto → borrador `{tipo, monto, categoria, descripcion, fecha}` y `adicionales` (hasta 5 movimientos por frase, una sola solicitud de cupo); **no guarda** |
| POST | `/expenses/parse-receipt` | IA: texto OCR de recibo → borrador; **no guarda** |
| POST | `/expenses/from-text` | Parsea y guarda en un paso (rechaza ingresos); con varios movimientos en la frase, guarda todos |
| POST | `/expenses/split` | Vaca: guarda la parte propia y crea un «por cobrar» por persona (201) |
| GET | `/receivables` | Lo que te deben (pendientes y total) |
| POST | `/receivables/{id}/paid` | Marca un cobro como pagado |
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
| GET / POST | `/coach/chat` | Historial / enviar mensaje. La respuesta puede traer `accion` (p. ej. `crear_meta` con el monto y la fecha calculados por `simulador.py`), que no se guarda |

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
| GET | `/reports/trends?semanas=8` | Gasto por semana (2–26) para las gráficas; `variacion_vs_semana_anterior_pct` compara los mismos días (lunes a hoy) |
| GET | `/reports/monthly-wrapped?mes=YYYY-MM` | Resumen mensual |
| GET | `/reports/repeated` | Gastos hormiga (≤ 12.000, categoría opcional, 4+ veces) y suscripciones (2+ meses con montos parecidos; nunca vivienda, deudas, estudio ni servicios), con su costo al mes y al semestre |

### Planes y suscripción — `routers/plans.py`

Planes simulados, sin pasarela de pago (ver [planes.md](planes.md)).

| Método | Ruta | Descripción |
|---|---|---|
| GET | `/plans` | Catálogo de planes con su cupo mensual de IA y sus `funciones` |
| GET | `/me/subscription` | Plan actual, cupo usado y restante, fecha de reinicio y datos de la familia si aplica |
| PUT | `/me/subscription` | Cambia de plan (`plan`); 422 si el cambio no es válido |
| PUT | `/me/subscription/share-progress` | Un integrante de la familia decide si comparte su progreso con el titular |
| GET | `/me/family/progress` | Para el titular: racha, constancia, metas y si el presupuesto alcanza de cada integrante que comparte. Nunca gastos |
| POST | `/me/subscription/redeem` | Canjea un código de convenio (activa Institucional) o familiar (une a una familia); 404 si el código no existe, 422 si no se puede usar, 429 tras 5 códigos inválidos en 15 minutos |

### Universidad — `routers/support.py`, `routers/panel.py`

| Método | Ruta | Descripción |
|---|---|---|
| GET | `/support` | Apoyos de la universidad de la persona (si tiene plan Institucional) y si conviene sugerirlos |
| POST | `/support/{id}/interest` | «Me interesa»; la universidad solo ve el conteo agregado |
| GET | `/panel/{org_id}?token=…` | Panel web de Bienestar (HTML, sin JWT, con el token de la organización): uso, estrés financiero, presupuestos en riesgo, metas, ánimo, categorías, tendencia e interés en los apoyos. Anonimato k ≥ 5; token inválido → 403 |

La captura automática (`POST /expenses` con `source = "sms"`) responde **402** `SIN_CAPTURA_AUTOMATICA` en el plan
Gratis.

## Consumidores de eventos / CLI

No hay colas ni consumidores. Comandos operativos:

- `alembic upgrade head` — migraciones.
- `python -m app.db.seed` — siembra categorías por defecto (idempotente).
- `python -m app.db.seed_demo` — cuentas de demo, una por plan, y la universidad con su panel (README).
- `sh start.sh` — migra, siembra y arranca uvicorn (entrypoint del contenedor).

## Cliente móvil

`mobile/lib/data/api.dart` (`Api`) expone un método por endpoint; `core/api/api_client.dart` añade el
`Authorization` y renueva el token. El canal nativo `pay_and_check/sms` (`MainActivity.kt`) lee la bandeja SMS
con `Telephony.Sms.Inbox`; `SmsInbox` filtra los que parecen movimientos y los envía a `/expenses/parse`
(`source="sms"`) para confirmación.
