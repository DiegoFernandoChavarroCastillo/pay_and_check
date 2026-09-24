# Plan de construcción — Backend, app de gestión de gastos (MVP)

## Cómo usar este documento

Este documento es la guía de construcción del backend, fase por fase. Antes de escribir código:

1. Lee el documento completo una vez.
2. Trabaja **una fase a la vez**, en orden. No adelantes features de fases posteriores.
3. Al terminar cada fase, verifica el "Criterio de aceptación" antes de pasar a la siguiente.
4. Si algo no está definido explícitamente aquí, pregunta antes de asumir — no inventes campos, endpoints ni lógica de negocio fuera de lo descrito.
5. Marca los checkboxes `- [ ]` a medida que completes tareas, para llevar el progreso visible.

## Contexto del producto

Es una app para que un estudiante universitario (y luego, opcionalmente, una familia) controle sus gastos frente a un presupuesto fijo por periodo (ej. un semestre). El usuario registra gastos en lenguaje natural ("me compré un helado de $5000") por texto o voz, y el sistema:

- Parsea ese texto con IA (Groq) para extraer monto, categoría, descripción y fecha.
- Calcula en tiempo real cuánto dinero queda disponible por día/semana para no quedarse sin presupuesto antes de que termine el periodo.
- Genera reportes semanales con estadísticas por categoría y recomendaciones de IA.

Este documento cubre **solo el backend** del MVP. El frontend se planea en un documento aparte.

## Decisiones técnicas (ya tomadas, no reabrir)

- **Lenguaje/framework**: Python 3.12 + FastAPI
- **ORM**: SQLModel (sobre SQLAlchemy 2.0) + Alembic para migraciones
- **Base de datos**: PostgreSQL
- **Gestor de dependencias**: `uv`
- **Autenticación**: dos métodos, ambos terminan en el mismo JWT propio de la app:
  - Email/contraseña: JWT (librería `python-jose`) + hashing con `passlib[bcrypt]`
  - Google: "Sign in with Google" vía Google Identity Services en el frontend, verificación del ID token en el backend con `google-auth`
- **IA**: SDK oficial `groq`, modelo `llama-3.1-8b-instant`
- **Contenedores**: Docker + docker-compose para desarrollo local
- **Testing**: `pytest` + `httpx` (TestClient de FastAPI)
- **CI**: GitHub Actions (lint + tests en cada push)

## Estructura de carpetas objetivo

```
backend/
├── app/
│   ├── main.py
│   ├── core/
│   │   ├── config.py          # settings desde variables de entorno
│   │   └── security.py        # hashing, JWT
│   ├── db/
│   │   ├── session.py         # engine y sesión de SQLModel
│   │   └── seed.py            # categorías por defecto
│   ├── models/                # modelos SQLModel (tablas)
│   │   ├── user.py
│   │   ├── budget.py
│   │   ├── category.py
│   │   └── expense.py
│   ├── schemas/                # Pydantic request/response
│   ├── routers/                 # endpoints agrupados por recurso
│   │   ├── auth.py
│   │   ├── budgets.py
│   │   ├── categories.py
│   │   ├── expenses.py
│   │   └── reports.py
│   ├── services/                 # lógica de negocio
│   │   ├── budget_calculator.py
│   │   ├── groq_client.py
│   │   ├── google_auth.py
│   │   └── prompts.py
│   └── deps.py                  # dependencias compartidas (get_current_user, get_session)
├── alembic/
├── tests/
├── .env.example
├── Dockerfile
├── docker-compose.yml
└── pyproject.toml
```

---

## Fase 0 — Arquitectura y setup de entorno

**Objetivo**: dejar el entorno de desarrollo listo antes de escribir lógica de negocio.

