# Modelo de amenazas — Pay&Check

Modelo de amenazas corto del backend (FastAPI en AWS EC2 detrás de Caddy, con Render de respaldo; Postgres en
Neon; IA vía Groq) y de sus dos clientes (APK Android y versión web en Vercel). Cada amenaza lleva el
control que **existe hoy en el código**, citado por archivo y función. Lo que no está resuelto se marca como
**riesgo aceptado** (decisión consciente para el piloto) o **riesgo abierto** (hallazgo pendiente de arreglo).

Documentos relacionados (algunos viven todavía en otras ramas):

- [docs/ia.md](ia.md) — inventario de las tareas de IA y qué datos usa cada una (rama `feature/PS-105-docs-ia`).
- [docs/informe-adversarial.md](informe-adversarial.md) — resultados de la suite de prompt injection
  (rama `feature/PS-102-adversarial`).
- [docs/decisiones/009-capas-seguridad-ia.md](decisiones/009-capas-seguridad-ia.md) — ADR de las capas de
  defensa de la IA (rama `feature/PS-106-adr`).

## Activos

| Activo | Dónde vive | Por qué importa |
|---|---|---|
| Datos financieros de la persona (gastos, ingresos, presupuestos, metas, check-ins emocionales, chat del coach) | Postgres (Neon) | Información personal y sensible; es lo que la app promete cuidar. |
| Credenciales | `users.hashed_password` (bcrypt), tokens JWT en el teléfono o en el navegador (versión web) | Dan acceso a todo lo anterior. |
| Secretos del servidor | `JWT_SECRET`, `DATABASE_URL`, `GROQ_API_KEY`, `GOOGLE_CLIENT_ID` en variables de entorno | Con `JWT_SECRET` se falsifica cualquier sesión; con `DATABASE_URL` se lee toda la base. |
| Saldo de la cuenta de Groq | Proveedor externo | Cada llamada cuesta: es el blanco del abuso económico. |
| Prompts del sistema y reglas del coach | `backend/app/services/prompts.py` | Su filtración o anulación permite sacar al coach de su rol. |

## Actores

- **Persona usuaria legítima** — usa la app; puede equivocarse o pegar texto de terceros sin saberlo.
- **Atacante externo sin cuenta** — prueba contraseñas, reutiliza tokens robados, llama a la API directo.
- **Atacante con cuenta propia** — se registra gratis y abusa de la IA o intenta inyecciones de prompt.
- **Tercero que inyecta contenido** — escribe el SMS bancario o el recibo que la persona luego pega o escanea
  (inyección indirecta).
- **Proveedores** — Groq, Render y Neon: reciben o alojan datos; se confía en ellos, pero se limita lo que ven.

## Amenazas y controles

### A1. Robo o falsificación de sesión (JWT y refresh)

- **Control.** `backend/app/core/security.py`: `_create_token` firma con `JWT_SECRET` (HS256) y mete un claim
  `type`; `_decode_token` rechaza un token de otro tipo, así un refresh token no sirve como access token
  (`decode_access_token`) ni al revés (`decode_refresh_token`). Access de 60 min y refresh de 30 días
  (`backend/app/core/config.py`, `Settings`). `backend/app/deps.py`, `get_current_user`, además de validar la
  firma, comprueba que el usuario siga existiendo. `POST /auth/refresh` (`backend/app/routers/auth.py`,
  `refresh`) entrega un par nuevo.
- **Riesgo aceptado.** Los tokens son stateless: no hay lista de revocación ni rotación con detección de reuso.
  Un refresh token robado sirve hasta 30 días (lo dice el docstring de `create_refresh_token`). No hay
  "cerrar sesión en todos los dispositivos" salvo cambiar `JWT_SECRET`, que cierra la de todos.

### A2. Fuerza bruta de contraseñas en el login

