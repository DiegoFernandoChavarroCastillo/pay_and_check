# Plan — de backend de gastos a app móvil "coach financiero" (Flutter + FastAPI)

> **Estado al 13 de octubre de 2026.** Las fases 1 a 5 y 7 están construidas y recorridas en un teléfono
> (Moto G6, Android 9, modo depuración) con la IA real. Siguen abiertos el APK de release, el login con
> Google, el despliegue del backend y la beta con probadores. Después de este plan vino la Fase 8 (al final):
> rediseño, notificaciones, gastos fijos con recordatorio y más retos e insignias. El detalle de cada
> iteración está en `notas-iteracion-app-movil.md`.

## Contexto

El backend del MVP original (FastAPI + Groq, Fases 0–11, 51 tests) está terminado pero no hay app: nadie puede usarlo. `mejoras.md` define a dónde llevar el producto: un coach financiero emocional, con gamificación verificable y captura automática (OCR/SMS), en el teléfono.

Decisiones ya tomadas contigo:

- **Backend**: se mantiene FastAPI + Groq y se extiende (no se reescribe en NestJS/OpenAI).
- **App**: Flutter, en una carpeta nueva `mobile/` junto a `backend/`.
- **Distribución**: APK directo (sin tienda) en esta etapa. Solo Android.
- **Presupuesto por periodo**: sigue siendo el núcleo; el "disponible por día" es el dato central y coach/metas/retos se construyen encima.

Alcance = MVP de la sección 5 de `mejoras.md`. **Fuera**: Gmail API, integración bancaria, ligas/retos sociales, ejecución autónoma, predicción de déficit con calendario, Redis, S3, iOS.

Adaptaciones al stack de `mejoras.md` (para no añadir infraestructura ni costo):

| mejoras.md | Aquí | Por qué |
|---|---|---|
| Google Vision + S3 | OCR en el dispositivo (ML Kit) + Groq estructura el texto | Gratis, offline, la foto no sale del teléfono, sirve el modelo de texto actual |
| Firebase Cloud Messaging | Notificaciones locales programadas | El MVP solo necesita recordatorios (check-in, gastos fijos); no hace falta servidor de push |
| Scheduler / ML en Python | Cálculo "al vuelo" + reglas deterministas | Nada corre en segundo plano en el servidor; la IA solo redacta, no calcula |
| Mover dinero real | "Apartados" virtuales hacia metas | Sin banco, el dinero se reserva dentro del presupuesto |

## Opciones para generar el APK

| Opción | Cómo | Costo | Cuándo usarla |
|---|---|---|---|
| **Local** | `flutter build apk --release --split-per-abi` | Gratis; requiere Flutter SDK + Android SDK + JDK en tu PC | Desarrollo diario y pruebas en tu teléfono (`flutter run`, `adb install`) |
| **GitHub Actions** | Workflow que compila y adjunta el APK a un GitHub Release al crear un tag | Gratis en repo público; minutos limitados en privado | Entregar versiones a probadores: un enlace de descarga, build reproducible |
| Codemagic | CI especializado en Flutter | Plan gratis con minutos limitados | Alternativa si Actions se queda corto |
| Firebase App Distribution | Sube el APK y avisa a testers por correo | Gratis | Si los probadores crecen (>10) |
| Play Store (AAB) | `flutter build appbundle` + cuenta de 25 USD | Pago único + prueba cerrada 12 testers/14 días | Fase de lanzamiento, no ahora |

**Recomendado**: local para desarrollar + GitHub Actions para publicar cada versión. Puntos que no se pueden saltar:

- **Keystore de firma propio** desde el primer APK compartido (`key.properties` fuera de git; en CI como secreto base64). Si se pierde o cambia, los usuarios tienen que desinstalar para actualizar.
- **Google Sign-In** necesita en Google Cloud: el Client ID *web* (el que ya espera el backend en `GOOGLE_CLIENT_ID`, se pasa a la app como `serverClientId`) y un Client ID *Android* con el SHA-1 del keystore y el nombre de paquete.
- **El backend debe estar en internet con HTTPS**: los tokens y datos financieros no deben viajar en HTTP plano fuera de tu PC. En desarrollo: emulador → `10.0.2.2:8000`, teléfono físico → `adb reverse tcp:8000 tcp:8000`.
- Leer SMS con APK directo no tiene restricciones; en Play Store exigiría declaración de permisos (por eso SMS queda al final y aislado).

## Fases

Cada fase es una rebanada vertical (backend → app → criterio de aceptación), igual que el plan anterior. Marca los checkboxes a medida que se completen las tareas.

### Fase 0 — Entorno y bases

