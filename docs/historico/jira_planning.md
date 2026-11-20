# Planificación de backlog (Jira / Azure DevOps)

Generado comparando el código real (`backend/app`, `mobile/lib`, `backend/tests`, `mobile/test`) contra la visión
de producto de `mejoras.md`, `plan-app-movil.md` y `notas-iteracion-app-movil.md`. El repo no tiene carpeta
`/src`: el código fuente está en `backend/app/` (FastAPI) y `mobile/lib/` (Flutter).

**Convenciones para importadores**

- Cada HU es un bloque que empieza con `### HU-XXX` y termina con `---`; los campos son líneas `**Campo:** valor`
  con nombres fijos: `Épica`, `Estado`, `Prioridad`, `Criterios de aceptación`, `Sub-tareas`, `Código`.
- Los estados válidos son exactamente `COMPLETADA`, `EN PROGRESO / PARCIAL` y `PENDIENTE`.
- Al final hay un índice CSV (`HU,Epica,Titulo,Estado,Prioridad`) listo para importar.
- En las HU `COMPLETADA` las sub-tareas son solo las de refuerzo (si las hay); el resto del trabajo ya existe.
- Las HU `PENDIENTE` marcadas con *(visión)* salen de `mejoras.md`; sus rutas y archivos son propuestos, no existen.

## Resumen

| Épica | HU | Completadas | Parciales | Pendientes |
|---|---|---|---|---|
| EP-01 Cuenta y seguridad | 5 | 3 | 2 | 0 |
| EP-02 Presupuesto y categorías | 4 | 4 | 0 | 0 |
| EP-03 Registro de movimientos | 7 | 5 | 2 | 0 |
| EP-04 Coach financiero | 6 | 5 | 1 | 0 |
| EP-05 Metas, retos y gamificación | 6 | 4 | 0 | 2 |
| EP-06 Reportes | 3 | 3 | 0 | 0 |
| EP-07 Automatización e integraciones | 3 | 0 | 0 | 3 |
| EP-08 Lanzamiento y operación | 5 | 0 | 2 | 3 |

---

## EP-01: Cuenta y seguridad

### HU-001: Persona nueva quiero registrarme e iniciar sesión con correo y contraseña para usar mis datos en cualquier sesión
**Épica:** EP-01: Cuenta y seguridad
**Estado:** [COMPLETADA]
**Prioridad:** Alta
**Criterios de aceptación:**
- Scenario 1: Given un correo no registrado, When envío `POST /auth/register` con nombre, correo, contraseña e idioma, Then recibo 201 y la cuenta nace en ese idioma.
- Scenario 2: Given una cuenta existente, When envío `POST /auth/login` con credenciales correctas, Then recibo `access_token` y `refresh_token`.
- Scenario 3: Given un correo con otras mayúsculas, When me registro o inicio sesión, Then se trata como el mismo correo (se guarda en minúsculas).
- Scenario 4: Given credenciales incorrectas, When inicio sesión, Then recibo 401.
**Sub-tareas:**
- [Backend] Limitar intentos de login (rate limiting) — hoy no existe.
- [Backend] Política mínima de contraseña en `RegisterRequest`.
- [Tests] Casos de contraseña débil y de intentos repetidos.
**Código:** `backend/app/routers/auth.py` (`register`, `login`), `backend/app/schemas/auth.py`, `backend/app/core/security.py` (`hash_password`, `create_access_token`), `backend/app/models/user.py`, `backend/alembic/versions/a1d4e7b90c33_correos_en_minusculas.py`, `backend/tests/test_auth.py`, `mobile/lib/features/auth/auth_screens.dart`

---

### HU-002: Persona usuaria quiero que mi sesión se renueve sola para no volver a iniciar sesión cada hora
**Épica:** EP-01: Cuenta y seguridad
**Estado:** [COMPLETADA]
**Prioridad:** Alta
**Criterios de aceptación:**
- Scenario 1: Given un access token vencido y un refresh token válido, When la app recibe 401, Then llama a `POST /auth/refresh` y reintenta la petición.
- Scenario 2: Given un refresh token, When lo uso como access token, Then recibo 401 (el claim `type` lo impide).
- Scenario 3: Given que cierro la app, When la reabro, Then la sesión sigue activa (tokens en almacén seguro).
**Sub-tareas:**
- [Backend] Revocación de refresh tokens (tabla de tokens): hoy cerrar sesión solo borra los tokens del teléfono.
**Código:** `backend/app/routers/auth.py` (`refresh`), `backend/app/core/security.py` (`decode_refresh_token`), `backend/app/deps.py`, `mobile/lib/core/api/api_client.dart` (`SecureTokenStorage`), `mobile/lib/data/session.dart`, `backend/tests/test_mobile_basics.py`

---

### HU-003: Persona usuaria quiero iniciar sesión con Google para entrar sin crear contraseña
**Épica:** EP-01: Cuenta y seguridad
**Estado:** [EN PROGRESO / PARCIAL]
**Prioridad:** Media
**Criterios de aceptación:**
- Scenario 1: Given un `id_token` válido de Google, When envío `POST /auth/google`, Then recibo tokens propios y se crea la cuenta si no existía.
- Scenario 2: Given `GOOGLE_CLIENT_ID` vacío, When envío cualquier token, Then recibo 401 explícito.
- Scenario 3: Given `GOOGLE_SERVER_CLIENT_ID` sin definir en la app, When abro el login, Then el botón "Continuar con Google" no aparece.
**Sub-tareas:**
- [Infra] Crear el Client ID de Google (web + Android) y registrar la huella SHA-1 del keystore.
- [Config] Cargar `GOOGLE_CLIENT_ID` en Render y `GOOGLE_SERVER_CLIENT_ID` en el workflow de release.
- [QA] Probar el flujo completo en un teléfono real (hoy "sin probar").
**Código:** `backend/app/routers/auth.py` (`login_google`), `backend/app/services/google_auth.py`, `backend/app/models/user.py` (`google_id`), `mobile/lib/core/config/app_config.dart`, `mobile/lib/features/auth/auth_screens.dart`, `backend/tests/test_auth.py`

---