- **Control.** `backend/app/core/rate_limit.py`: `revisar_login`, `registrar_fallo_de_login` y
  `limpiar_fallos_de_login`, llamados desde `login` en `backend/app/routers/auth.py`. Máximo 10 intentos
  **fallidos** en 5 minutos por IP **y** por email (`MAX_FALLOS_LOGIN`, `VENTANA_LOGIN_S`); al bloquearse
  responde 429 con `Retry-After` sin comprobar la contraseña. Un login correcto perdona los fallos del email,
  no los de la IP. Las contraseñas se guardan con bcrypt (`hash_password`, `verify_password`).
- **Riesgo aceptado — IP detrás de Render.** `ip_del_cliente` usa `request.client.host`, que uvicorn reescribe
  desde `X-Forwarded-For` porque `backend/start.sh` arranca con `--proxy-headers --forwarded-allow-ips='*'`.
  Con `'*'`, uvicorn (0.52, `ProxyHeadersMiddleware`) confía en todos los saltos y toma la **primera** IP de la
  cabecera, que el cliente puede escribir a su gusto. Un atacante que rote ese valor evade el contador por IP;
  el contador por email sigue frenando el ataque a una cuenta concreta, pero no el *password spraying*
  (una contraseña contra muchos emails). Arreglo posible: confiar solo en el rango del proxy de Render o tomar
  la última IP añadida por él.
- **Riesgo aceptado — contadores en memoria.** `LimiteDeTasa` guarda los eventos en un `dict` del proceso: se
  borran con cada despliegue o reinicio (en el plan gratis de Render, cada vez que el servicio se duerme) y con
  más de una instancia cada una lleva su cuenta. Vale para el piloto con una instancia; para escalar haría
  falta Redis (lo anota el docstring del módulo).

### A3. Llamadas desde un origen web no autorizado (CORS)

- **Control.** `backend/app/main.py`: `CORSMiddleware` con `allow_origins=settings.cors_origins_list`, una
  lista explícita leída de `CORS_ORIGINS` (`Settings.cors_origins_list` en `backend/app/core/config.py`), nunca
  `*`. La autenticación va en la cabecera `Authorization: Bearer`, no en cookies, así que un sitio ajeno no
  puede montar un CSRF con la sesión de la persona.
- **Desde la versión web (nov 2026)** CORS sí está en el camino crítico: `CORS_ORIGINS` debe listar
  `https://pay-and-check-seven.vercel.app`. Se agrega el dominio exacto, nunca un comodín de `*.vercel.app`, que
  dejaría llamar a la API desde cualquier proyecto de Vercel.
- **Nota.** CORS solo protege a navegadores: la app móvil y cualquier script llaman a la API sin pasar por él.
  La defensa real de cada endpoint es `get_current_user`. `allow_methods` y `allow_headers` están abiertos
  (`["*"]`); con orígenes acotados es aceptable.

### A4. Fuga de secretos (`.env`)

- **Control.** `backend/app/core/config.py`, `Settings`, lee los secretos de variables de entorno o de
  `.env`; ningún secreto tiene valor por defecto en el código (`JWT_SECRET` y `DATABASE_URL` son
  obligatorios). `.gitignore` excluye `.env` y `.env.*` (salvo `.env.example`, que solo trae marcadores).
  En producción, `render.yaml` hace que Render genere `JWT_SECRET` (`generateValue: true`) y deja
  `DATABASE_URL` y `GROQ_API_KEY` como `sync: false`, cargadas a mano en el panel. El manejador
  `unhandled_exception_handler` de `backend/app/main.py` devuelve un mensaje genérico y no filtra trazas ni
  configuración en un 500.
- **Riesgo aceptado.** No hay rotación periódica de secretos ni un gestor de secretos; un `.env` copiado en una
  máquina de desarrollo queda fuera de control.

### A4b. Sesión guardada en el navegador (versión web)

- **Control.** La versión web usa `flutter_secure_storage` para web, que cifra los tokens con WebCrypto antes de
  guardarlos en el almacenamiento del navegador. La API solo acepta el token por cabecera, no por cookie, y el
  sitio se sirve por HTTPS (Vercel) con `X-Content-Type-Options: nosniff` (`mobile/web/vercel.json`).
