# Registro de decisiones (ADR)

Cada archivo es una decisión técnica de Pay&Check con el formato **contexto / decisión / alternativas /
consecuencias** y cita los archivos del repo donde se ve. Lo que el plan pedía y el código no hace está dicho en
cada ADR, no se da por hecho. Ticket de origen: PS-106.

| # | Decisión | Estado |
|---|---|---|
| [001](001-monolito-modular.md) | Monolito modular en lugar de microservicios. Incluye **¿un monolito escala?**, los disparadores medibles y el rate limit en memoria (a escala: Redis) | aceptada |
| [002](002-groq-gpt-oss-20b.md) | Groq con `openai/gpt-oss-20b`; por qué no Llama 3.1 8B | aceptada |
| [003](003-ia-redacta-no-calcula.md) | La IA redacta, no calcula: cálculo determinista, guardrails y textos de respaldo | aceptada |
| [004](004-sin-colas-ni-cron.md) | Sin colas ni *cron*: gamificación, gastos fijos y cupos se calculan al consultar | aceptada |
| [005](005-zona-horaria-del-usuario.md) | El "hoy" es el de la persona (`today_for`), no el del servidor | aceptada |
| [006](006-postgres-neon-alembic.md) | PostgreSQL en Neon y migraciones con Alembic | aceptada |
| [007](007-distribucion-apk.md) | Distribución por APK en el piloto, Google Play después | aceptada |
| [008](008-planes-simulados-cupo-ia.md) | Planes simulados en el piloto y cupo de IA por plan | aceptada |
| [009](009-capas-seguridad-ia.md) | Capas de seguridad de la IA | aceptada |
| [010](010-version-web-respaldo.md) | Versión web (Flutter) en Vercel como respaldo para iPhone y PC; qué se oculta y el diseño adaptable | aceptada |
| [011](011-backend-aws-ec2.md) | Backend de producción en AWS EC2 con Caddy; Render queda de respaldo | aceptada |

## Diferencias entre el plan y el código

Encontradas al verificar cada ADR contra el código:

- **La API no es del todo *stateless*:** el rate limit vive en la memoria del proceso
  (`backend/app/core/rate_limit.py`). Con más de una instancia hay que moverlo a Redis (ADR-001).
- **Dos disparadores de escalado no se miden hoy:** no hay métrica de p95 de la API y `ai_usage` no distingue
  un 429 de Groq de otro fallo (ADR-001).
- **"Modelo único por tarea":** hoy `COACH_MODEL = MODEL`, un solo modelo para todo (ADR-002).
- **"El parseo no guarda nada":** `POST /expenses/from-text` guarda en un paso; la app no lo usa (ADR-003, ADR-009).
- **El rechazo fuera de alcance lo aplica el backend**, no la app (ADR-009).
- **No se verifica el idioma** de la salida del coach (ADR-009).
- **Google Play Billing:** solo está descrito, no implementado; las suscripciones no vencen (ADR-008).
- **El backend de AWS se actualiza a mano:** no hay despliegue automático ni está documentada la instalación (ADR-011).

## Cómo agregar una decisión

1. Copiar un ADR existente como `NNN-titulo-corto.md` con el número siguiente.
2. Llenar contexto, decisión, alternativas y consecuencias, citando archivos con enlaces relativos.
3. Si reemplaza a otra, marcar la anterior como `reemplazada por ADR-NNN` en vez de borrarla.
4. Agregar la fila a esta tabla.