### HU-004: Persona usuaria quiero configurar mi perfil (tono del coach, idioma, zona horaria) para que la app se adapte a mí
**Épica:** EP-01: Cuenta y seguridad
**Estado:** [COMPLETADA]
**Prioridad:** Media
**Criterios de aceptación:**
- Scenario 1: Given una sesión activa, When envío `PATCH /auth/me` con `coach_tone`, `idioma` o `zona_horaria`, Then el cambio se guarda y se refleja en la respuesta.
- Scenario 2: Given una zona horaria, When calculo "hoy", Then se usa `today_for(user)` y no la fecha del servidor.
- Scenario 3: Given que cambio el idioma, When navego la app, Then la interfaz y los textos del coach cambian a es/en.
**Sub-tareas:** Ninguna pendiente (`UserUpdate` ya restringe `coach_tone` e `idioma` con los tipos `CoachTone` e `Idioma`).
**Código:** `backend/app/routers/auth.py` (`update_me`), `backend/app/schemas/user.py`, `backend/app/core/time.py` (`today_for`), `mobile/lib/features/profile/profile_screen.dart`, `mobile/lib/l10n/app_es.arb`, `mobile/lib/l10n/app_en.arb`

---

### HU-005: Persona usuaria quiero borrar mi cuenta y todos mis datos para controlar mi privacidad
**Épica:** EP-01: Cuenta y seguridad
**Estado:** [EN PROGRESO / PARCIAL]
**Prioridad:** Alta
**Criterios de aceptación:**
- Scenario 1: Given una sesión activa, When envío `DELETE /auth/me`, Then recibo 204 y desaparecen mis gastos, ingresos, presupuestos, metas, retos, check-ins y mensajes del coach.
- Scenario 2: Given que borré la cuenta, When uso mi token anterior, Then recibo 401.
- Scenario 3: Given que otra persona usa la misma categoría por defecto, When borro mi cuenta, Then sus datos no cambian.
**Sub-tareas:**
- [Mobile] Confirmación en dos pasos y aviso de consentimiento (ver HU-037).
- [Tests] Verificar que el borrado cubre las 14 tablas si se agregan modelos nuevos (test que recorra `SQLModel.metadata`).
**Código:** `backend/app/routers/auth.py` (`delete_me`), `mobile/lib/features/profile/profile_screen.dart`, `backend/tests/test_mobile_basics.py`

---

## EP-02: Presupuesto y categorías

### HU-006: Persona usuaria quiero definir un presupuesto por periodo para saber cuánto dinero tengo que repartir
**Épica:** EP-02: Presupuesto y categorías
**Estado:** [COMPLETADA]
**Prioridad:** Alta
**Criterios de aceptación:**
- Scenario 1: Given un monto y un rango de fechas, When envío `POST /budgets`, Then se crea con 201.
- Scenario 2: Given presupuestos existentes, When pido `GET /budgets/active`, Then recibo el que contiene "hoy" según mi zona horaria.
- Scenario 3: Given un gasto con fecha fuera de todo presupuesto, When intento crearlo, Then recibo 400.
**Sub-tareas:**
- [Backend] Impedir presupuestos propios con rangos solapados (hoy no se valida de forma explícita).
**Código:** `backend/app/routers/budgets.py`, `backend/app/models/budget.py`, `backend/app/services/budget_lookup.py` (`find_budget_for_date`), `backend/app/schemas/budget.py`, `mobile/lib/features/budget/budget_screen.dart`, `backend/tests/test_budgets.py`

---

### HU-007: Persona usuaria quiero ver cuánto puedo gastar por día para decidir con tranquilidad
**Épica:** EP-02: Presupuesto y categorías
**Estado:** [COMPLETADA]
**Prioridad:** Alta
**Criterios de aceptación:**
- Scenario 1: Given un presupuesto con gastos, ingresos y aportes a metas, When consulto `GET /budgets/active/summary`, Then `disponible_total = monto_total + ingresos − gastado − apartado` y `disponible_por_dia` lo divide entre los días restantes.
- Scenario 2: Given un presupuesto vencido, When consulto el resumen, Then los días restantes y el disponible por día son 0 sin error.
- Scenario 3: Given un ritmo de gasto que agotaría el dinero antes del fin, When consulto el resumen, Then `en_riesgo` es verdadero y llega `fecha_proyectada_agotamiento`.
**Sub-tareas:** Ninguna pendiente.
**Código:** `backend/app/services/budget_calculator.py` (`calculate_budget_summary`), `backend/app/services/budget_totals.py` (`summary_for`), `backend/app/routers/budgets.py`, `mobile/lib/features/home/home_screen.dart`, `backend/tests/test_budget_calculator.py`

---

### HU-008: Persona usuaria quiero categorías por defecto y propias, con tipo fijo/opcional, para organizar mis gastos
**Épica:** EP-02: Presupuesto y categorías
**Estado:** [COMPLETADA]
**Prioridad:** Alta
**Criterios de aceptación:**
- Scenario 1: Given una base nueva, When arranca el contenedor, Then `app.db.seed` crea comida, transporte, entretenimiento, salud, servicios y otros.
- Scenario 2: Given `GET /categories`, When respondo, Then incluyo las por defecto y solo las propias de la persona.
- Scenario 3: Given una categoría propia, When envío `POST /categories` con `tipo` fijo u opcional, Then se crea con 201.
**Sub-tareas:** Ninguna pendiente.
**Código:** `backend/app/routers/categories.py`, `backend/app/models/category.py`, `backend/app/db/seed.py`, `backend/app/services/category_lookup.py`, `mobile/lib/features/transactions/manage_screens.dart`, `backend/tests/test_categories.py`

---

### HU-009: Persona usuaria quiero ponerle un límite a cada categoría para controlar dónde se me va el dinero
**Épica:** EP-02: Presupuesto y categorías
**Estado:** [COMPLETADA]
**Prioridad:** Media
**Criterios de aceptación:**
- Scenario 1: Given una categoría propia, When envío `PATCH /categories/{id}` con `limite`, Then se guarda en `Category.limite`.
- Scenario 2: Given una categoría por defecto, When fijo un límite, Then se guarda en `CategoryLimit` solo para mí y los demás no lo ven.
- Scenario 3: Given una categoría por defecto, When intento renombrarla, Then la API lo rechaza.
**Sub-tareas:** Ninguna pendiente.
**Código:** `backend/app/routers/categories.py` (`update_category`), `backend/app/models/category.py` (`CategoryLimit`), `backend/alembic/versions/b7e2f4a61d58_limites_propios_y_categorias_fijas.py`, `backend/tests/test_category_breakdown.py`