- **Riesgo aceptado.** En un navegador la llave de cifrado vive en el mismo origen, así que un script inyectado
  en la página (XSS) o una extensión maliciosa podría leer la sesión. Flutter no inyecta HTML con datos de la
  persona, lo que reduce el XSS, pero no hay *Content-Security-Policy*. Para el piloto se acepta; en un
  computador compartido conviene cerrar sesión.

### A4c. Contraseñas débiles y abuso de canjes

- **Control.** `backend/app/schemas/auth.py`, `NuevaContrasena`: al registrarse se exigen 8 caracteres y se
  rechazan contraseñas obvias o de pocos caracteres distintos. `core/rate_limit.py`: `revisar_canje` limita los
  códigos de plan fallidos a 5 cada 15 minutos (429 con `Retry-After`). `schemas/common.py`: montos entre 0 y
  1.000 millones y textos con tope de largo; `services/validaciones.py` rechaza fechas futuras. Todo con
  pruebas en `tests/test_validaciones_e2e.py` (hallazgos de la prueba de punta a punta del 20 nov 2026).

### A5. Prompt injection directa e indirecta

- **Control.** Capas en `backend/app/services/ia_seguridad.py` (detalle en el ADR 009):
  1. `como_datos` envuelve el texto libre (dictado, SMS, OCR del recibo, mensajes del chat y su historial) en
     `<datos_usuario>…</datos_usuario>` y borra cualquier etiqueta de cierre que traiga.
  2. `sanear_dato` deja los nombres (persona, metas, categorías) en una línea, sin `<`, `>` ni comillas
     triples y con 40 caracteres como máximo (`MAX_DATO`).
  3. `marca_inyeccion` etiqueta patrones de ataque (solo registra, no bloquea).
  4. `filtra_salida` revisa la respuesta: fragmentos literales del prompt, URLs, código/HTML y largo excesivo;
     `rompe_guardrails` e `inventa_cifras` (`backend/app/services/coach.py`) añaden culpa, asesoría de
     inversión y cifras inventadas.
  5. Contratos estrictos: `_validar_gasto` (`backend/app/services/groq_client.py`) valida el JSON del gasto
     (categoría de la lista, montos y fechas con topes) y el chat exige `{"en_alcance", "respuesta"}`
     (`responder_chat`), con frase fija de redirección si el tema es ajeno.
- **Riesgos abiertos.** Ver R1 y R3 más abajo.

### A6. Abuso económico de la IA ("denial of wallet")

- **Control.** Dos topes independientes:
  - Por minuto: `limite_ia` en `backend/app/core/rate_limit.py`, dependencia de todos los endpoints que llaman
    a Groq (`/expenses/parse`, `/expenses/parse-receipt`, `/expenses/from-text`, `/coach/reaction`,
    `/coach/insights`, `/coach/chat`, `/reports/weekly`, `/reports/monthly-wrapped`): 20 solicitudes por
    persona y minuto, sumadas entre endpoints.
  - Por mes: `cupo_agotado` y `cupo_de` en `backend/app/services/ia_uso.py`; el cupo sale del plan
    (`CUPOS` en `backend/app/services/planes.py`) y en el plan Familiar se comparte. `_chat` en
    `groq_client.py` lo comprueba **antes** de llamar a Groq; agotado, la persona recibe el respaldo
    determinista (402 en el parseo). Cada llamada queda en `ai_usage` con su propio commit (`_guardar`).
  - Además: `GROQ_TIMEOUT_S = 15` y `GROQ_MAX_REINTENTOS = 0` acotan cuánto dura y se repite cada llamada, y el
    texto del recibo tiene tope de 6000 caracteres (`ReceiptParseRequest`) y el del chat de 1000
    (`ChatRequest` en `backend/app/schemas/coach.py`).
- **Riesgo aceptado.** La revisión del cupo y el registro no son atómicos (lo dice `cupo_agotado`): peticiones
  simultáneas pueden pasarse por unas pocas llamadas. El límite por minuto comparte las limitaciones de
  memoria de A2. Registrarse es gratis, así que muchas cuentas multiplican el cupo del plan Gratis.
- **Riesgo abierto.** Ver R2: `/expenses/parse` no limita el largo del texto, así que una sola solicitud puede
  costar muchos tokens.

