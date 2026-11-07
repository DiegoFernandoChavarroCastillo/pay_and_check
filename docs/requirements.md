# Documento de requerimientos – Pay and Check

Fecha: 2026-11-07

## 1. Introducción

Pay & Check es una app Android de finanzas personales que registra gastos e ingresos con muy poca fricción y acompaña a la persona con un coach de IA que no regaña. Este documento fija qué debe hacer el sistema (requerimientos funcionales) y con qué calidad (no funcionales).

**Alcance.** App móvil Flutter, API REST (FastAPI) y base PostgreSQL. Queda fuera: conexión con bancos, iOS, web, servidor de notificaciones push y movimiento de dinero real.

| Término | Significado |
| --- | --- |
| Movimiento | Gasto o ingreso registrado por la persona |
| Borrador | Movimiento propuesto por la IA (texto, voz, recibo o SMS) que la persona confirma o edita |
| Disponible por día | Dinero que se puede gastar hoy sin agotar el presupuesto del periodo |
| Gasto fijo | Pago recurrente semanal o mensual que se descuenta solo al confirmarlo |
| Reto | Desafío con verificación automática a partir de datos reales |
| Guardrails | Filtros que descartan salidas de la IA con culpa, asesoría de inversión o cifras inventadas |

## 2. Descripción general

Las apps de finanzas suelen ser contadores pasivos que la gente abandona por pereza o culpa; Pay & Check busca que registrar sea casi gratis y que cada interacción deje una acción clara y sin reproche.

**Usuario objetivo.** Persona con smartphone Android que quiere controlar su gasto diario sin hojas de cálculo. Idiomas: español e inglés.

**Actores externos.**

| Actor | Rol |
| --- | --- |
| Groq (LLM) | Interpreta texto, voz, recibos y SMS; redacta mensajes del coach |
| Google Identity | Inicio de sesión con Google |
| SMS del banco | Origen de movimientos detectados, leídos con permiso |
| Servicios del dispositivo | Cámara, micrófono, OCR en el teléfono y notificaciones locales |

**Supuestos y dependencias.**

- La persona concede los permisos de cámara, micrófono, SMS y notificaciones solo si quiere usar esas funciones.
- El backend corre en Render (plan gratuito, se duerme) con PostgreSQL en Neon.
- Si Groq falla o falta la clave, la app sigue funcionando con formulario manual y textos de respaldo.
- La app se distribuye como APK directo, sin tienda.

## 3. Requerimientos funcionales

El sistema debe cubrir 40 requerimientos en siete módulos; todos están implementados salvo los marcados como parciales o pendientes.

| ID | Módulo | Requerimiento | Estado |
| --- | --- | --- | --- |
| RF-01 | Cuenta | Registrarse e iniciar sesión con correo y contraseña (el correo no distingue mayúsculas) | Hecho |
| RF-02 | Cuenta | Iniciar sesión con Google, verificando el token en el servidor | Hecho |
| RF-03 | Cuenta | Renovar la sesión con token de refresco sin pedir credenciales | Hecho |
| RF-04 | Cuenta | Editar perfil: tono del coach (motivador, directo, con humor, minimalista), idioma y zona horaria | Hecho |
| RF-05 | Cuenta | Borrar la cuenta y todos los datos de la persona | Hecho |
| RF-06 | Presupuesto | Definir el presupuesto de un periodo | Hecho |
| RF-07 | Presupuesto | Mostrar el disponible por día como número central de la app | Hecho |
| RF-08 | Presupuesto | Avisar cuando el presupuesto no alcanzaría al ritmo de gasto actual | Parcial |
| RF-09 | Categorías | Ofrecer categorías por defecto y permitir crear propias | Hecho |
| RF-10 | Categorías | Fijar un límite propio por categoría, también sobre las por defecto | Hecho |
| RF-11 | Movimientos | Registrar, consultar, editar y borrar gastos manualmente | Hecho |
| RF-12 | Movimientos | Registrar ingresos | Hecho |
| RF-13 | Movimientos | Registrar por frase escrita o dictada; la IA devuelve un borrador con categoría y tipo (gasto o ingreso) | Hecho |
| RF-14 | Movimientos | Registrar por foto de un recibo, con OCR en el teléfono e interpretación por IA | Hecho |
| RF-15 | Movimientos | Detectar movimientos en SMS del banco al abrir la app y proponerlos como borrador | Hecho |
| RF-16 | Movimientos | Confirmar, editar u omitir cada borrador antes de guardarlo; nada se guarda sin aprobación | Hecho |
| RF-17 | Gastos fijos | Programar pagos semanales o mensuales | Hecho |
| RF-18 | Gastos fijos | Avisar con notificación el día del vencimiento; el pago se descuenta solo al confirmarlo | Hecho |
| RF-19 | Gastos fijos | Pagar u omitir un vencido, sin duplicar el cobro de una misma fecha | Hecho |
| RF-20 | Notificaciones | Centralizar en la app los pagos por hacer y los movimientos detectados en SMS | Hecho |
| RF-21 | Coach | Check-in emocional diario de un minuto | Hecho |
| RF-22 | Coach | Mostrar una reacción contextual al registrar un movimiento | Hecho |
| RF-23 | Coach | Mostrar consejos del día, cada uno con una acción de un toque | Hecho |
| RF-24 | Coach | Chat con el coach | Hecho |
| RF-25 | Coach | Nunca usar lenguaje culposo ni recomendar inversiones | Hecho |
| RF-26 | Coach | Predecir déficit cruzando calendario y flujo de caja | Pendiente |
| RF-27 | Metas | Crear metas de ahorro y apartar dinero dentro del presupuesto | Hecho |
| RF-28 | Retos | Sugerir y aceptar retos de 6 tipos, según los datos de la persona | Hecho |
| RF-29 | Retos | Verificar retos a partir de gastos y check-ins reales, sin auto-reporte | Hecho |
| RF-30 | Gamificación | Otorgar puntos, niveles, racha y 23 insignias, con libro de puntos idempotente | Hecho |
| RF-31 | Reportes | Gráfica de gasto por semana | Hecho |
| RF-32 | Reportes | Reporte semanal redactado por el coach | Hecho |
| RF-33 | Reportes | Resumen mensual (wrapped) | Hecho |
| RF-34 | Reportes | Análisis por semana con desglose por categoría | Hecho |
| RF-35 | Interfaz | Interfaz completa en español e inglés | Hecho |
| RF-36 | Interfaz | Notificaciones locales programadas en el teléfono | Hecho |
| RF-37 | Resiliencia | Si la IA falla, ofrecer formulario manual y textos de respaldo | Hecho |
| RF-38 | Social | Ligas, competición y retos colaborativos | Pendiente |
| RF-39 | Automatización | Leer correos y detectar suscripciones | Pendiente |
| RF-40 | Automatización | Sincronizar con calendario | Pendiente |