---

## EP-03: Registro de movimientos

### HU-010: Persona usuaria quiero registrar, ver, editar y borrar gastos manualmente para llevar mis cuentas
**Épica:** EP-03: Registro de movimientos
**Estado:** [COMPLETADA]
**Prioridad:** Alta
**Criterios de aceptación:**
- Scenario 1: Given un monto, categoría y fecha válidos, When envío `POST /expenses`, Then se guarda ligado al presupuesto de esa fecha.
- Scenario 2: Given gastos de varias fechas y categorías, When filtro `GET /expenses` por `category_id`, `fecha_desde` y `fecha_hasta`, Then solo recibo los que coinciden, ordenados por fecha descendente.
- Scenario 3: Given un gasto de otra persona, When intento editarlo o borrarlo, Then recibo 404.
**Sub-tareas:**
- [Backend] Paginación en `GET /expenses` (hoy devuelve todo).
**Código:** `backend/app/routers/expenses.py`, `backend/app/models/expense.py`, `backend/app/schemas/expense.py`, `mobile/lib/features/transactions/expense_form_screen.dart`, `mobile/lib/features/transactions/transactions_screen.dart`, `backend/tests/test_expenses.py`

---

### HU-011: Persona usuaria quiero registrar un gasto escribiendo o dictando una frase para anotar en segundos
**Épica:** EP-03: Registro de movimientos
**Estado:** [COMPLETADA]
**Prioridad:** Alta
**Criterios de aceptación:**
- Scenario 1: Given la frase "almuerzo 18 mil ayer", When envío `POST /expenses/parse`, Then recibo un borrador con monto, categoría existente, descripción y fecha, sin guardar nada.
- Scenario 2: Given un texto sin monto interpretable, When lo envío, Then recibo 422.
- Scenario 3: Given que Groq falla o no hay `GROQ_API_KEY`, When parseo, Then recibo 502 y puedo usar el formulario manual.
- Scenario 4: Given `POST /expenses/from-text` con un ingreso, When se procesa, Then recibo 422 pidiendo registrarlo como ingreso.
**Sub-tareas:**
- [IA] Evaluar un modelo mayor para el parseo si la categorización falla (ej. Rappi clasificado como transporte).
- [Tests] Banco de frases reales para medir precisión de categoría.
**Código:** `backend/app/routers/expenses.py` (`parse_expense`, `create_expense_from_text`), `backend/app/services/groq_client.py` (`parse_expense_text`, `_validar_gasto`), `backend/app/services/prompts.py`, `mobile/lib/features/transactions/add_sheet.dart`, `backend/tests/test_expenses_parse.py`

---

### HU-012: Persona usuaria quiero registrar un gasto con la foto de un recibo para no teclear los datos
**Épica:** EP-03: Registro de movimientos
**Estado:** [EN PROGRESO / PARCIAL]
**Prioridad:** Media
**Criterios de aceptación:**
- Scenario 1: Given una foto de un recibo, When la app reconoce el texto con ML Kit y llama a `POST /expenses/parse-receipt`, Then recibo comercio, monto, fecha y categoría sugerida.
- Scenario 2: Given el borrador, When lo confirmo, Then se guarda con `source="ocr"`.
- Scenario 3: Given que la foto nunca sale del teléfono, When se parsea, Then al backend solo llega `texto_ocr`.
**Sub-tareas:**
- [QA] Probar con ~10 recibos reales (pendiente según `plan-app-movil.md`) y registrar la tasa de acierto.
- [IA] Ajustar `build_receipt_parse_prompt` según los fallos hallados.
- [Tests] Casos de OCR ruidoso en `backend/tests/test_expenses_parse.py`.
**Código:** `backend/app/routers/expenses.py` (`parse_receipt`), `backend/app/services/groq_client.py` (`parse_receipt_text`), `backend/app/services/prompts.py`, `mobile/lib/features/transactions/add_sheet.dart`, `backend/tests/test_coach.py`

---

### HU-013: Persona usuaria quiero que los SMS del banco se detecten como movimientos para aprobarlos con un toque
**Épica:** EP-03: Registro de movimientos
**Estado:** [EN PROGRESO / PARCIAL]
**Prioridad:** Media
**Criterios de aceptación:**
- Scenario 1: Given permiso de lectura de SMS, When abro la app, Then los mensajes que parecen movimientos aparecen en Notificaciones.
- Scenario 2: Given un SMS detectado, When lo apruebo, Then se envía a `/expenses/parse` con `source="sms"` y se guarda tras confirmar.
- Scenario 3: Given un SMS descartado, When reabro la app, Then no vuelve a aparecer en esa cuenta.
**Sub-tareas:**
- [Mobile] Pruebas con SMS reales de varios bancos (el filtro `parece movimiento` es heurístico).
- [Mobile] Tests de `SmsInbox` con un `SmsSource` falso.
- [Legal] Declaración del permiso `READ_SMS` para Google Play (ver HU-038).
**Código:** `mobile/android/app/src/main/kotlin/com/diegochavarro/pay_and_check/MainActivity.kt`, `mobile/lib/features/sms/sms_inbox_screen.dart` (`SmsSource`, `SmsInbox`), `mobile/android/app/src/main/AndroidManifest.xml`, `backend/app/routers/expenses.py`

---

