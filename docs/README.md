# Pay & Check — Documentación técnica

App de finanzas personales con un coach financiero, para Android y para la web (iPhone y computador). Un monorepo con dos piezas: `backend/` (API REST en FastAPI) y `mobile/` (app Flutter, compilada para
Android y para web).

## Índice

### Producto
- [requirements.md](requirements.md) — Requisitos funcionales y no funcionales.
- [use-cases.md](use-cases.md) — Diagrama de contexto, casos de uso y trazabilidad a endpoints.
- [planes.md](planes.md) — Planes y cupo de IA: qué incluye cada plan y qué cuenta como solicitud.
- [reglas-calculo.md](reglas-calculo.md) — Fórmulas del resumen de presupuesto, casos especiales y ejemplos calculados a mano.
- [privacidad.md](privacidad.md) — Política de privacidad (Ley 1581): qué se guarda, qué se queda en el teléfono y qué sale a la IA.

### Arquitectura
- [architecture.md](architecture.md) — Stack, capas, componentes, despliegue, flujo de un registro y autenticación.
- [data-model.md](data-model.md) — Modelo entidad-relación, reglas de integridad y migraciones.
- [api.md](api.md) — Endpoints HTTP por router, autenticación y errores.
- [ia.md](ia.md) — IA en la app: casos de uso, datos que salen a Groq, guardrails y métricas.
- [decisiones/](decisiones/) — Registro de decisiones de arquitectura (ADR-001 a ADR-011).
- [diagramas/](diagramas/) — Diagramas en PNG y sus fuentes.

### Seguridad
- [seguridad.md](seguridad.md) — Modelo de amenazas con los controles que existen en el código.
- [informe-adversarial.md](informe-adversarial.md) — Resultados de la suite de *prompt injection*.

### Operación
- [setup.md](setup.md) — Puesta en marcha local, variables de entorno, pruebas y CI.
- [despliegue.md](despliegue.md) — Producción: API en AWS, web en Vercel, APK en GitHub Releases y Google Sign-In.
- [pendientes.md](pendientes.md) — Trabajo pendiente y deuda técnica conocida.

### Negocio
- [negocio/](negocio/) — Análisis financiero, modelo a 36 meses y documento del modelo de negocio.

### Otros
- [../README.md](../README.md) — Qué hace la app, cómo probarla y cómo correrla.
- [../mobile/README.md](../mobile/README.md) — App Flutter: correr, probar, compilar el APK y la versión web.

## Visión general

Pay & Check reduce la fricción de registrar dinero y responde una sola pregunta: **cuánto se puede gastar hoy**
(`disponible_por_dia`). Un presupuesto por periodo (`Budget`) más los ingresos (`Income`), menos gastos
(`Expense`) y lo apartado a metas (`GoalContribution`), dividido entre los días restantes.

Entradas de datos: formulario manual, texto escrito, voz (`speech_to_text`), foto de recibo (OCR en el teléfono
con ML Kit) y SMS del banco (canal nativo Android). En la versión web solo existen el formulario, el texto y la voz
([ADR-010](decisiones/010-version-web-respaldo.md)). En los cuatro últimos casos la IA (Groq) solo **propone** un
borrador estructurado; la persona lo confirma antes de guardarlo.

Dos reglas de diseño atraviesan el backend:

- **La IA redacta, no calcula.** Toda cifra sale de código determinista (`services/budget_calculator.py`,
  `budget_totals.py`, `patterns.py`, `gamification.py`). La salida del LLM pasa por guardrails
  (`services/coach.py`: `rompe_guardrails`, `inventa_cifras`) y siempre hay texto de respaldo, así que la app
  funciona sin `GROQ_API_KEY`.
- **Nada se auto-reporta ni se programa en el servidor.** Retos, puntos, insignias, vencimientos de gastos fijos
  y metas se recalculan "al vuelo" al consultar (`sync_gamification`, `recurring_expenses.pendientes`). No hay
  workers, colas ni crons. Los avisos son notificaciones locales en el teléfono.
