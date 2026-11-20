# Política de privacidad de Pay&Check

**Versión 2026-11.** Este texto es el mismo que muestra la app (`mobile/lib/features/auth/privacy_policy.dart`).
Si cambia uno, cambia el otro, y se sube la versión en la app (`politicaVersion`, `core/config/app_config.dart`) y en
el backend (`POLITICA_VERSION`, `app/core/config.py`). Con la versión nueva, cada cuenta vuelve a ver la política y
la acepta al entrar.

Esta página está lista para publicarse en una URL pública (GitHub Pages) y enlazarla desde el perfil (PS-48).

---

## Quién es responsable

Pay&Check es un proyecto académico en fase piloto. El equipo de Pay&Check es el responsable del tratamiento de tus
datos personales, conforme a la Ley 1581 de 2012 (habeas data) y al Decreto 1377 de 2013.

## Qué datos guardamos

- **Tu cuenta:** nombre, correo y una contraseña cifrada o tu identificador de Google; idioma y zona horaria.
- **Tus finanzas en la app:** presupuestos, gastos, ingresos, gastos fijos, metas de ahorro, check-ins de ánimo,
  retos, puntos y tus conversaciones con el coach.
- **Tu plan y tu uso de la IA:** cuántas solicitudes de IA haces, tokens y tiempo de respuesta. En ese registro no
  se guarda lo que escribes.
- **Tu consentimiento:** la fecha y la versión de la política que aceptaste, y si permitiste leer tus SMS.

## Qué se queda en tu teléfono

- **La voz:** tu teléfono la convierte en texto; la app solo recibe el texto.
- **Las fotos de recibos:** el texto se reconoce en tu teléfono. La foto nunca se sube.
- **Los SMS del banco:** solo si lo permites aparte. Se leen en tu teléfono y no se guardan en nuestro servidor.
- **Las notificaciones de tus apps de pago (Nequi, Daviplata, Bancolombia, Nu…):** solo si activas el acceso en
  los ajustes de Android, con el mismo consentimiento de los SMS. La app solo mira las notificaciones de una lista
  fija de apps financieras (`BankNotificationListener.kt`), las guarda en tu teléfono (las últimas 300) y nada
  sale de él hasta que eliges registrar un movimiento.

## Qué se envía al servicio de IA

Para entender lo que escribes y redactar los mensajes del coach usamos Groq, un servicio de IA con servidores en
Estados Unidos (transferencia internacional de datos). Si Groq no responde y el respaldo está configurado, la misma
solicitud va a DeepInfra, también en Estados Unidos, con el mismo modelo (`AI_FALLBACK_*`). Enviamos:

- tu nombre de pila;
- el texto que escribes o dictas para registrar un movimiento;
- el texto del SMS o del recibo que eliges registrar;
- tus mensajes del chat, con los últimos 10 turnos;
- un resumen de tus cifras: disponible, totales, categorías, descripciones de gastos y nombres de metas.

Nunca enviamos tu correo, tu contraseña, tu identificador de Google, tu ubicación, tus fotos ni los SMS que no
elegiste. La IA no guarda nada por su cuenta: tú confirmas cada movimiento antes de guardarlo.

## Para qué los usamos

Para calcular cuánto puedes gastar, registrar tus movimientos, darte consejos, llevar tus retos y aplicar el cupo de
IA de tu plan. No vendemos tus datos, no los usamos para publicidad y no tomamos decisiones automáticas con efectos
legales sobre ti.

## Dónde se guardan y por cuánto tiempo

En proveedores en la nube: la API en Render y la base de datos PostgreSQL en Neon. Tus datos se guardan mientras
tengas cuenta. Al borrar tu cuenta se elimina todo de inmediato y para siempre.

## Cómo los protegemos

Conexiones cifradas (HTTPS), contraseñas guardadas solo como hash, sesiones que expiran, límites de solicitudes y
capas que impiden que la IA obedezca instrucciones escondidas en tus datos.

## Tus derechos

Puedes conocer, actualizar, rectificar y suprimir tus datos y revocar esta autorización cuando quieras:

- edita tu perfil;
- quita el permiso de SMS en los ajustes de Android, y el acceso a notificaciones en Ajustes → Acceso a
  notificaciones;
- borra tu cuenta en **Perfil › Eliminar mi cuenta**.

Si no quedas conforme con nuestra respuesta, puedes presentar una queja ante la Superintendencia de Industria y
Comercio (SIC).

> **Pendiente:** definir el correo de contacto del equipo para ejercer estos derechos. En la app se fija al compilar
> con `--dart-define=PRIVACY_CONTACT=...` y aparece en esta sección.

## Menores de edad

Si eres menor de 18 años, necesitas la autorización de tu padre, madre o representante legal para usar la app.

## Cambios

Si esta política cambia, la app te mostrará la nueva versión y te pedirá aceptarla de nuevo antes de seguir.

---

## Cómo se aplica en el código

| Qué | Dónde |
|---|---|
| Casilla obligatoria en el registro | `mobile/lib/features/auth/auth_screens.dart` (`PolicyCheckbox`) |
| El backend rechaza el registro sin aceptar (422) | `backend/app/routers/auth.py` → `register` |
| Cuentas de Google o con una versión anterior: pantalla bloqueante | `mobile/lib/app.dart` (`/consent`), `PUT /auth/me/consent` |
| Consentimiento antes del permiso de SMS | `mobile/lib/features/sms/sms_inbox_screen.dart` (`permitirSms`), `PUT /auth/me/consent/sms` |
| Versión y fecha aceptadas | `users.politica_version`, `users.politica_aceptada_at`, `users.sms_consent_at` |
| Borrar la cuenta en dos pasos y sin dejar filas | `profile_screen.dart` (`confirmarBorrado`), `tests/test_consentimiento.py` |

## Apoyos de la universidad y plan Familiar

- **Apoyos:** con plan Institucional, la app muestra los apoyos que ofrece tu universidad y te los sugiere solo
  cuando tus cifras lo justifican (el presupuesto no alcanza o marcaste ansiedad o preocupación 3 o más días en
  dos semanas). Ese cálculo se hace en nuestro servidor con tus datos y no se le comunica a nadie. Si tocas «Me
  interesa», la universidad solo ve cuántos estudiantes se interesaron en cada apoyo (y solo si son 5 o más),
  nunca quién. El contacto lo haces tú.
- **Plan Familiar:** quien paga el plan puede ver tu progreso agregado (racha, constancia, cuántas metas tienes
  y qué tan avanzadas van, y si tu presupuesto alcanza) **solo si tú lo activas** en Mi plan. Nunca ve tus
  gastos, tus montos ni tus check-ins. Lo puedes apagar cuando quieras.
- **Vacas:** los nombres de las personas que te deben se guardan como texto en tu cuenta; no se les escribe ni
  se crean cuentas para ellas. El mensaje de cobro lo envías tú desde tu teléfono.

## Panel de Bienestar Universitario

La universidad que paga el plan Institucional ve un panel web (`GET /panel/{id}?token=…`) con **solo cifras
agregadas y anónimas** de sus estudiantes: uso de la app, porcentaje con presupuesto en riesgo, con meta de ahorro
y con señales de estrés financiero (3 o más check-ins de ansiedad o preocupación en dos semanas), distribución de
ánimo, categorías de gasto y tendencia semanal. Ningún indicador se calcula sobre menos de 5 estudiantes
(anonimato k ≥ 5) y el panel nunca muestra nombres, correos, descripciones ni montos individuales
(`backend/app/services/panel.py`, pruebas en `tests/test_panel.py`).