### HU-014: Persona usuaria quiero registrar ingresos para ampliar mi presupuesto
**Épica:** EP-03: Registro de movimientos
**Estado:** [COMPLETADA]
**Prioridad:** Media
**Criterios de aceptación:**
- Scenario 1: Given un ingreso con monto y fecha dentro de un presupuesto, When envío `POST /incomes`, Then aumenta `ingresos_total` y el disponible.
- Scenario 2: Given la frase "mis papás me dieron 200.000", When la parseo, Then `tipo` es `ingreso`.
- Scenario 3: Given un ingreso, When lo edito o borro, Then el disponible se recalcula.
**Sub-tareas:** Ninguna pendiente.
**Código:** `backend/app/routers/incomes.py`, `backend/app/models/income.py`, `backend/app/schemas/income.py`, `mobile/lib/features/transactions/transactions_screen.dart`, `backend/tests/test_incomes.py`

---

### HU-015: Persona usuaria quiero programar gastos fijos y confirmarlos cuando vencen para que no se me olviden
**Épica:** EP-03: Registro de movimientos
**Estado:** [COMPLETADA]
**Prioridad:** Media
**Criterios de aceptación:**
- Scenario 1: Given un gasto fijo semanal o mensual, When llega su vencimiento, Then aparece en `GET /recurring-expenses/pending` y no se descuenta solo.
- Scenario 2: Given un vencimiento pendiente, When envío `POST /{id}/pay`, Then se crea un `Expense` con `source="recurrente"`.
- Scenario 3: Given dos `pay` simultáneos para la misma fecha, When ambos llegan, Then solo se crea un gasto (restricción única).
- Scenario 4: Given un mensual el día 31, When el mes tiene menos días, Then vence el último día.
- Scenario 5: Given `POST /{id}/skip`, When omito, Then el vencimiento deja de aparecer.
**Sub-tareas:**
- [Mobile] Verificar que las alarmas locales no caigan todas a las 9:00 de días futuros (observado en las notas de iteración).
**Código:** `backend/app/routers/recurring_expenses.py`, `backend/app/services/recurring_expenses.py` (`pendientes`, `pagar`, `omitir`), `backend/app/models/recurring_expense.py`, `backend/alembic/versions/7f2a9c4e1d05_gasto_recurrente_unico_por_fecha.py`, `mobile/lib/core/notifications.dart`, `backend/tests/test_recurring_expenses.py`

---

### HU-016: Persona usuaria quiero una bandeja de notificaciones para revisar pagos por hacer y movimientos detectados
**Épica:** EP-03: Registro de movimientos
**Estado:** [COMPLETADA]
**Prioridad:** Baja
**Criterios de aceptación:**
- Scenario 1: Given gastos fijos vencidos y SMS por revisar, When abro la campana, Then veo ambos con su contador.
- Scenario 2: Given que apruebo u omito un elemento, When vuelvo al inicio, Then el contador baja.
**Sub-tareas:** Ninguna pendiente.
**Código:** `mobile/lib/features/sms/sms_inbox_screen.dart`, `mobile/lib/core/notifications.dart`, `mobile/lib/data/providers.dart` (`pendingPaymentsProvider`)

---

## EP-04: Coach financiero

### HU-017: Persona usuaria quiero hacer un check-in emocional diario para que el coach entienda cómo me siento con el dinero
**Épica:** EP-04: Coach financiero
**Estado:** [COMPLETADA]
**Prioridad:** Media
**Criterios de aceptación:**
- Scenario 1: Given un ánimo válido (ansioso, preocupado, neutral, tranquilo, confiado), When envío `POST /checkins`, Then queda registrado para hoy.
- Scenario 2: Given un check-in ya hecho hoy, When envío otro, Then reemplaza al anterior.
- Scenario 3: Given un ánimo inválido, When lo envío, Then recibo 422.
**Sub-tareas:** Ninguna pendiente.
**Código:** `backend/app/routers/checkins.py`, `backend/app/models/coach.py` (`EmotionalCheckin`), `backend/app/schemas/coach.py`, `mobile/lib/features/coach/coach_widgets.dart`, `backend/tests/test_coach.py`

---

### HU-018: Persona usuaria quiero una reacción del coach al registrar un gasto para sentir acompañamiento
**Épica:** EP-04: Coach financiero
**Estado:** [COMPLETADA]
**Prioridad:** Media
**Criterios de aceptación:**
- Scenario 1: Given un gasto recién creado, When la app llama `POST /coach/reaction`, Then recibo un mensaje que usa solo cifras calculadas por el backend.
- Scenario 2: Given que el modelo usa lenguaje culposo o inventa cifras, When pasa por los guardrails, Then se descarta y se usa el texto de respaldo.
- Scenario 3: Given que la reacción falla, When registro un gasto, Then el registro no se bloquea.
**Sub-tareas:** Ninguna pendiente.
**Código:** `backend/app/routers/coach.py` (`reaccion`), `backend/app/services/coach.py` (`reaccion_a_gasto`, `rompe_guardrails`, `inventa_cifras`), `backend/app/services/prompts.py`, `backend/tests/test_coach.py`

---

### HU-019: Persona usuaria quiero consejos accionables del día para saber qué hacer con un toque
**Épica:** EP-04: Coach financiero
**Estado:** [COMPLETADA]
**Prioridad:** Media
**Criterios de aceptación:**
- Scenario 1: Given suficientes datos, When pido `GET /coach/insights`, Then recibo consejos basados en patrones (fin de semana, variación semanal, categoría dominante, ánimo vs. gasto, estado del presupuesto).
- Scenario 2: Given que ya se generaron hoy, When vuelvo a pedir, Then se sirven desde `coach_messages` sin llamar a Groq; con `refresh=true` se regeneran.
- Scenario 3: Given un consejo con acción, When la acepto, Then se crea el reto o límite sugerido.
**Sub-tareas:** Ninguna pendiente.
**Código:** `backend/app/services/patterns.py` (`detect_patterns`), `backend/app/services/coach.py` (`insights_del_dia`), `backend/app/routers/coach.py`, `mobile/lib/features/coach/coach_screen.dart`, `backend/tests/test_coach.py`

---