- [x] Instalar `uv` (Python 3.12 lo gestiona uv), crear `backend/.env`, confirmar 51 tests + `ruff` en verde en esta máquina. `backend/.env` quedó con un `JWT_SECRET` aleatorio; **falta que pongas `GROQ_API_KEY` y `GOOGLE_CLIENT_ID`**.
- [x] Instalar Flutter SDK + Android SDK; `flutter doctor` limpio; `flutter create` en `mobile/` (definir nombre de app e id de paquete). Flutter 3.47.7 en `C:/Users/chava/dev/flutter`, JDK 17 y Android SDK (solo línea de comandos, sin Android Studio) en `%LOCALAPPDATA%/Android/Sdk`. Nombre provisional "Pay & Check", id `com.diegochavarro.pay_and_check` — **cambiable sin costo hasta que se cree el Client ID Android de Google**.
- [ ] Crear el Client ID de Google (pendiente de la Fase 0 original) — web + Android.
- [ ] Desplegar backend: Render (Dockerfile existente) + Neon (ya usado), migraciones y seed según `README.md`.
- [x] Ajustes de backend para móvil (migración `c3d81f0a7b21`, tests en `backend/tests/test_mobile_basics.py`):
  - [x] `POST /auth/refresh` con refresh token (hoy el JWT expira a los 60 min y no hay forma de renovarlo) — `backend/app/core/security.py`, `backend/app/routers/auth.py`.
  - [x] `User` gana `coach_tone`, `idioma`, `zona_horaria`; `PATCH /auth/me` y `DELETE /auth/me` (borrado total de datos).
  - [x] "Hoy" según la zona horaria del usuario: hoy se usa `date.today()` del servidor (UTC), que a las 7 pm en Colombia ya es mañana. Centralizar en un helper junto a `backend/app/core/time.py` y usarlo en `budget_lookup.py`, `budget_calculator.py`, `recurring_expenses.py`, `weekly_report.py`.
  - [x] `Expense` gana `source` (`manual|texto|voz|ocr|sms|recurrente`) y `comercio` (nullable). `POST /expenses` acepta además `texto_original`, para conservar la frase/recibo cuando el gasto se confirma tras un parseo.
- [x] CI: añadir job `flutter analyze` + `flutter test` en `.github/workflows/` (`mobile-ci.yml`).

**Aceptación**: app vacía corre en tu teléfono y hace `GET /health` contra el backend desplegado.
🟡 **A medias**: la app completa corre en un teléfono contra el backend local (por USB, con `adb reverse`). El backend desplegado sigue pendiente.

**Notas de la fase**
- El refresh token es stateless: no se puede revocar uno ya emitido (cerrar sesión solo lo borra del teléfono). Suficiente para la beta; si hiciera falta revocación, requiere una tabla de tokens.
- `zona_horaria` por defecto es `America/Bogota`; la app debe enviar la del dispositivo con `PATCH /auth/me` en el onboarding (Fase 1).
- La plantilla `.gitignore` de Python de la raíz ignoraba `lib/`, que es donde vive el código Flutter: se agregó la excepción `!mobile/lib/`.
- Se agregó `tzdata` a las dependencias del backend: Windows y las imágenes Docker *slim* no traen la base de zonas horarias.

### Fase 1 — App base: auth, presupuesto y dashboard

- [x] Arquitectura Flutter por features (`mobile/lib/features/<feature>/{data,domain,ui}`), `core/` para API, tema e i18n.
- [x] Paquetes: `flutter_riverpod`, `go_router`, `dio` (interceptor de refresh), `flutter_secure_storage`, `google_sign_in`, `fl_chart`, `intl` + ARB (es/en desde el día 1).
- [x] Tema: modo claro/oscuro, tipografía escalable, contraste AA.
- [x] Pantallas: login/registro (email y Google), onboarding (crear presupuesto, elegir tono del coach), Home con `GET /budgets/active/summary` (disponible por día, alerta `en_riesgo`, desglose por categoría).

**Aceptación**: registrarse, crear presupuesto y ver el disponible por día en el teléfono; la sesión sobrevive a cerrar la app.
✅ **Hecho y recorrido en un teléfono**: registro, presupuesto y disponible por día; la sesión sobrevive a cerrar la app. Falta el login con Google (sin Client ID). Desviaciones: los modelos y llamadas a la API viven juntos en `mobile/lib/data/` (no una carpeta `data/domain` por feature) — ver `notas-iteracion-app-movil.md`.

### Fase 2 — Transacciones: manual, texto y voz