- [x] Crear repositorio y estructura de carpetas descrita arriba (vacía, solo `__init__.py` donde aplique).
- [x] Inicializar proyecto con `uv` y `pyproject.toml`, agregar dependencias base: `fastapi`, `uvicorn`, `sqlmodel`, `alembic`, `psycopg2-binary`, `python-jose`, `passlib[bcrypt]`, `groq`, `google-auth`, `python-dotenv`.
- [x] Crear `.env.example` con las variables necesarias: `DATABASE_URL`, `JWT_SECRET`, `JWT_ALGORITHM`, `GROQ_API_KEY`, `ACCESS_TOKEN_EXPIRE_MINUTES`, `GOOGLE_CLIENT_ID`.
- [ ] Crear el proyecto en [Google Cloud Console](https://console.cloud.google.com/) (pantalla de consentimiento OAuth + credencial "ID de cliente OAuth" de tipo aplicación web), y guardar el Client ID en `GOOGLE_CLIENT_ID`. Este mismo Client ID lo usará después el frontend. **Pendiente: requiere login manual del usuario en la consola de Google, ver instrucciones que dio el agente.**
- [x] Crear `app/core/config.py` que lea esas variables (usar `pydantic-settings`).
- [x] Crear `docker-compose.yml` con dos servicios: `api` (build local) y `db` (imagen `postgres:16`), con volumen persistente para la DB. Sintaxis validada con `docker compose config`; `docker-compose up` real queda pendiente de que el usuario habilite permisos de Docker (ver nota del agente).

**Criterio de aceptación**: `docker-compose up` levanta ambos servicios sin errores y la API responde algo en `http://localhost:8000` (aunque sea un 404 por defecto de FastAPI).
✅ **Confirmado tras el reinicio** (el bloqueo del módulo `veth` del kernel se resolvió solo). `docker compose up --build` levanta `api` + `db` y `/health` responde `200` real contra Postgres en Docker.

**Bug real encontrado y arreglado**: `docker-compose.yml` montaba todo `backend/` dentro del contenedor (`.:/app`), y como el contenedor corre `uv sync`/`uv run` como root, sobrescribió el `.venv` del host con archivos **root-owned** (ni siquiera se podían borrar sin `sudo`). Se arregló agregando un volumen anónimo `/app/.venv` en el servicio `api`, que le da al contenedor su propio `.venv` sin tocar el del host — patrón estándar para Python/Node en docker-compose con bind mounts.

---

## Fase 1 — Scaffolding de la aplicación FastAPI

**Objetivo**: tener el esqueleto de la app corriendo, con conexión a base de datos y manejo de errores, sin features de negocio todavía.

- [x] Crear `app/main.py` con la instancia de FastAPI, CORS habilitado para el origen del frontend, y registro de routers (vacíos por ahora). **Nota:** la Fase 0 no había definido ninguna variable de entorno para el origen del frontend; se agregó `CORS_ORIGINS` a `config.py`/`.env.example` en esta fase (ver pregunta al usuario).
- [x] Crear `app/db/session.py` con el engine de SQLModel y una función `get_session()` para inyectar como dependencia.
- [x] Configurar Alembic (`alembic init`), apuntando su `env.py` a los modelos de SQLModel y a `DATABASE_URL` desde `config.py`.
- [x] Agregar manejo global de excepciones (handler para errores de validación y errores no controlados, respuestas JSON consistentes).
- [x] Crear endpoint `GET /health` que verifique conexión a la base de datos y responda `{"status": "ok"}`.

**Criterio de aceptación**: la app arranca con `uvicorn app.main:app --reload` ✅ verificado. `/health` y `alembic revision --autogenerate -m "init"` necesitan Postgres corriendo — **pendiente de validar**: `docker-compose up` sigue bloqueado en este entorno por un problema de red a nivel de kernel (módulo `veth` no cargado), ver nota del agente en el chat.

---

## Fase 2 — Modelos de datos y migraciones

**Objetivo**: definir el esquema de datos completo del MVP.

- [x] Modelo `User`: id, email (único), hashed_password (nullable — un usuario que solo entra con Google no tiene contraseña propia), google_id (nullable, único — el `sub` que devuelve Google), nombre, created_at. Un usuario debe tener al menos `hashed_password` o `google_id`, nunca ninguno de los dos (`CheckConstraint` a nivel de DB).
- [x] Modelo `Budget`: id, owner_id (FK a User), monto_total, fecha_inicio, fecha_fin, created_at. (Un usuario puede tener varios presupuestos históricos; el "activo" es el que contiene la fecha de hoy.)
- [x] Modelo `Category`: id, nombre, owner_id (nullable — si es null, es una categoría por defecto del sistema; si tiene valor, es personalizada de ese usuario).
- [x] Modelo `Expense`: id, user_id (FK), budget_id (FK), category_id (FK), monto, descripcion, texto_original (nullable, guarda el texto que el usuario escribió si vino de IA), fecha, created_at.
- [x] Dejar en el modelo `User` un campo `group_id` (FK nullable a una tabla `Group` mínima con solo `id` y `nombre`, en `app/models/group.py`) — no se usa en el MVP, pero se deja preparado para el modo familiar sin migraciones destructivas después.
- [x] Generar migración con Alembic y aplicarla contra la base local. ✅ Generada (`alembic/versions/6a4686a52aeb_init.py`) y aplicada contra **Neon** (Postgres real) y contra la base de Docker local — ambas sincronizadas.
- [x] Crear `app/db/seed.py` con un script que inserte las categorías por defecto: comida, transporte, entretenimiento, salud, servicios, otros. Idempotencia verificada dos veces contra Postgres real (Neon).

**Criterio de aceptación**: las tablas existen en Postgres (verificar con `psql` o un cliente), y correr el seed puebla las categorías sin duplicarlas si se ejecuta más de una vez.
✅ **Validado contra Postgres real**: las 5 tablas existen (`groups`, `users`, `budgets`, `categories`, `expenses`), y el seed corrido dos veces deja exactamente 6 categorías sin duplicar. También confirmé que el `CheckConstraint` de `users` lo aplica Postgres de verdad (no solo SQLite).

**Bug real encontrado y arreglado** (Alembic + SQLModel, problema conocido): la migración autogenerada usa `sqlmodel.sql.sqltypes.AutoString()` pero el archivo no importaba `sqlmodel` — fallaba con `NameError` al aplicarla. Se arregló agregando `import sqlmodel` a la migración generada y a `alembic/script.py.mako` (para que las migraciones futuras lo incluyan solas).

---

## Fase 3 — Autenticación

**Objetivo**: que un usuario pueda registrarse/entrar por email+contraseña o por Google, y acceder a endpoints protegidos. Los dos métodos son independientes en la entrada, pero convergen en el mismo JWT propio de la app — el resto del backend (Fases 4 en adelante) nunca necesita saber por cuál método entró el usuario.

**Contexto del flujo de Google**: el frontend usa la librería de Google Identity Services para mostrar el botón "Iniciar sesión con Google" y obtener un `id_token` firmado por Google. Ese token se manda tal cual al backend; el backend nunca ve ni maneja la contraseña de la cuenta de Google del usuario, solo verifica la firma del token.

**Sub-pasos — email/contraseña**
- [x] `POST /auth/register`: recibe email, password, nombre. Hashea el password con bcrypt antes de guardar. Devuelve el usuario creado (sin el hash). Si el email ya existe con `google_id` pero sin password, permitir "agregar" una contraseña a esa cuenta en vez de fallar.
- [x] `POST /auth/login`: recibe email y password, valida contra el hash, devuelve un JWT con expiración configurable. Si el usuario no tiene `hashed_password` (solo se registró con Google), devolver un 400 con mensaje claro ("esta cuenta usa Google para iniciar sesión").
- [x] `app/core/security.py`: funciones `hash_password`, `verify_password`, `create_access_token`, `decode_access_token`.

**Sub-pasos — Google**
- [x] `app/services/google_auth.py`: función `verify_google_token(id_token: str)` que usa `google.oauth2.id_token.verify_oauth2_token` contra `GOOGLE_CLIENT_ID`, y devuelve `{google_id, email, nombre}` o lanza error si el token es inválido/expirado.
- [x] `POST /auth/google`: recibe `{id_token: string}` del frontend. Verifica el token con la función anterior. Si ya existe un usuario con ese `google_id`, lo loguea. Si existe un usuario con ese email pero sin `google_id` (se había registrado por password), le asocia el `google_id` a esa misma cuenta. Si no existe ningún usuario con ese email, lo crea con `hashed_password = null`. En todos los casos, devuelve el mismo JWT propio de la app que devuelve `/auth/login`.

**Sub-pasos — comunes**
- [x] `app/deps.py`: dependencia `get_current_user` que decodifica el JWT del header `Authorization: Bearer` y devuelve el usuario o lanza 401 (funciona igual sin importar el método de login original).
- [x] Endpoint de prueba `GET /auth/me` protegido, que devuelve el usuario autenticado.

**Criterio de aceptación**: (1) registrar y loguear por email/contraseña funciona como antes; (2) enviar un `id_token` válido de Google a `/auth/google` crea o loguea al usuario correctamente y devuelve un JWT usable en `/auth/me`; (3) un mismo email puede terminar asociado a ambos métodos sin duplicar el usuario; (4) un token inválido o ausente en cualquier endpoint protegido devuelve 401.
✅ **Los 4 casos se validaron** con un smoke test (`TestClient` + SQLite en memoria + `verify_google_token` mockeado, sin llamar a la API real de Google) y además (1), (3) y (4) se repitieron con peticiones HTTP reales contra Postgres (Docker). Falta solo la prueba manual con un `id_token` real de Google desde el frontend (no aplica hasta que exista el frontend con el botón de Google).

**Nota técnica importante**: `passlib==1.7.4` (última versión, sin mantenimiento activo) es incompatible con `bcrypt>=4.1` — lanza `ValueError: password cannot be longer than 72 bytes` incluso con passwords cortos, por un bug de detección de versión en passlib. Fijé `bcrypt==4.0.1` explícitamente en `pyproject.toml` como workaround. Si en el futuro `uv sync`/`uv add` actualiza `bcrypt` a 4.1+, este error reaparece — no subir esa versión sin cambiar de librería de hashing.

---

## Fase 4 — Presupuesto y cálculo de disponibilidad

**Objetivo**: exponer el dato central de la app — cuánto dinero queda disponible por día/semana.

- [x] `POST /budgets`: crea un presupuesto para el usuario autenticado (monto_total, fecha_inicio, fecha_fin).
- [x] `GET /budgets/active`: devuelve el presupuesto cuyo rango de fechas incluye hoy, o 404 si no hay ninguno.
- [x] `PATCH /budgets/{id}`: permite ajustar monto_total o fechas de un presupuesto existente.
- [x] `app/services/budget_calculator.py`: función que, dado un presupuesto y la suma de gastos ya registrados en su rango, calcule:
  - `gastado_total`
  - `disponible_total` (monto_total - gastado_total)
  - `dias_restantes` y `semanas_restantes` del periodo
  - `disponible_por_dia` y `disponible_por_semana` (disponible_total / restante)
- [x] `GET /budgets/active/summary`: expone los valores anteriores en un solo response, pensado para el dashboard del frontend.

**Criterio de aceptación**: con un presupuesto de prueba y algunos gastos manuales insertados directo en la DB, el endpoint de resumen devuelve los cálculos correctos (verificar a mano con una fecha y montos de prueba).
✅ Validado con smoke test (SQLite): 4 casos de `budget_calculator` calculados y verificados a mano. ✅ **Repetido contra Postgres real** (Docker): presupuesto creado vía API, gastos insertados directo en la DB, `/budgets/active/summary` devolvió `gastado_total=50000.00`, `disponible_total=450000.00`, `dias_restantes=7`, `disponible_por_dia=64285.71` — verificado a mano y coincide exacto.

**Bug real encontrado y arreglado** (en el manejo global de excepciones de la Fase 1, no en esta fase): cuando un `@model_validator` de Pydantic lanza `ValueError` (usado aquí para validar `fecha_fin > fecha_inicio`), `RequestValidationError.errors()` incluye el objeto `ValueError` crudo en `ctx["error"]`, que no es serializable a JSON directo — rompía con `500` en vez de devolver el `422` esperado. Se arregló envolviendo `exc.errors()` en `fastapi.encoders.jsonable_encoder` en `app/main.py`.

---

## Fase 5 — Categorías

**Objetivo**: exponer las categorías disponibles para clasificar gastos.

- [x] `GET /categories`: devuelve las categorías por defecto (owner_id nulo) más las personalizadas del usuario autenticado.
- [x] `POST /categories`: crea una categoría personalizada asociada al usuario autenticado.

**Criterio de aceptación**: un usuario nuevo ve las categorías por defecto sin haber creado ninguna; puede agregar una propia y esta aparece solo para él.
✅ Validado con smoke test (SQLite, dos usuarios) y ✅ **repetido contra Postgres real** (Docker): usuario nuevo ve las 6 categorías del seed sin haber creado ninguna.

---

## Fase 6 — Gastos: CRUD manual

**Objetivo**: poder registrar, consultar, editar y borrar gastos sin depender todavía de la IA (esto valida el modelo de datos y las relaciones antes de meter la complejidad de Groq).

- [x] `POST /expenses`: crea un gasto manual (monto, category_id, descripcion, fecha). Se asocia automáticamente al presupuesto activo del usuario.
- [x] `GET /expenses`: lista los gastos del usuario, con filtros opcionales por query params: `category_id`, `fecha_desde`, `fecha_hasta`.
- [x] `PATCH /expenses/{id}`: edita un gasto existente (solo si pertenece al usuario autenticado).
- [x] `DELETE /expenses/{id}`: elimina un gasto (solo si pertenece al usuario autenticado).
- [x] Validar en cada operación que el gasto quede dentro del rango de fechas de algún presupuesto del usuario; si no, devolver un error claro.

**Nota de interpretación** (el plan no lo precisaba del todo): "se asocia automáticamente al presupuesto activo" lo implementé como *el presupuesto del usuario cuyo rango contiene la `fecha` del gasto* (no necesariamente el de HOY) — así se pueden registrar gastos atrasados dentro de un presupuesto histórico, y esto es consistente con la validación de "algún presupuesto" del bullet siguiente. Si la intención real era exclusivamente el presupuesto de hoy, dime y lo ajusto. También agregué una validación no listada explícitamente: la categoría debe ser por defecto o del propio usuario (igual que en `GET /categories`), para no permitir usar la categoría privada de otro usuario.

**Criterio de aceptación**: crear, listar con filtros, editar y borrar gastos funciona vía API, y el `GET /budgets/active/summary` de la Fase 4 refleja los cambios inmediatamente después de cada operación.
✅ **Validado con HTTP real contra Postgres** (Docker): crear vía API subió `gastado_total` de 50000→60000 en el summary; `PATCH` del monto lo reflejó a 65000 al instante; `DELETE` lo devolvió a 50000. También probé los rechazos: fecha fuera de cualquier presupuesto → 400 claro, categoría inexistente → 404, y que un segundo usuario no puede ver/editar/borrar el gasto del primero (404, sin filtrar existencia).

---

## Fase 7 — Integración con IA (Groq): parseo de lenguaje natural

**Objetivo**: permitir registrar un gasto escribiendo una frase libre, en vez de llenar un formulario.

- [x] `app/services/groq_client.py`: wrapper delgado sobre el SDK `groq`, con la API key leída desde `config.py`.
- [x] `app/services/prompts.py`: prompt de sistema que instruye al modelo a responder **únicamente** un JSON con las llaves `monto`, `categoria`, `descripcion`, `fecha` (fecha por defecto: hoy, si el texto no la menciona). Incluir en el prompt la lista de categorías válidas del usuario para que el modelo elija entre esas.
- [x] `POST /expenses/parse`: recibe `{texto: string}`, llama a Groq, devuelve el JSON estructurado **sin guardar el gasto** — pensado para que el frontend muestre una confirmación antes de guardar.
- [x] `POST /expenses/from-text`: mismo parseo, pero guarda el gasto directamente en un solo paso (usar cuando el frontend quiera flujo rápido sin confirmación).
- [x] Manejo de errores: si el modelo no devuelve un JSON válido o no logra extraer un monto, devolver un 422 con un mensaje claro — nunca inventar un monto o guardar datos incompletos. También se agregó un 502 claro si Groq falla por red/API (no estaba pedido explícitamente, pero evita un 500 genérico en ese caso).

**⚠️ Decisión técnica invalidada — señalado, no corregido en silencio**: el modelo `llama-3.1-8b-instant` fijado en el plan **ya no existe en Groq** (`404 model_not_found` al probarlo). Consulté los modelos activos actuales de la cuenta y no hay ningún `llama-3.1-*`. Cambié a **`openai/gpt-oss-20b`** (el modelo de propósito general más chico/barato disponible hoy), probado a mano y funciona bien con el prompt en español. Si prefieres otro modelo de los disponibles (`openai/gpt-oss-120b`, `qwen/qwen3.8-27b`, `allam-2-7b`), es un cambio de una sola constante en `app/services/groq_client.py`.

**Criterio de aceptación**: enviar "me compré un helado de $5000" a `/expenses/parse` devuelve `{"monto": 5000, "categoria": "comida", ...}` de forma consistente en varias pruebas; un texto sin monto claro devuelve un error controlado, no un 500.
✅ **Validado con la API real de Groq** (no mockeada): 3 llamadas consecutivas devolvieron el mismo resultado consistente; un texto sin monto ("hoy me sentí feliz") devolvió `422` limpio. También probé `/expenses/from-text` end-to-end: guardó el gasto y `/budgets/active/summary` subió de 50000 a 62000 al instante.

---

## Fase 8 — Reportes semanales y recomendaciones de IA

**Objetivo**: generar el resumen semanal con recomendaciones personalizadas.

- [x] Servicio que agregue, para un rango de fechas (semana), el gasto total por categoría y la comparación contra el ritmo esperado del presupuesto (`app/services/weekly_report.py`).
- [x] Prompt específico en `prompts.py` que reciba ese resumen agregado (no las transacciones individuales, para ahorrar tokens) y devuelva 2-3 recomendaciones en texto natural.
- [x] `GET /reports/weekly`: devuelve el resumen agregado (para las gráficas del frontend) más el texto de recomendaciones de la IA.

**Nota de interpretación**: el plan no precisaba qué es "el ritmo esperado del presupuesto" ni qué semana usar. Implementé: (a) la semana calendario lunes-domingo que contiene hoy, y (b) el ritmo esperado como `monto_total / semanas_totales_del_periodo` (un promedio fijo parejo de referencia) — deliberadamente distinto del `disponible_por_semana` dinámico de la Fase 4 (que mira hacia adelante desde hoy y cambia con cada gasto). Si la intención era otra métrica, es un cambio acotado a `weekly_report.py`.

**Criterio de aceptación**: con datos de prueba de una semana, el endpoint devuelve un resumen numérico correcto y una recomendación coherente con esos números (por ejemplo, si "comida" es la categoría más alta, la recomendación debería mencionarla).
✅ **Validado con Groq real**: con gastos de prueba (comida=110000, transporte=32000, total=142000 en la semana), el resumen calculó `ritmo_esperado_semanal=116666.67` y `diferencia_vs_ritmo=25333.33` — verificado a mano (monto_total 500000 / 4.2857 semanas del periodo) — y la recomendación de la IA mencionó explícitamente "comida" como categoría dominante y sugirió acciones concretas. Ajusté el prompt para que no use símbolos de moneda (el modelo puso "€" la primera vez).

---

## Fase 9 — Testing

**Objetivo**: tener una red de seguridad antes de tocar el frontend.

- [x] Tests unitarios de `budget_calculator.py` (casos borde: presupuesto recién iniciado, presupuesto vencido, sin gastos aún, y agregué "aún no empieza").
- [x] Tests de integración de los endpoints de auth, budgets, categories y expenses usando SQLite en memoria (`StaticPool`, vía `tests/conftest.py`).
- [x] Mockeado `parse_expense_text` y `generate_weekly_recommendations` (los puntos de entrada a Groq) en los tests de `/expenses/parse`, `/expenses/from-text` y `/reports/weekly` — nunca llaman a la API real.

**Criterio de aceptación**: `pytest` corre en verde localmente sin necesitar `GROQ_API_KEY` real ni conexión a internet.
✅ **32/32 tests pasan**, incluso quitando el `.env` por completo y con el entorno de shell limpio (`env -i`) — probado explícitamente para asegurar que ningún test dependa por accidente de un `.env` local o de internet. `tests/conftest.py` fija variables dummy (`DATABASE_URL=sqlite:///:memory:`, etc.) antes de importar la app, así que la suite es hermética para CI.

---

## Fase 10 — Dockerización y CI

**Objetivo**: dejar el backend listo para desplegar.

- [x] `Dockerfile` multi-stage para la API (build de dependencias + imagen final liviana). La imagen final no lleva `uv` ni herramientas de build, corre como usuario no-root (`appuser`), y solo copia el venv ya resuelto + el código.
- [x] Confirmar que `docker-compose.yml` sirve tanto para desarrollo como de base para producción (variables de entorno externalizadas vía `.env`/`env_file`). En dev, `docker-compose.yml` sigue usando bind mount + `--reload`; el mismo `Dockerfile` sin ese override es la imagen de producción.
- [x] Workflow de GitHub Actions (`.github/workflows/backend-ci.yml`): en cada push/PR que toque `backend/`, corre `ruff check` y `pytest`.
- [x] Documentado en `README.md` (raíz del repo) las variables de entorno y los pasos para desplegar en Railway/Render/Fly.io (o cualquier plataforma que despliegue desde `Dockerfile`).

**Bug real encontrado y arreglado**: al reescribir el `Dockerfile` a multi-stage, la imagen final dejó de tener `uv` instalado (solo el venv ya armado), pero `docker-compose.yml` seguía arrancando con `uv run uvicorn ...` — se hubiera roto en el próximo `--build`. Se corrigió a `uvicorn ...` directo (el venv ya está en `PATH`).

**Extra no pedido explícitamente**: agregué `ruff` como dependencia de desarrollo con una selección de reglas curada (`E, F, I, UP, B`, ignorando `B008` porque `Depends(...)` como default de FastAPI es idiomático, no un bug) — el plan menciona `ruff` en la Fase 10 pero no especificaba qué reglas.

**Criterio de aceptación**: la imagen Docker se construye sin errores y el contenedor levantado localmente se comporta igual que en desarrollo con `uvicorn --reload`.
✅ **Validado**: `docker build` sin errores; corrí la imagen de producción standalone (sin compose, sin bind mount) contra la misma base de datos y confirmé `/health` 200, `/docs` 200, login real funcionando, y el proceso corriendo como `appuser` (no root). También reconstruí `docker-compose up --build` completo con el Dockerfile nuevo: el `.venv` del host quedó intacto y los datos persistentes (usuario de prueba) sobrevivieron. `ruff check .` y `pytest` pasan limpio, simulando exactamente los pasos del workflow de CI localmente (incluso con `.env` removido y entorno de shell limpio).

---

## Fase 11 — Ingresos, categorías fijas/opcionales, gastos recurrentes y alerta de riesgo

**Origen**: al validar el caso de uso real del usuario (presupuesto de semestre, gastos semanales fijos,
gastos extemporáneos, dinero que le mandan los papás, y querer una advertencia si el ritmo de gasto no le va
a alcanzar) se encontraron 4 huecos reales no cubiertos por las Fases 0-10. Ninguno estaba mencionado en el
plan original — se diseñan y documentan aquí antes de implementar.

### 11.1 — Ingresos (dinero extra que amplía el presupuesto)

- [x] Modelo `Income`: id, user_id (FK), budget_id (FK — se asocia automáticamente igual que un `Expense`, por
  la fecha), monto, descripcion, fecha, created_at.
- [x] `POST /incomes`, `GET /incomes` (filtros `fecha_desde`/`fecha_hasta`), `PATCH /incomes/{id}`,
  `DELETE /incomes/{id}` — mismo patrón de aislamiento por usuario que `Expense`.
- [x] `budget_calculator.calculate_budget_summary` pasa a recibir también `ingresos_total`:
  `disponible_total = monto_total + ingresos_total - gastado_total`.
- [x] `GET /budgets/active/summary` expone `ingresos_total` además de `gastado_total`.

**Criterio de aceptación**: registrar un ingreso de $50.000 sube `disponible_total` del summary en esa misma
cantidad, sin tocar `monto_total` del presupuesto (que sigue siendo el valor original fijado).
✅ **Validado contra Postgres real**: registrar un ingreso de 50.000 subió `disponible_total` a 2.050.000
manteniendo `monto_total` en 2.000.000. También con tests de pytest (`test_incomes.py`).

### 11.2 — Categorías fijas vs. opcionales, con límite propio

- [x] `Category` gana dos campos: `tipo` (`"fijo"` | `"opcional"`, default `"opcional"`) y `limite: Decimal | None`
  (tope de gasto de esa categoría durante el presupuesto activo; `None` = sin tope).
- [x] `POST/PATCH` de categorías aceptan estos dos campos. Se agregó `PATCH /categories/{id}` (no existía desde
  la Fase 5) — restringido a categorías propias: las por defecto (`owner_id` nulo) son **un solo registro
  compartido por todos los usuarios**, editarlas cambiaría el tipo/límite para todo el mundo.
- [x] Nuevo cálculo `desglose_por_categoria` en `GET /budgets/active/summary`: por cada categoría con gasto en
  el presupuesto activo, `{categoria, tipo, gastado, limite, excedido}`.

**Nota de interpretación**: el usuario habló de "un presupuesto de gastos opcionales" como si fuera un solo
bolsillo agregado. Lo generalicé a un límite *por categoría* (cualquier categoría puede tener límite, no solo
un bucket fijo llamado "opcionales") porque es estrictamente más flexible y cubre el mismo caso (poner límite
solo a "entretenimiento" y "comida fuera de casa" logra el mismo resultado). Si se prefiere un único bolsillo
agregado de "opcionales" en vez de límites por categoría, es un cambio de diseño, no solo de código.

**Criterio de aceptación**: marcar "entretenimiento" con `limite=50000` y gastar 60000 en ella durante el
presupuesto activo hace que `excedido=true` para esa categoría en el summary, sin afectar a las demás.
✅ **Validado contra Postgres real**: categoría "salidas" con `limite=30000`, gasto de 40000 →
`excedido=true`; categorías sin límite nunca marcan excedido. Confirmado también que `PATCH` sobre una
categoría por defecto da `404` (protección de dato compartido). Tests en `test_categories.py` y
`test_category_breakdown.py`.

### 11.3 — Gastos fijos recurrentes (semanales)

- [x] Modelo `RecurringExpense`: id, user_id (FK), category_id (FK), monto, descripcion, dia_semana
  (0=lunes..6=domingo — el día de la semana en que "cuenta" como gastado), fecha_inicio (desde cuándo generar;
  por defecto hoy, para no rellenar retroactivamente semanas antes de que el usuario lo creara), activo (bool),
  created_at.
- [x] `Expense` gana `recurring_expense_id: int | None` (FK nullable) para rastrear qué gastos vinieron de una
  recurrencia y no duplicarlos.
- [x] `POST/GET/PATCH/DELETE /recurring-expenses`.
- [x] Servicio `sync_recurring_expenses`: por cada `RecurringExpense` activo del usuario, genera los `Expense`
  de las semanas ya transcurridas (entre `fecha_inicio` y hoy) que todavía no existan, asociándolos al
  presupuesto de esa fecha (si no hay presupuesto para esa semana, se omite esa semana). Se ejecuta
  automáticamente al pedir `GET /budgets/active/summary` y `GET /expenses` — no hace falta un cron ni un
  worker aparte, es "al vuelo" cuando el usuario mira su información.

**Nota de alcance**: no se monta un scheduler (Celery/cron) — habría sido una pieza de infraestructura nueva
no contemplada en el plan original. La generación "al vuelo" logra el mismo resultado percibido por el
usuario sin esa complejidad.

**Criterio de aceptación**: crear un gasto fijo semanal, avanzar el reloj del sistema una semana (o simular
`today` en un test) y pedir `GET /expenses` genera automáticamente el gasto de esa semana sin que el usuario
tenga que registrarlo a mano; pedirlo dos veces seguidas no lo duplica.
✅ **Validado contra Postgres real**: gasto fijo semanal creado con `fecha_inicio` de 20 días atrás generó
automáticamente las 4 ocurrencias correspondientes al pedir `GET /expenses`; repetir la llamada no duplicó
nada. Tests con fechas controladas (no dependientes del reloj real) en `test_recurring_expenses.py`.

### 11.4 — Alerta de riesgo / proyección de agotamiento

- [x] `budget_calculator.calculate_budget_summary` gana dos campos calculados: `en_riesgo: bool` y
  `fecha_proyectada_agotamiento: date | None`, a partir del ritmo real de gasto desde `fecha_inicio` hasta
  hoy (`gastado_total / días_transcurridos`), proyectado hacia adelante: si a ese ritmo el dinero se acaba
  antes de `fecha_fin`, `en_riesgo=true` y se informa la fecha proyectada.

**Criterio de aceptación**: con datos de prueba donde el ritmo real de gasto agotaría el presupuesto antes de
`fecha_fin`, el summary devuelve `en_riesgo=true` con una fecha de agotamiento anterior a `fecha_fin`;
con gasto lento, `en_riesgo=false`.
✅ **Validado contra Postgres real**: en un presupuesto de semestre (2026-09-03 a 2026-11-02) con un gasto
grande imprevisto, el summary devolvió `en_riesgo=true` con `fecha_proyectada_agotamiento=2026-09-27` — muy
antes del fin real — coincidiendo con el cálculo a mano. Sin ese gasto, `en_riesgo=false`. 5 tests unitarios
adicionales en `test_budget_calculator.py`.

**Resumen de la Fase 11**: 51/51 tests de pytest en verde (hermético, sin `.env`), `ruff check` limpio,
migración aplicada sin romper las categorías ya existentes (columna `tipo` con `server_default` en Postgres),
y las 4 features probadas de punta a punta simulando exactamente el caso de uso real descrito (presupuesto de
semestre + ingresos de los papás + gasto fijo semanal de transporte + límite en salidas + alerta de riesgo).

---

## Notas generales para el agente de código

- Cada endpoint debe tener su propio schema Pydantic de entrada y de salida — nunca devolver el modelo de SQLModel directamente en una respuesta.
- No se implementa el modo familiar/grupal en este plan; solo se deja la FK `group_id` preparada en el modelo `User`.
- El prompt de Groq vive aislado en `prompts.py` para poder iterarlo sin tocar la lógica de los routers o servicios.
- Si una fase revela que una decisión anterior estaba mal (por ejemplo, un campo faltante en un modelo), no lo corrijas silenciosamente: señálalo explícitamente antes de continuar.
