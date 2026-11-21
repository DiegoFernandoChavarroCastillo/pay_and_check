# ADR-001 · Monolito modular en lugar de microservicios

- **Estado:** aceptada
- **Fecha:** 2026-11-18

## Contexto

Pay&Check es un producto en fase piloto con un equipo de 5 personas y un solo equipo de despliegue. El backend es una
sola API FastAPI ([`backend/app/main.py`](../../backend/app/main.py)) que monta 12 routers y se despliega como un
único servicio web Docker en Render ([`render.yaml`](../../render.yaml), `plan: free`, región `ohio`) contra una
base PostgreSQL externa en Neon (ver [ADR-006](006-postgres-neon-alembic.md)).

El código ya está separado en capas:

| Capa | Carpeta | Ejemplos |
|---|---|---|
| HTTP | [`backend/app/routers/`](../../backend/app/routers/) | `expenses.py`, `coach.py`, `plans.py` |
| Negocio | [`backend/app/services/`](../../backend/app/services/) | `budget_calculator.py`, `coach.py`, `groq_client.py`, `gamification.py`, `planes.py`, `ia_seguridad.py` |
| Datos | [`backend/app/models/`](../../backend/app/models/) | SQLModel, una tabla por archivo |
| Transversal | [`backend/app/core/`](../../backend/app/core/) | `config.py`, `security.py`, `time.py`, `rate_limit.py` |

## Decisión

Un **monolito modular**: un proceso, un despliegue, una base de datos, con los límites entre dominios marcados
por módulos (routers → services → models) y no por la red.

## Alternativas consideradas

- **Microservicios** (auth, finanzas, coach/IA, planes). Descartado: agregan red, despliegue, configuración y
  observabilidad distribuidos, y transacciones entre servicios (p. ej. `planes.cambiar_plan` toca usuarios,
  grupos, suscripciones y códigos en una sola transacción, [`services/planes.py`](../../backend/app/services/planes.py)).
  Con un equipo y un piloto no compran nada.
- **Serverless por endpoint.** Descartado: el plan gratuito de Render con Docker ya cubre el piloto y el arranque
  en frío sería igual o peor.

## Consecuencias

- Un solo `alembic upgrade head` y un solo arranque ([`backend/start.sh`](../../backend/start.sh)).
- Las pruebas corren todo el backend en proceso, con SQLite en memoria
  ([`backend/tests/conftest.py`](../../backend/tests/conftest.py)), sin levantar servicios.
- Todo comparte el mismo pool de conexiones ([`backend/app/db/session.py`](../../backend/app/db/session.py)): una
  carga alta en un dominio (p. ej. el coach) afecta a los demás.

## ¿Un monolito escala?

**Respuesta corta:** escala horizontalmente con un cambio acotado (el rate limit), y verticalmente sin cambios.
Lo que se rompe primero no es el monolito sino sus dependencias externas.

### Lo que sí escala hoy

- **Autenticación sin sesión en el servidor.** JWT firmado con `JWT_SECRET`
  ([`backend/app/core/security.py`](../../backend/app/core/security.py)); cada petición resuelve el usuario desde
  el token y la base ([`backend/app/deps.py`](../../backend/app/deps.py)). Cualquier instancia puede atender
  cualquier petición.
- **El estado de negocio está en Postgres:** gastos, presupuestos, puntos (`PointEvent`), consejos cacheados del
  día (`coach_messages`), uso y cupo de IA (`ai_usage`, contado con `WHERE mes = …` en
  [`services/ia_uso.py`](../../backend/app/services/ia_uso.py)).
- **Sin trabajos en segundo plano** que haya que coordinar entre instancias ([ADR-004](004-sin-colas-ni-cron.md)).
- **Los límites de un futuro servicio ya existen como módulos.** El servicio de IA de la fase B tendría como
  frontera natural [`services/groq_client.py`](../../backend/app/services/groq_client.py), por donde pasan todas
  las llamadas a Groq (`_chat()`).

### Lo que NO es *stateless*: el rate limit vive en memoria

El diseño original dice que la API es *stateless* y que basta con poner N instancias detrás de un balanceador
"sin cambiar código". **El código no cumple eso del todo:** los límites de tasa (20 solicitudes de IA por minuto
por persona; 10 fallos de login por IP o email en 5 minutos) se guardan en un diccionario del proceso
([`backend/app/core/rate_limit.py`](../../backend/app/core/rate_limit.py), clase `LimiteDeTasa`, instancias
`LIMITE_IA` y `LIMITE_LOGIN`). Consecuencias, tal como las documenta el propio módulo:

- se reinician con cada despliegue o reinicio del contenedor;
- con N instancias, cada una lleva su propia cuenta y el límite efectivo se multiplica por N.

Para el piloto, con una sola instancia, alcanza. **A escala, el rate limit pasa a un almacén compartido
(Redis)** con la misma interfaz (`consumir`, `espera`, `registrar`, `olvidar`); es el único cambio de código que
exige escalar horizontalmente. Hoy no hay ninguna dependencia de Redis en
[`backend/pyproject.toml`](../../backend/pyproject.toml).

El cupo mensual de IA sí es compartido (está en Postgres), pero su revisión y su registro no son atómicos: dos
peticiones simultáneas pueden pasarse del tope por unas pocas llamadas (comentario en `cupo_agotado`,
[`services/ia_uso.py`](../../backend/app/services/ia_uso.py)). Es un tope de costo, no de seguridad.

### Lo que se rompería primero (en orden)

1. **El límite de tokens por minuto de Groq.** El modelo financiero estima ~54.000 tokens/min en la hora pico del
   mes 12 frente a 8.000 del plan gratis. *Esta cifra viene del modelo financiero
   (`docs/negocio/`), no del código.* El cliente no reintenta (`GROQ_MAX_REINTENTOS = 0`, `GROQ_TIMEOUT_S = 15`
   en `groq_client.py`): ante un 429 la persona recibe el texto de respaldo, no un error.
2. **Conexiones y latencia de Neon.** Cada petición hace varias consultas y los resúmenes se calculan al vuelo
   (`summary_for` en [`services/budget_totals.py`](../../backend/app/services/budget_totals.py), la gamificación
   en `sync_gamification`). El engine usa el pool por defecto de SQLAlchemy con `pool_pre_ping` y
   `pool_recycle=300` ([`db/session.py`](../../backend/app/db/session.py)); no hay *pooler* configurado en el código.
3. **El plan gratuito de Render:** una instancia, y se duerme sin tráfico (arranque en frío). Está en
   [`render.yaml`](../../render.yaml) (`plan: free`) y en `docs/requirements.md`.

### Plan de migración por disparadores (no por calendario)

| Fase | Disparador medible | Acción |
|---|---|---|
| A · Hoy | — | Monolito modular; escalar verticalmente (planes de pago de Render y Neon, un escalón por cada 3.000 usuarios pagos según el modelo financiero) |
| B | > 3.000 usuarios pagos, o p95 > 800 ms, o 429 de Groq > 1 % | Rate limit a Redis; instancias adicionales de la API; extraer un **servicio de IA** (cola + caché + cupos + proveedor de respaldo) detrás de la misma interfaz de `groq_client` |
| C | Reportes lentos o carga de lectura alta | Réplica de lectura y precálculo de resúmenes en un *worker* (recordatorios, gastos fijos, *wrapped*) |
| D | Equipos o dominios independientes | Separar dominios por contexto (cuentas/planes, finanzas, coach) solo si hay un dueño distinto |

Cada fase es reversible y no exige reescribir la app móvil: la API pública no cambia.

### Cómo se mide cada disparador hoy

| Disparador | ¿Se puede medir con lo que hay en el repo? |
|---|---|
| Usuarios pagos | **Sí.** Filas de `subscriptions` con plan `premium`, `familiar` o `institucional` ([`models/plan.py`](../../backend/app/models/plan.py)); sin fila es Gratis. |
| p95 de la API > 800 ms | **No.** No hay middleware de métricas ni APM en el backend; habría que tomarlo de las métricas de Render o agregar instrumentación. |
| 429 de Groq > 1 % | **Parcial.** `ai_usage` guarda `exito=False` y `latencia_ms` de cada llamada fallida ([`models/ai_usage.py`](../../backend/app/models/ai_usage.py)) y [`db/reporte_ia.py`](../../backend/app/db/reporte_ia.py) resume por tarea, pero **no se guarda el código de error**: un 429 no se distingue de una caída o un *timeout*. |
| Latencia de la IA | **Sí.** `latencia_ms` promedio por tarea con `uv run python -m app.db.reporte_ia`. |