### HU-020: Persona usuaria quiero chatear con el coach para resolver dudas sobre mi presupuesto
**Épica:** EP-04: Coach financiero
**Estado:** [COMPLETADA]
**Prioridad:** Media
**Criterios de aceptación:**
- Scenario 1: Given un mensaje, When envío `POST /coach/chat`, Then recibo una respuesta con contexto financiero y las últimas 10 interacciones.
- Scenario 2: Given una pregunta sobre inversiones, When respondo, Then solo doy educación general, sin asesoría regulada.
- Scenario 3: Given que Groq no responde, When envío un mensaje, Then recibo el texto de respaldo.
**Sub-tareas:**
- [Backend] Límite de mensajes por minuto por usuario para cuidar la cuota de Groq.
**Código:** `backend/app/routers/coach.py` (`chat`), `backend/app/services/coach.py` (`responder_chat`, `contexto_financiero`), `backend/app/models/coach.py` (`CoachMessage`), `mobile/lib/features/coach/coach_screen.dart`, `backend/tests/test_coach.py`

---

### HU-021: Persona usuaria quiero elegir el tono del coach para que me hable como prefiero
**Épica:** EP-04: Coach financiero
**Estado:** [COMPLETADA]
**Prioridad:** Baja
**Criterios de aceptación:**
- Scenario 1: Given `coach_tone` = motivador, directo, humorístico o minimalista, When el coach redacta, Then el prompt incluye ese estilo vía `build_coach_rules`.
- Scenario 2: Given cualquier tono, When responde, Then nunca regaña ni recomienda inversiones.
**Sub-tareas:** Ninguna pendiente.
**Código:** `backend/app/services/prompts.py` (`build_coach_rules`), `backend/app/services/coach.py` (`reglas_para`), `backend/app/models/user.py` (`coach_tone`)

---

### HU-022: Persona usuaria quiero alertas proactivas de riesgo y acciones asistidas para actuar antes de quedarme sin dinero
**Épica:** EP-04: Coach financiero
**Estado:** [EN PROGRESO / PARCIAL]
**Prioridad:** Media
**Criterios de aceptación:**
- Scenario 1: Given `en_riesgo` verdadero, When abro el coach, Then veo el aviso con la fecha proyectada de agotamiento.
- Scenario 2: Given un patrón impulsivo recurrente (ej. viernes por la noche), When ocurre, Then recibo una alerta antes del momento de riesgo (hoy no existe).
- Scenario 3: Given una acción propuesta (apartar dinero, aceptar un reto, fijar un límite), When la confirmo, Then se ejecuta con mi consentimiento.
**Sub-tareas:**
- [Backend] Detector de horarios/días de riesgo en `patterns.py`.
- [Mobile] Notificación local programada a partir del patrón.
- [Backend] Ampliar los tipos de acción asistida más allá de reto/meta/límite.
- [Tests] Casos de cada patrón nuevo.
**Código:** `backend/app/services/patterns.py` (`_del_presupuesto`), `backend/app/services/budget_calculator.py` (`_proyectar_agotamiento`), `mobile/lib/core/notifications.dart`, `mobile/lib/features/coach/coach_widgets.dart`

---

## EP-05: Metas, retos y gamificación

### HU-023: Persona usuaria quiero crear metas de ahorro con dinero realmente apartado para avanzar sin autoengañarme
**Épica:** EP-05: Metas, retos y gamificación
**Estado:** [COMPLETADA]
**Prioridad:** Media
**Criterios de aceptación:**
- Scenario 1: Given una meta con nombre y monto, When envío `POST /goals`, Then se crea activa.
- Scenario 2: Given disponible suficiente, When aporto con `POST /goals/{id}/contributions`, Then el aporte baja el disponible del presupuesto de esa fecha.
- Scenario 3: Given disponible insuficiente, When aporto, Then el aporte se rechaza.
- Scenario 4: Given que la suma de aportes alcanza el objetivo, When consulto la meta, Then pasa a `cumplida`.
- Scenario 5: Given un aporte, When lo elimino, Then el progreso y el disponible se revierten.
**Sub-tareas:** Ninguna pendiente.
**Código:** `backend/app/routers/goals.py`, `backend/app/models/goal.py` (`Goal`, `GoalContribution`), `backend/app/schemas/goal.py`, `mobile/lib/features/progress/goal_dialogs.dart`, `mobile/lib/features/progress/progress_screen.dart`, `backend/tests/test_gamification.py`

---

### HU-024: Persona usuaria quiero retos personalizados verificados con mis datos para mejorar mis hábitos
**Épica:** EP-05: Metas, retos y gamificación
**Estado:** [COMPLETADA]
**Prioridad:** Media
**Criterios de aceptación:**
- Scenario 1: Given mis patrones de gasto, When pido `GET /challenges/suggestions`, Then recibo retos sugeridos.
- Scenario 2: Given un reto de alguno de los 6 tipos (`reducir_categoria`, `dias_sin_gasto`, `checkins`, `registro_diario`, `aportar_meta`, `semana_en_ritmo`), When lo creo, Then se guarda con su `objetivo`, ventana y puntos.
- Scenario 3: Given que termina la ventana, When consulto `/challenges`, Then el estado pasa a `cumplido` o `fallido` según los datos reales.
- Scenario 4: Given un reto activo, When lo abandono con `DELETE`, Then desaparece sin dar puntos.
**Sub-tareas:** Ninguna pendiente.
**Código:** `backend/app/routers/gamification.py`, `backend/app/services/gamification.py` (`crear_reto`, `progreso_reto`, `sugerencias_de_retos`), `backend/app/models/gamification.py` (`Challenge`), `backend/alembic/versions/c9f3a5d27e41_mas_tipos_de_reto.py`, `backend/tests/test_gamification.py`

---

### HU-025: Persona usuaria quiero puntos, niveles, rachas e insignias para sentir progreso por constancia
**Épica:** EP-05: Metas, retos y gamificación
**Estado:** [COMPLETADA]
**Prioridad:** Media
**Criterios de aceptación:**
- Scenario 1: Given actividad registrada, When consulto `GET /gamification/profile`, Then `sync_gamification` recalcula puntos, nivel, racha e insignias (23 en el catálogo).
- Scenario 2: Given que consulto varias veces, When se recalcula, Then no se duplican puntos (`UNIQUE(user_id, clave)` en `point_events`).
- Scenario 3: Given una insignia ya desbloqueada, When se evalúa de nuevo, Then no se repite (`UNIQUE(user_id, codigo)`).
**Sub-tareas:** Ninguna pendiente.
**Código:** `backend/app/services/gamification.py` (`_sync_gamification`, `_desbloquear_insignias`, `nivel_para`, `racha_actual`), `backend/app/models/gamification.py` (`PointEvent`, `Achievement`), `backend/app/routers/gamification.py`, `mobile/lib/features/progress/progress_screen.dart`, `backend/tests/test_gamification.py`