- [x] Pantalla Transacciones: lista con filtros (`GET /expenses`), alta/edición/borrado, ingresos, gastos recurrentes, categorías con tipo y límite — todo sobre endpoints existentes.
- [x] Registro rápido por frase: `POST /expenses/parse` → pantalla de confirmación → `POST /expenses`.
- [x] Voz: `speech_to_text` (reconocimiento en el dispositivo) y el texto resultante va al mismo flujo de parseo. Cierra el hueco "por voz" del plan original sin tocar el backend.

**Aceptación**: decir "me compré un helado de 5000" crea el gasto tras confirmar y el dashboard se actualiza.
✅ **Hecho y probado en un teléfono**, por texto y por voz. Del uso real salieron dos correcciones (el modo JSON de Groq y los miles con coma del dictado) y que la frase puede ser un ingreso.

### Fase 3 — OCR de recibos (A-01, A-04)

- [x] App: `image_picker`/cámara + `google_mlkit_text_recognition`; envía solo el texto reconocido.
- [x] Backend: `POST /expenses/parse-receipt` — nuevo prompt en `backend/app/services/prompts.py` y función en `groq_client.py` reutilizando la validación de `parse_expense_text` (monto, categoría válida, fecha), más `comercio`. Mismo manejo 422/502 que `/expenses/parse`.
- [x] Misma pantalla de confirmación de la Fase 2; `source="ocr"`.

**Aceptación**: foto de un recibo real → monto, comercio, fecha y categoría propuestos correctamente en la mayoría de 10 recibos de prueba; un recibo ilegible da error controlado.
🟡 **Backend validado** (tests + HTTP real contra Postgres). **La foto de un recibo real no se ha probado en el teléfono**: sigue pendiente la prueba con 10 recibos.

### Fase 4 — Coach (C-01, C-02, C-04, C-07)

Módulo backend independiente: `routers/coach.py`, `routers/checkins.py`, `services/patterns.py`, `services/coach.py`, modelos `EmotionalCheckin` y `CoachMessage`.

- [x] **Check-in diario**: `POST/GET /checkins` (ánimo, nota opcional, uno por día). Recordatorio con `flutter_local_notifications`.
- [x] **Patrones** (`patterns.py`, determinista y testeable): gasto fin de semana vs entre semana por categoría, variación contra la semana anterior, categoría dominante, relación ánimo ↔ gasto.
- [x] **Mensaje al registrar** (C-01): `POST /coach/reaction` para un gasto; la app lo pide en segundo plano tras guardar (no bloquea el registro). Si Groq falla, plantilla local.
- [x] **Consejos accionables** (C-04): `GET /coach/insights` — la IA redacta a partir de los patrones calculados y cada consejo trae una acción de un tap (`{tipo, payload}`: apartar a una meta, aceptar un reto, poner límite a una categoría) que la app ejecuta con endpoints normales tras tu aprobación. Se cachea por día en `CoachMessage`.
- [x] **Chat con el coach**: `POST /coach/chat`, con el resumen del presupuesto y patrones como contexto.
- [x] **Guardrails** en el prompt y con tests: tono elegido, cero lenguaje culposo, sin recomendar inversiones concretas, explica el porqué de cada sugerencia.
- [ ] Evaluar `openai/gpt-oss-120b` para el coach (el parseo sigue con el modelo chico); confirmar modelos disponibles en Groq en ese momento. Por ahora el modelo chico resultó suficiente redactando con razonamiento `medium`.

**Aceptación**: tras una semana de datos de prueba con gasto alto en fines de semana, el coach lo menciona con cifras correctas, en el tono configurado, y su acción de un tap funciona.
✅ **Validado con tests y con la IA real en un teléfono**: con tres semanas de datos de prueba el coach menciona el patrón de fin de semana con sus cifras, en el tono elegido, y la acción de un toque crea el reto. Con la IA real apareció que inventaba cifras; hay un guardrail nuevo que las descarta.

### Fase 5 — Gamificación (G-01 a G-04)

Módulo backend: `routers/goals.py`, `routers/gamification.py`, `services/gamification.py`; modelos `Goal`, `GoalContribution`, `Challenge`, `Achievement`, `PointEvent`.

- [x] **Metas con verificación**: los aportes son apartados virtuales; solo se aceptan si hay disponible. `calculate_budget_summary` (`backend/app/services/budget_calculator.py`) gana `apartado_total` y `disponible_total = monto_total + ingresos − gastado − apartado`. La meta se cumple por cálculo, nunca por auto-reporte.
- [x] **Puntos y niveles**: libro `PointEvent` idempotente (clave única por evento). Reglas basadas en consistencia y mejora de ratios (`ratio_ahorro`, `consistencia`, `mejora_mensual` de `mejoras.md`), no en montos.
- [x] **Rachas, retos e insignias**: `sync_gamification(session, user_id)` calculado al vuelo al consultar el perfil, siguiendo el patrón de `backend/app/services/recurring_expenses.py`. Retos desde plantillas alimentadas por `patterns.py` (reducir X % una categoría, días sin gasto opcional, N check-ins).
- [x] App: pantallas Metas y Retos, anillos/barras de progreso, celebración al desbloquear.

