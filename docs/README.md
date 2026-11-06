# Pay & Check — Documentación técnica

App de finanzas personales para Android con un coach financiero. Un monorepo con dos piezas:
`backend/` (API REST en FastAPI) y `mobile/` (app Flutter).

| Documento | Contenido |
|---|---|
| [architecture.md](architecture.md) | Visión general, tech stack, capas, **Diagrama 1** (componentes) y **Diagrama 2** (flujo end-to-end) |
| [use-cases.md](use-cases.md) | **Diagrama de contexto** y **diagrama de casos de uso**, con trazabilidad a endpoints |
| [data-model.md](data-model.md) | **Diagrama 3** (ER), reglas de integridad y migraciones |
| [api.md](api.md) | Endpoints HTTP por router, autenticación y errores |
| [setup.md](setup.md) | Puesta en marcha local, variables de entorno, tests, CI y despliegue |

Otros documentos del repo (históricos / de producto): `../README.md`, `../mejoras.md`,
`../plan-app-movil.md`, `../plan-backend-gestion-gastos.md`, `../notas-iteracion-app-movil.md`,
`../ESPECIFICACIONES-TECNICAS.md`, `../mobile/README.md`.

## Visión general

Pay & Check reduce la fricción de registrar dinero y responde una sola pregunta: **cuánto se puede gastar hoy**
(`disponible_por_dia`). Un presupuesto por periodo (`Budget`) más los ingresos (`Income`), menos gastos
(`Expense`) y lo apartado a metas (`GoalContribution`), dividido entre los días restantes.

Entradas de datos: formulario manual, texto escrito, voz (`speech_to_text`), foto de recibo (OCR en el teléfono
con ML Kit) y SMS del banco (canal nativo Android). En los cuatro últimos casos la IA (Groq) solo **propone** un
borrador estructurado; la persona lo confirma antes de guardarlo.

Dos reglas de diseño atraviesan el backend:

- **La IA redacta, no calcula.** Toda cifra sale de código determinista (`services/budget_calculator.py`,
  `budget_totals.py`, `patterns.py`, `gamification.py`). La salida del LLM pasa por guardrails
  (`services/coach.py`: `rompe_guardrails`, `inventa_cifras`) y siempre hay texto de respaldo, así que la app
  funciona sin `GROQ_API_KEY`.
- **Nada se auto-reporta ni se programa en el servidor.** Retos, puntos, insignias, vencimientos de gastos fijos
  y metas se recalculan "al vuelo" al consultar (`sync_gamification`, `recurring_expenses.pendientes`). No hay
  workers, colas ni crons. Los avisos son notificaciones locales en el teléfono.
