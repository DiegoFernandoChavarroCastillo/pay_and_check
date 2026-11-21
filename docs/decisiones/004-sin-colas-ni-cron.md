# ADR-004 · Sin colas ni *cron*: se calcula al consultar

- **Estado:** aceptada
- **Fecha:** 2026-11-18

## Contexto

Varias funciones parecen pedir trabajos programados: otorgar puntos y rachas, registrar gastos fijos cada mes,
reiniciar el cupo de IA el día 1, recordar a la persona que registre sus gastos. El backend corre en el plan
gratuito de Render, que se duerme sin tráfico ([`render.yaml`](../../render.yaml)): un *cron* dentro del proceso
no correría mientras está dormido, y un *worker* aparte es otro servicio que desplegar.

## Decisión

No hay colas, *workers* ni *cron* en el backend. Todo se calcula cuando la persona lo consulta:

| Función | Cómo se resuelve | Dónde |
|---|---|---|
| Puntos, rachas, retos, insignias | `sync_gamification` recalcula al pedir el perfil o los retos; el libro `PointEvent` es idempotente (restricciones únicas + `IntegrityError` → se descarta el intento duplicado) | [`services/gamification.py`](../../backend/app/services/gamification.py), [`routers/gamification.py`](../../backend/app/routers/gamification.py) |
| Gastos fijos "por pagar" | Se calcula al vuelo el vencimiento más reciente sin gasto ni omisión; no se registra nada solo, la persona confirma | [`services/recurring_expenses.py`](../../backend/app/services/recurring_expenses.py) |
| Reinicio del cupo de IA | No hay reinicio: se cuenta `ai_usage` con `WHERE mes = <mes actual de la persona>` | `usadas_en_el_mes` en [`services/ia_uso.py`](../../backend/app/services/ia_uso.py) |
| Consejos del día | Caché por día, tono e idioma en `coach_messages`; se generan en la primera consulta del día | `insights_del_dia` en [`services/coach.py`](../../backend/app/services/coach.py) |
| Recordatorios | Los programa la app en el teléfono (`zonedSchedule`) | [`mobile/lib/core/notifications.dart`](../../mobile/lib/core/notifications.dart) |

Verificado: no hay `celery`, `apscheduler`, `BackgroundTasks` ni Redis en
[`backend/pyproject.toml`](../../backend/pyproject.toml) ni en `backend/app/`.

## Alternativas consideradas

- **Cron de Render o GitHub Actions programado.** Descartado: otro componente que configurar y vigilar, y en
  el plan gratuito no aporta frente a calcular al consultar.
- **Cola + *worker* (Celery/RQ + Redis).** Descartado para el piloto; es la fase C del plan de escalabilidad
  ([ADR-001](001-monolito-modular.md)).
- **`BackgroundTasks` de FastAPI.** Corren en el mismo proceso tras responder; no sirven para tareas
  programadas y se pierden si el contenedor se reinicia.

## Consecuencias

- Nada se pierde porque el servidor estuvo dormido: el estado se reconstruye desde los datos.
- Las consultas cuestan más: la gamificación y los resúmenes se recalculan en cada petición. Es el segundo
  cuello de botella al crecer ([ADR-001](001-monolito-modular.md)).
- La idempotencia es obligatoria: dos peticiones simultáneas del mismo usuario (la app pide perfil y retos a la
  vez) intentan otorgar lo mismo; lo frenan las restricciones únicas.
- El reporte semanal y el *wrapped* no se cachean: cada consulta llama a Groq y gasta una solicitud
  ([`routers/reports.py`](../../backend/app/routers/reports.py)).
- Un recordatorio depende de que el teléfono tenga la app instalada y las notificaciones permitidas.