---

### HU-026: Persona usuaria quiero que puntos y logros premien la mejora y no los montos para que sea justo con todos los ingresos
**Épica:** EP-05: Metas, retos y gamificación
**Estado:** [COMPLETADA]
**Prioridad:** Baja
**Criterios de aceptación:**
- Scenario 1: Given dos meses consecutivos, When el `ratio_ahorro` mejora, Then se otorgan puntos por mejora mensual.
- Scenario 2: Given un mes sin gastos registrados, When calculo el ratio, Then es `None` (no cuenta como ahorro del 100 %).
**Sub-tareas:** Ninguna pendiente.
**Código:** `backend/app/services/budget_totals.py` (`ratio_ahorro`, `presupuesto_prorrateado`), `backend/app/services/gamification.py` (`_otorgar_mejora_mensual`, `_otorgar_semanas_en_ritmo`)

---

### HU-027: Persona usuaria quiero competir con amigos por constancia para mantener la motivación *(visión)*
**Épica:** EP-05: Metas, retos y gamificación
**Estado:** [PENDIENTE]
**Prioridad:** Baja
**Criterios de aceptación:**
- Scenario 1: Given que pertenezco a un grupo, When consulto la liga, Then veo el ranking por consistencia y mejora, nunca por monto gastado.
- Scenario 2: Given un reto colaborativo del grupo, When los miembros aportan, Then el progreso es compartido.
- Scenario 3: Given que no quiero participar, When lo desactivo, Then mis datos no aparecen para otros.
**Sub-tareas:**
- [DB] Activar `Group` y `User.group_id` (hoy reservados) y crear tabla de membresías.
- [Backend] Router `groups` e invitaciones; endpoints de liga y reto colaborativo.
- [Backend] Reglas de privacidad: solo métricas agregadas.
- [Mobile] Pantallas de grupo y ranking.
- [Tests] Aislamiento entre grupos.
**Código:** `backend/app/models/group.py` (existe, sin uso), `backend/app/models/user.py` (`group_id`), nuevos `backend/app/routers/groups.py`, `backend/app/services/leagues.py`, `mobile/lib/features/groups/`

---

### HU-028: Persona usuaria quiero recompensas desbloqueables para tener un incentivo tangible *(visión)*
**Épica:** EP-05: Metas, retos y gamificación
**Estado:** [PENDIENTE]
**Prioridad:** Baja
**Criterios de aceptación:**
- Scenario 1: Given que alcanzo un nivel, When consulto recompensas, Then veo las desbloqueadas y las bloqueadas.
- Scenario 2: Given una recompensa desbloqueada, When la reclamo, Then queda marcada como entregada una sola vez.
**Sub-tareas:**
- [Producto] Definir el catálogo de recompensas.
- [DB] Tabla `rewards` / `user_rewards` + migración Alembic.
- [Backend] Endpoints de listado y reclamo; reglas en `services/gamification.py`.
- [Mobile] Sección en Progreso.
**Código:** nuevos `backend/app/models/reward.py`, `backend/app/routers/rewards.py`; extender `backend/app/services/gamification.py`, `mobile/lib/features/progress/progress_screen.dart`

---

## EP-06: Reportes

### HU-029: Persona usuaria quiero ver mi gasto por semana en gráficas para detectar tendencias
**Épica:** EP-06: Reportes
**Estado:** [COMPLETADA]
**Prioridad:** Media
**Criterios de aceptación:**
- Scenario 1: Given `GET /reports/trends?semanas=8`, When respondo, Then devuelvo gasto por semana y por día, con promedio.
- Scenario 2: Given `semanas` fuera de 2–26, When lo envío, Then recibo 422.
**Sub-tareas:** Ninguna pendiente.
**Código:** `backend/app/routers/reports.py` (`trends`), `backend/app/services/trends.py` (`build_trends`), `mobile/lib/core/charts.dart`, `mobile/lib/features/reports/analytics_screen.dart`, `backend/tests/test_trends.py`, `mobile/test/charts_test.dart`

---

### HU-030: Persona usuaria quiero un reporte semanal con recomendaciones para revisar cómo voy
**Épica:** EP-06: Reportes
**Estado:** [COMPLETADA]
**Prioridad:** Media
**Criterios de aceptación:**
- Scenario 1: Given un presupuesto activo, When pido `GET /reports/weekly`, Then recibo el resumen numérico y recomendaciones.
- Scenario 2: Given que Groq falla, When pido el reporte, Then recibo el resumen con texto de respaldo.
- Scenario 3: Given que no hay presupuesto activo, When lo pido, Then recibo 404.
**Sub-tareas:** Ninguna pendiente.
**Código:** `backend/app/routers/reports.py` (`weekly_report`), `backend/app/services/weekly_report.py`, `backend/app/services/groq_client.py` (`generate_weekly_recommendations`), `mobile/lib/features/reports/report_screens.dart`, `backend/tests/test_reports.py`

---

### HU-031: Persona usuaria quiero un resumen mensual tipo "Wrapped" para celebrar y entender mi mes
**Épica:** EP-06: Reportes
**Estado:** [COMPLETADA]
**Prioridad:** Baja
**Criterios de aceptación:**
- Scenario 1: Given `GET /reports/monthly-wrapped?mes=YYYY-MM`, When respondo, Then devuelvo los datos del mes con frase de cierre.
- Scenario 2: Given un `mes` con formato inválido, When lo envío, Then recibo 422.
**Sub-tareas:**
- [Producto] Asociar fotos o recuerdos a los gastos (la visión lo pide; hoy se entrega sin fotos).
**Código:** `backend/app/services/wrapped.py` (`build_wrapped`), `backend/app/routers/reports.py`, `mobile/lib/features/reports/report_screens.dart`, `backend/tests/test_gamification.py`