### A7. Datos personales que salen a Groq

- **Control.** Se manda lo mínimo y nada identificable de forma directa:
  - Parseo (`parse_expense_text`, `parse_receipt_text`): el texto que escribió o escaneó la persona y la lista
    de nombres de categoría.
  - Coach (`contexto_financiero` en `backend/app/services/coach.py`): totales agregados del presupuesto,
    nombres de metas saneados y patrones detectados; la reacción añade el gasto recién registrado; el chat,
    el historial de mensajes (`HISTORIAL_CHAT`). El nombre de pila entra saneado en `build_coach_rules`.
  - Reporte semanal (`summary_to_text` en `backend/app/services/weekly_report.py`): totales por categoría,
    "nunca transacciones individuales".
  - Nunca sale el email, el id de usuario, contraseñas ni tokens. `ai_usage` no guarda ningún texto de la
    persona (`backend/app/models/ai_usage.py`), solo tarea, modelo, tokens, latencia y resultado.
- **Riesgo aceptado.** Lo que la persona escribe en el chat o dicta viaja tal cual; si mete datos sensibles
  (un número de cuenta), llegan a Groq. La retención de Groq queda fuera de nuestro control y no se puede
  borrar desde el borrado de cuenta.

### A8. Borrado de cuenta incompleto (derecho a eliminar los datos)

- **Control.** `delete_me` en `backend/app/routers/auth.py` (`DELETE /auth/me`): primero `salir_del_plan`
  (si era titular de una familia, esta se disuelve y todos vuelven a Gratis) y luego borra en orden de llaves
  foráneas aportes, metas, retos, logros, puntos, check-ins, mensajes del coach, límites, `ai_usage`, gastos,
  ingresos, gastos fijos, presupuestos y categorías propias, y al final el usuario, todo en un solo commit.
  Los tokens emitidos dejan de servir al instante porque `get_current_user` y `refresh` devuelven 401 si el
  usuario ya no existe.
- **Riesgo aceptado.** La lista de tablas es manual: una tabla nueva con `user_id` que no se agregue aquí
  rompe el borrado (falla por llave foránea) o deja datos. Los backups de Neon y lo que ya recibió Groq no se
  borran.

### A9. Acceso a datos de otra persona (IDOR)

- **Control.** Todos los routers filtran por el usuario autenticado (`current_user` de `get_current_user`):
  por ejemplo `Expense.user_id == user_id` y `Budget.owner_id`; las categorías comparten las por defecto
  (`owner_id` nulo) y las propias. Los totales del reporte semanal y del coach se calculan solo con el
  `user_id` de la sesión (`build_weekly_summary`, `contexto_financiero`).

## Riesgos abiertos (hallazgos de otros tickets)

Verificados en el código de `origin/feature/plan-final` y, para R3, en `backend/tests/test_adversarial.py` de
`origin/feature/PS-102-adversarial`.

### R1. El reporte semanal mete nombres de categoría sin sanear y fuera de `<datos_usuario>`

`summary_to_text` (`backend/app/services/weekly_report.py`) escribe `f"  - {c.categoria}: ..."` con el nombre
crudo de la categoría, y `build_weekly_report_prompt` (`backend/app/services/prompts.py`) lo interpola dentro
de `WEEKLY_REPORT_SYSTEM_PROMPT`, que se manda como mensaje `system` (`generate_weekly_recommendations`). Es
el único prompt que no pasa los nombres por `sanear_dato` ni los encierra en `<datos_usuario>`, y el
prompt no advierte que el resumen son datos. Una persona puede crear una categoría propia cuyo nombre sea una
instrucción (con saltos de línea y de cualquier largo, ver R2) y quedará escrita en el prompt de sistema. **Mitigación actual:** la salida pasa por `rompe_guardrails`, `_MENCIONA_INVERSION` e
`inventa_cifras` en `weekly_report` (`backend/app/routers/reports.py`) y, si falla, se muestra
`resumen_de_respaldo`. **Arreglo:** sanear con `sanear_dato` y mover el resumen a `<datos_usuario>`, como en
el coach.

