# Pay & Check — Documentación técnica

App de finanzas personales para Android con un coach financiero. Un monorepo con dos piezas:
`backend/` (API REST en FastAPI) y `mobile/` (app Flutter).

## Índice

### Vigentes

- [iteracion-jurado-nov-2026.md](iteracion-jurado-nov-2026.md) — **Lo último:** auditoría como inversor, funciones para el jurado, análisis financiero, prueba en el teléfono y la fusión con `feature/sebastian-cierre`.
- [demo-guion.md](demo-guion.md) — Guion de la demo ante el jurado, preguntas difíciles y checklist.
- [analisis-financiero-nov-2026.md](analisis-financiero-nov-2026.md) — Costo de IA medido, proveedores comparados, escenarios a 36 meses y la ronda.
- [privacidad.md](privacidad.md) — Política de privacidad (Ley 1581): qué se guarda, qué se queda en el teléfono y qué sale a la IA.
- [planFinal.md](planFinal.md) — Plan final: estado real frente a Jira, tickets nuevos, diseño técnico y cronograma de la entrega.
- [planes.md](planes.md) — Planes y cupo de IA: qué incluye cada plan y qué cuenta como solicitud.
- [ia.md](ia.md) — IA en la app: casos de uso, qué datos salen a Groq, guardrails y métricas.
- [seguridad.md](seguridad.md) — Modelo de amenazas del backend con los controles que existen en el código.
- [decisiones/](decisiones/) — Registro de decisiones de arquitectura (ADR-001 a ADR-009).
- [reglas-calculo.md](reglas-calculo.md) — Fórmulas del resumen de presupuesto, casos especiales y casos calculados a mano.
- [informe-adversarial.md](informe-adversarial.md) — Resultados de la suite adversarial de *prompt injection* y huecos encontrados.
- [architecture.md](architecture.md) — Visión general, tech stack, capas, **Diagrama 1** (componentes) y **Diagrama 2** (flujo end-to-end).
- [architecture.pdf](architecture.pdf) — Versión en PDF de la arquitectura.
- [use-cases.md](use-cases.md) — **Diagrama de contexto** y **diagrama de casos de uso**, con trazabilidad a endpoints.
- [data-model.md](data-model.md) — **Diagrama 3** (ER), reglas de integridad y migraciones.
- [api.md](api.md) — Endpoints HTTP por router, autenticación y errores.
- [requirements.md](requirements.md) — Requisitos del producto.
- [setup.md](setup.md) — Puesta en marcha local, variables de entorno, tests, CI y despliegue.
- [sesion-codigo.md](sesion-codigo.md) — Guía de la sesión de código (PS-44): estructura, flujo de una petición y reglas de la IA.
- [diagramas/](diagramas/) — PNG de los diagramas (componentes, contexto, casos de uso, datos, secuencia).
- [negocio/](negocio/) — Modelo financiero (`.docx`) y plantilla de finanzas a 36 meses (`.xlsx`), con el costo de IA medido y la ronda de $150 M.
- [../README.md](../README.md) — README del repo: qué hace la app hoy.
- [../mobile/README.md](../mobile/README.md) — Cómo correr, probar y compilar la app móvil.

### Históricos

- [historico/](historico/) — Documentos de iteraciones anteriores; se conservan como referencia, no describen el estado actual.
- [historico/jira_planning.md](historico/jira_planning.md) — Backlog por épicas e historias de usuario (BDD) y mapeo al código (histórico).
- [historico/jira-import-nuevos.csv](historico/jira-import-nuevos.csv) — CSV de los tickets nuevos para importar al Jira.
- [historico/ESPECIFICACIONES-TECNICAS.md](historico/ESPECIFICACIONES-TECNICAS.md) — Especificaciones técnicas originales.
- [historico/mejoras.md](historico/mejoras.md) — Visión del producto (coach, gamificación, automatización).
- [historico/plan-app-movil.md](historico/plan-app-movil.md) — Plan de la app Android fase por fase.
- [historico/notas-iteracion-app-movil.md](historico/notas-iteracion-app-movil.md) — Estado, bugs y decisiones técnicas, iteración por iteración.
- [historico/plan-backend-gestion-gastos.md](historico/plan-backend-gestion-gastos.md) — Plan del backend original (terminado).

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