---

## EP-07: Automatización e integraciones

### HU-032: Persona usuaria quiero que la app detecte suscripciones y cargos recurrentes para decidir cuáles cancelar *(visión)*
**Épica:** EP-07: Automatización e integraciones
**Estado:** [PENDIENTE]
**Prioridad:** Media
**Criterios de aceptación:**
- Scenario 1: Given cargos similares en meses consecutivos, When corre la detección, Then se propone convertirlos en gasto fijo.
- Scenario 2: Given una suscripción sin uso aparente, When aparece la sugerencia, Then puedo ignorarla o pausarla.
**Sub-tareas:**
- [Backend] Detector sobre `Expense` (comercio + monto + periodicidad) en `services/`.
- [Backend] Endpoint `GET /recurring-expenses/suggestions`.
- [Mobile] Tarjeta de sugerencia que reutilice el alta de `RecurringExpense`.
- [Tests] Casos con montos variables y falsos positivos.
**Código:** nuevo `backend/app/services/subscriptions.py`; extender `backend/app/routers/recurring_expenses.py`, `backend/app/models/expense.py` (`comercio`), `mobile/lib/features/transactions/manage_screens.dart`

---

### HU-033: Persona usuaria quiero anticipar gastos futuros con mi calendario para evitar déficits *(visión)*
**Épica:** EP-07: Automatización e integraciones
**Estado:** [PENDIENTE]
**Prioridad:** Baja
**Criterios de aceptación:**
- Scenario 1: Given que conecto mi calendario, When hay un evento con gasto esperado (cumpleaños, matrícula), Then el coach me avisa del posible déficit.
- Scenario 2: Given que desconecto el calendario, When reviso, Then se eliminan los datos importados.
**Sub-tareas:**
- [Mobile] Permiso y lectura de calendario.
- [Backend] Endpoint para recibir eventos y estimar impacto en `disponible_por_dia`.
- [IA] Clasificar eventos con costo probable.
- [Legal] Consentimiento y política de privacidad (ver HU-037).
**Código:** nuevos `backend/app/services/calendar_forecast.py`, `backend/app/routers/calendar.py`, `mobile/lib/features/calendar/`

---

### HU-034: Persona usuaria quiero importar movimientos de mis correos bancarios para no registrarlos *(visión)*
**Épica:** EP-07: Automatización e integraciones
**Estado:** [PENDIENTE]
**Prioridad:** Baja
**Criterios de aceptación:**
- Scenario 1: Given que autorizo Gmail (`gmail.readonly`), When llegan correos de transacciones, Then se proponen como borradores a confirmar.
- Scenario 2: Given que revoco el permiso, When sincronizo, Then deja de leerse el correo.
**Sub-tareas:**
- [Legal] Evaluación de seguridad CASA de Google exigida para producción (costo alto; `mejoras.md` recomienda dejarlo para después del MVP).
- [Backend] OAuth, lectura y parseo reutilizando `parse_expense_text`.
- [Mobile] Pantalla de conexión.
**Código:** nuevos `backend/app/services/gmail_import.py`, `backend/app/routers/integrations.py`; reutilizar `backend/app/services/groq_client.py`

---

## EP-08: Lanzamiento y operación

### HU-035: Equipo de desarrollo quiero CI y despliegue automatizados para publicar con confianza
**Épica:** EP-08: Lanzamiento y operación
**Estado:** [EN PROGRESO / PARCIAL]
**Prioridad:** Alta
**Criterios de aceptación:**
- Scenario 1: Given un push que toca `backend/**`, When corre `backend-ci.yml`, Then ejecuta `ruff` y `pytest` herméticos.
- Scenario 2: Given un tag `v*`, When corre `mobile-release.yml`, Then compila el APK firmado y lo adjunta a un GitHub Release.
- Scenario 3: Given un merge a la rama de despliegue, When Render recibe el cambio, Then construye la imagen, migra, siembra y responde `/health`.
**Sub-tareas:**
- [Infra] Recuperar `upload-keystore.jks` y `key.properties` y cargar los secretos del workflow de release.
- [Infra] Cambiar la rama de despliegue de Render si `feature/bento-ui` se borra tras el merge.
- [CI] Probar de punta a punta el workflow de release (aún sin ejecutar con un tag real).
- [CI] Publicar `/health` de cada despliegue como paso de verificación.
**Código:** `.github/workflows/backend-ci.yml`, `.github/workflows/mobile-ci.yml`, `.github/workflows/mobile-release.yml`, `render.yaml`, `backend/Dockerfile`, `backend/start.sh`

---

### HU-036: Responsable del producto quiero medir retención y una bienvenida inicial para saber si el producto es viable
**Épica:** EP-08: Lanzamiento y operación
**Estado:** [PENDIENTE]
**Prioridad:** Alta
**Criterios de aceptación:**
- Scenario 1: Given una cuenta nueva, When entra por primera vez, Then ve una bienvenida que explica el coach y la lleva a su primer registro.
- Scenario 2: Given usuarios activos, When consulto la métrica, Then veo cuántos siguen a los 7 y 30 días.
**Sub-tareas:**
- [Mobile] Flujo de onboarding (presupuesto inicial + primer gasto).
- [Backend] Registro de actividad mínima (último acceso) o analítica respetuosa de la privacidad.
- [Producto] Definir la métrica de retención y el panel donde se lee.
**Código:** nuevos `mobile/lib/features/onboarding/`; extender `backend/app/models/user.py` (o tabla de eventos), `mobile/lib/app.dart` (ruta de bienvenida)

---

### HU-037: Persona usuaria quiero una política de privacidad y un consentimiento claros para saber qué se lee y qué se envía a Groq
**Épica:** EP-08: Lanzamiento y operación
**Estado:** [EN PROGRESO / PARCIAL]
**Prioridad:** Alta
**Criterios de aceptación:**
- Scenario 1: Given el primer registro, When acepto, Then se me explica que se leen SMS (si doy permiso) y que el texto de los movimientos aprobados se envía a Groq.
- Scenario 2: Given Perfil, When abro privacidad, Then veo la política y la opción de borrar mis datos (HU-005).
**Sub-tareas:**
- [Legal] Redactar y publicar la política en una URL pública.
- [Mobile] Pantalla de consentimiento previa al permiso de SMS.
- [Backend] Guardar fecha y versión del consentimiento aceptado.
**Código:** `mobile/lib/features/profile/profile_screen.dart` (sección de privacidad existente), `mobile/lib/features/auth/auth_screens.dart`, `backend/app/models/user.py`, `backend/alembic/versions/` (migración nueva)