### R2. Categorías y `/expenses/parse` sin tope de largo

- `CategoryCreate.nombre` y `CategoryUpdate.nombre` (`backend/app/schemas/category.py`) son `str` sin
  `max_length`, y la columna `Category.nombre` tampoco lo tiene. En los prompts del parseo y del coach se
  recortan a 40 caracteres con `sanear_dato`, pero no en el reporte semanal (R1) ni en la respuesta de la API.
- `ExpenseParseRequest.texto` (`backend/app/schemas/expense.py`), usado por `POST /expenses/parse` y
  `POST /expenses/from-text`, es `str` sin `max_length`: el texto entero va a Groq dentro de `como_datos`. A
  diferencia de `ReceiptParseRequest.texto_ocr` (máx. 6000) y del chat (máx. 1000), una sola solicitud puede
  costar tantos tokens como admita el modelo, lo que debilita el control de A6 (el cupo cuenta solicitudes,
  no tokens).
- **Arreglo:** `Field(min_length=1, max_length=...)` en ambos esquemas (y una migración si se acota la columna).

### R3. `filtra_salida` no detecta cambios de rol ni fugas parafraseadas

`filtra_salida` (`backend/app/services/ia_seguridad.py`) solo busca fragmentos **literales** de las reglas
(`_FRAGMENTOS_PROMPT`), URLs, código/HTML y largo. La suite `backend/tests/test_adversarial.py` deja
documentados con `xfail(strict=True)` **14 casos de contención** que hoy pasan esa capa: 11 respuestas que
declaran otro rol o "sin reglas" (`ROL_NO_DETECTADO`: modo desarrollador, DAN, "asistente sin restricciones"…),
1 fuga parafraseada del prompt (`FUGA_PARAFRASEADA`) y 2 temas ajenos que el modelo comprometido marca
`en_alcance=true` (`TEMA_AJENO_NO_DETECTADO`), donde el rechazo depende solo del contrato. La misma suite marca
otros 7 casos en que `marca_inyeccion` no etiqueta la entrada (leetspeak, base64 corto o partido en líneas,
sinónimos, falsificar el contrato JSON); como esa capa solo registra, no cambian lo que ve la persona.
Detalle y propuestas en [docs/informe-adversarial.md](informe-adversarial.md).

## Resumen

| # | Amenaza | Control principal | Estado |
|---|---|---|---|
| A1 | Robo/falsificación de sesión | `security._decode_token`, `deps.get_current_user` | Controlado; sin revocación (aceptado) |
| A2 | Fuerza bruta de login | `rate_limit.revisar_login` + bcrypt | Controlado; IP falsificable y contadores en memoria (aceptado) |
| A3 | Origen web no autorizado | `CORSMiddleware` en `main.py`, Bearer sin cookies | Controlado |
| A4 | Fuga de secretos | `config.Settings`, `.gitignore`, `render.yaml` | Controlado; sin rotación (aceptado). Hay credenciales por rotar ([pendientes.md](pendientes.md)) |
| A4b | Sesión en el navegador (web) | `flutter_secure_storage` web, HTTPS, token por cabecera | Parcial; sin CSP (aceptado) |
| A4c | Contraseñas débiles, canjes por fuerza bruta, montos y fechas inválidos | `NuevaContrasena`, `revisar_canje`, `schemas/common.py`, `validaciones.py` | Controlado |
| A5 | Prompt injection | Capas de `ia_seguridad.py` + contratos | Parcial; R1 y R3 abiertos |
| A6 | Abuso económico de la IA | `rate_limit.limite_ia` + `ia_uso.cupo_agotado` | Controlado; R2 abierto, carrera del cupo (aceptado) |
| A7 | Datos que salen a Groq | Agregados, nombres saneados, `ai_usage` sin texto | Controlado; texto libre y retención de Groq (aceptado) |
| A8 | Borrado incompleto | `auth.delete_me` | Controlado; lista manual de tablas, backups (aceptado) |
| A9 | Acceso a datos ajenos | Filtro por `current_user` en cada router | Controlado |