**Aceptación**: aceptar un reto de "reducir 20 % ocio", registrar gastos que lo cumplen y ver puntos + insignia otorgados sin intervención manual; repetir la consulta no duplica puntos.
✅ **Validado con tests** (`backend/tests/test_gamification.py`), por HTTP real contra Postgres y en un teléfono: el reto de reducir 20 % se cumple solo al cerrar la ventana, otorga puntos e insignia, y repetir la consulta no duplica nada.

### Fase 6 — APK de release y beta cerrada

- [x] Keystore, `key.properties`, ícono, nombre y splash.
- [x] Workflow `mobile-release.yml`: en cada tag `v*` compila el APK firmado y lo adjunta al GitHub Release.
- [x] Pantalla de privacidad (qué datos se usan y por qué) y borrado de cuenta desde Perfil.
- [ ] Repartir a probadores y recoger feedback.

**Aceptación**: un probador instala el APK desde el enlace, entra con Google y registra un gasto contra el backend de producción.
🟡 **Firma, ícono y workflow configurados, pero todavía no existe un APK de release**: la app solo ha corrido en modo depuración. El workflow de release está escrito pero no se ha ejecutado (necesita los secretos del keystore y `API_BASE_URL` en GitHub), y el keystore está en el PC de la primera iteración. El login con Google y el backend de producción dependen de los dos pendientes de la Fase 0.

### Fase 7 — Prioridad baja (después de la beta)

- [x] **Wrapped mensual** (G-08): `GET /reports/monthly-wrapped` + pantalla tipo historias.
- [x] **SMS bancarios** (A-03): canal nativo Android aislado en `mobile/lib/features/sms/`; el texto del SMS pasa por el parseo existente y cae en una bandeja "por confirmar" (`source="sms"`). Probado en un teléfono con SMS insertados por `adb`; no con mensajes reales de un banco.

### Fase 8 — Después del plan original (12 y 13 de octubre)

No estaba en el plan; salió de usar la app en un teléfono. Todo hecho y con tests.

- [x] **Rediseño "Bento suave"** de todas las pantallas: sistema de diseño (`mobile/lib/core/`), coach con avatar animado, barra inferior flotante.
- [x] **Ingresos por texto, voz o SMS**: `/expenses/parse` devuelve `tipo` y la app abre el formulario que corresponde.
- [x] **Notificaciones** en la app: campana en el inicio con los pagos por hacer y los SMS por revisar; aprobar un SMS sin salir de la lista.
- [x] **Gastos fijos semanales o mensuales**: quedan por pagar el día que vencen, con notificación local a las 9:00; confirmar el pago es lo que descuenta (`/recurring-expenses/pending`, `/pay`, `/skip`).
- [x] **Límite propio sobre categorías por defecto** (`category_limits`); transporte, salud y servicios pasan a gasto fijo.
- [x] **Más gamificación**: 6 tipos de reto y 23 insignias.
- [x] **Guardrail de cifras** en consejos, reacción y reporte semanal; el reporte semanal bajo las reglas del coach.
- [x] **Historia de usuario completa** con una cuenta de prueba (ver notas, sección 9).

**Lo siguiente** (no empezado): subir la rama, desplegar el backend, plan de pago de Groq, APK de release, una bienvenida para usuarios nuevos y una beta de 30 a 50 personas para medir retención.

## Convenciones a respetar (del plan anterior)

- Un schema Pydantic de entrada y otro de salida por endpoint; nunca devolver el modelo SQLModel.
- Prompts solo en `backend/app/services/prompts.py`.
- Migración Alembic por fase; `bcrypt==4.0.1` fijo.
- Tests herméticos: Groq mockeado con los fixtures de `backend/tests/conftest.py`.
- Si una fase invalida una decisión previa, se señala antes de continuar.

## Verificación

- **Backend** (cada fase): `uv run pytest` y `uv run ruff check .` en `backend/`; probar endpoints nuevos con HTTP real contra Postgres en Docker (`docker compose up --build`).
- **App** (cada fase): `flutter analyze`, `flutter test` (widgets y lógica de cada feature) y recorrido manual del criterio de aceptación en un teléfono físico.
- **APK**: `flutter build apk --release`, instalar con `adb install` en un teléfono limpio y repetir el flujo completo contra producción; verificar que una versión nueva actualiza sobre la anterior sin desinstalar.