---

### HU-038: Equipo de producto quiero publicar en Google Play para llegar a más personas
**Épica:** EP-08: Lanzamiento y operación
**Estado:** [PENDIENTE]
**Prioridad:** Baja
**Criterios de aceptación:**
- Scenario 1: Given la app firmada, When la subo a Play Console, Then pasa la revisión con el permiso `READ_SMS` declarado.
- Scenario 2: Given la política de privacidad pública, When completo el formulario de datos, Then queda aprobado.
**Sub-tareas:**
- [Legal] Formulario de excepción "SMS-based money management" con video demostrativo.
- [Release] Cuenta de desarrollador, ficha de la tienda, capturas (`mobile/tool/screenshots_test.dart` ya las genera).
- [Release] Migrar de APK directo a App Bundle firmado.
**Código:** `mobile/android/app/build.gradle.kts`, `mobile/android/app/src/main/AndroidManifest.xml`, `.github/workflows/mobile-release.yml`, `mobile/tool/screenshots_test.dart`

---

### HU-039: Equipo técnico quiero un entorno que no se duerma y una cuota de IA suficiente para una beta con varias personas
**Épica:** EP-08: Lanzamiento y operación
**Estado:** [PENDIENTE]
**Prioridad:** Media
**Criterios de aceptación:**
- Scenario 1: Given tráfico de varias personas, When llegan peticiones tras un rato inactivo, Then la API responde sin el arranque en frío del plan gratuito.
- Scenario 2: Given varias personas usando el parseo a la vez, When se alcanza el límite de tokens por minuto, Then el sistema degrada con elegancia (texto de respaldo o reintento) y no devuelve 500.
**Sub-tareas:**
- [Infra] Plan de Render y de Neon sin suspensión.
- [Infra] Plan de pago o más cuota en Groq (el gratuito limita a 8.000 tokens por minuto).
- [Backend] Reintentos con espera y límite por usuario en `groq_client.py`.
- [Observabilidad] Métricas y alertas sobre errores 502 y latencia.
**Código:** `render.yaml`, `backend/app/services/groq_client.py`, `backend/app/main.py`

---

## Índice CSV

```csv
HU,Epica,Titulo,Estado,Prioridad
HU-001,EP-01,Registro e inicio de sesión con correo,COMPLETADA,Alta
HU-002,EP-01,Renovación automática de sesión,COMPLETADA,Alta
HU-003,EP-01,Inicio de sesión con Google,EN PROGRESO / PARCIAL,Media
HU-004,EP-01,Perfil: tono, idioma y zona horaria,COMPLETADA,Media
HU-005,EP-01,Borrar cuenta y datos,EN PROGRESO / PARCIAL,Alta
HU-006,EP-02,Definir presupuesto por periodo,COMPLETADA,Alta
HU-007,EP-02,Disponible por día y riesgo,COMPLETADA,Alta
HU-008,EP-02,Categorías por defecto y propias,COMPLETADA,Alta
HU-009,EP-02,Límites por categoría,COMPLETADA,Media
HU-010,EP-03,Gastos manuales (CRUD),COMPLETADA,Alta
HU-011,EP-03,Gasto por texto o voz con IA,COMPLETADA,Alta
HU-012,EP-03,Gasto por foto de recibo,EN PROGRESO / PARCIAL,Media
HU-013,EP-03,Movimientos desde SMS del banco,EN PROGRESO / PARCIAL,Media
HU-014,EP-03,Ingresos,COMPLETADA,Media
HU-015,EP-03,Gastos fijos con confirmación,COMPLETADA,Media
HU-016,EP-03,Bandeja de notificaciones,COMPLETADA,Baja
HU-017,EP-04,Check-in emocional diario,COMPLETADA,Media
HU-018,EP-04,Reacción del coach al registrar,COMPLETADA,Media
HU-019,EP-04,Consejos accionables del día,COMPLETADA,Media
HU-020,EP-04,Chat con el coach,COMPLETADA,Media
HU-021,EP-04,Tono configurable del coach,COMPLETADA,Baja
HU-022,EP-04,Alertas proactivas y acciones asistidas,EN PROGRESO / PARCIAL,Media
HU-023,EP-05,Metas de ahorro con aportes reales,COMPLETADA,Media
HU-024,EP-05,Retos personalizados verificados,COMPLETADA,Media
HU-025,EP-05,Puntos niveles rachas e insignias,COMPLETADA,Media
HU-026,EP-05,Puntos por mejora y no por monto,COMPLETADA,Baja
HU-027,EP-05,Ligas y retos colaborativos,PENDIENTE,Baja
HU-028,EP-05,Recompensas desbloqueables,PENDIENTE,Baja
HU-029,EP-06,Tendencia semanal en gráficas,COMPLETADA,Media
HU-030,EP-06,Reporte semanal con recomendaciones,COMPLETADA,Media
HU-031,EP-06,Resumen mensual Wrapped,COMPLETADA,Baja
HU-032,EP-07,Detección de suscripciones,PENDIENTE,Media
HU-033,EP-07,Sincronización con calendario,PENDIENTE,Baja
HU-034,EP-07,Importación desde Gmail,PENDIENTE,Baja
HU-035,EP-08,CI y despliegue automatizados,EN PROGRESO / PARCIAL,Alta
HU-036,EP-08,Onboarding y métricas de retención,PENDIENTE,Alta
HU-037,EP-08,Política de privacidad y consentimiento,EN PROGRESO / PARCIAL,Alta
HU-038,EP-08,Publicación en Google Play,PENDIENTE,Baja
HU-039,EP-08,Entorno sin suspensión y cuota de IA,PENDIENTE,Media
```