## 4. Requerimientos no funcionales

| ID | Categoría | Requerimiento |
| --- | --- | --- |
| RNF-01 | Veracidad | La IA redacta pero no calcula: toda cifra sale de código determinista y se descarta el texto que traiga cifras ausentes del dato de origen |
| RNF-02 | Seguridad | Autenticación con JWT de acceso y refresco; contraseñas con hash bcrypt; tokens en almacén seguro del teléfono |
| RNF-03 | Seguridad | Cada persona accede solo a sus datos; el hash de la contraseña nunca sale por la API |
| RNF-04 | Privacidad | Los SMS se leen solo con permiso y bajo demanda; cada movimiento se aprueba antes de guardarse |
| RNF-05 | Privacidad | Los secretos viven en variables de entorno, nunca en el repositorio |
| RNF-06 | Disponibilidad | `/health` verifica la conexión a la base; la app funciona sin IA |
| RNF-07 | Escalabilidad | API stateless, sin tareas programadas: retos, pagos pendientes y puntos se recalculan al consultar |
| RNF-08 | Mantenibilidad | Backend en capas (routers, services, models); la IA aislada en `groq_client.py` y `prompts.py` |
| RNF-09 | Mantenibilidad | Esquema versionado con Alembic; dependencias fijadas con `uv.lock` |
| RNF-10 | Calidad | Pruebas automáticas: 108 en el backend (pytest) y 42 en la app (flutter test), ejecutadas en CI |
| RNF-11 | Usabilidad | Registrar un movimiento debe tomar pocos toques; el coach no usa lenguaje culposo y el tono es configurable |
| RNF-12 | Localización | Español e inglés; "hoy" se calcula con la zona horaria de la persona (por defecto America/Bogota) |
| RNF-13 | Portabilidad | La API puede ser reutilizada por otros clientes sin cambiar la lógica |
| RNF-14 | Despliegue | Backend en contenedor Docker; CI y APK de release con GitHub Actions |
| RNF-15 | Compatibilidad | Android; los SMS requieren código nativo Kotlin aislado en un solo módulo |
| RNF-16 | Documentación | API documentada con OpenAPI en `/docs` |

## 5. Restricciones, riesgos y criterios de aceptación

**Restricciones.**

- Sin conexión a bancos: los aportes a metas son dinero virtual.
- Sin servidor de push: los avisos son notificaciones locales.
- Stack fijo: Python 3.12 + FastAPI + PostgreSQL, Flutter/Dart, Groq como proveedor de IA.
- Hosting gratuito: el backend puede tardar en responder tras dormirse.

**Riesgos.**

| Riesgo | Mitigación |
| --- | --- |
| Groq no responde o cambia su plan gratuito | Formulario manual y textos de respaldo; proveedor aislado en un solo archivo |
| El OCR no se ha probado con recibos reales | Todo recibo pasa por borrador que la persona confirma |
| El formato de los SMS varía entre bancos | Cada movimiento detectado se aprueba u omite manualmente |
| El modelo inventa cifras o regaña | Guardrails con texto de respaldo y pruebas del coach |

**Criterios de aceptación.**

- Los 108 tests del backend y los 42 de la app pasan en CI.
- Un movimiento escrito, dictado, fotografiado o recibido por SMS llega a un borrador editable y solo se guarda al confirmarlo.
- El disponible por día cambia de inmediato al registrar un gasto, un ingreso o un pago fijo.
- Con `GROQ_API_KEY` ausente, la app sigue permitiendo registrar y ver reportes.
- Ningún texto del coach contiene lenguaje culposo, asesoría de inversión ni cifras ajenas a los datos.
