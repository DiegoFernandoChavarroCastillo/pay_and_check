# Pay&Check

App de finanzas personales para Android con un coach financiero. Registra gastos e ingresos con muy poca
fricción (texto, voz, foto de un recibo o SMS del banco), dice **cuánto se puede gastar hoy** y acompaña con un
coach que no regaña y con retos e insignias verificados con datos reales.

El repo es un monorepo con dos piezas:

- `backend/`: API REST en Python 3.12 + FastAPI + SQLModel/Alembic + PostgreSQL. IA con [Groq](https://console.groq.com/).
- `mobile/`: app Flutter, solo Android (detalle en [mobile/README.md](mobile/README.md)).

## Qué hace hoy

- **Presupuesto del periodo** y el número central de la app: el disponible por día.
- **Registro de movimientos**: manual, por frase escrita o dictada, por foto de un recibo (el texto se reconoce
  en el teléfono) y desde SMS del banco. La IA solo propone un borrador; la persona lo confirma.
- **Gastos fijos** semanales o mensuales: el día que vencen llega un aviso y quedan por pagar hasta que la
  persona confirma; ahí se descuentan.
- **Coach**: check-in emocional diario, consejos con una acción de un toque, chat, reacción al registrar y
  reporte semanal. Nunca regaña, no recomienda inversiones y no puede inventar cifras.
- **Progreso**: metas de ahorro con dinero realmente apartado, retos, insignias, puntos y niveles.
- **Reportes**: gasto por semana con gráficas, reporte semanal y resumen mensual.
- **Planes** Gratis, Premium, Familiar e Institucional (simulados, sin pasarela de pago) con cupo mensual de IA.

Dos reglas atraviesan el backend: **la IA redacta, no calcula** (toda cifra sale de código determinista y la
app funciona igual sin Groq) y **nada se auto-reporta ni se programa en el servidor** (retos, puntos y
vencimientos se recalculan al consultar). Ver [docs/ia.md](docs/ia.md) y [docs/decisiones/](docs/decisiones/).

## Correr el backend

Requisitos: Python 3.12, [`uv`](https://docs.astral.sh/uv/) y un PostgreSQL accesible (local, Docker o uno
gestionado como [Neon](https://neon.tech/)).

```bash
cd backend
uv sync                        # instala dependencias en .venv
cp .env.example .env           # y completar DATABASE_URL, JWT_SECRET y, si hay, GROQ_API_KEY
uv run alembic upgrade head    # crea o actualiza las tablas
uv run python -m app.db.seed_demo
uv run uvicorn app.main:app --reload
```

La API queda en `http://localhost:8000`, con documentación interactiva en `/docs`. `.env.example` explica cada
variable; las imprescindibles son `DATABASE_URL` y `JWT_SECRET`. Sin `GROQ_API_KEY` la app arranca igual: el
registro con IA responde 503 (la app lleva al formulario manual) y el coach usa sus textos de respaldo.

¿Sin Postgres instalado? `docker compose up --build` dentro de `backend/` levanta la API y una base de datos;
luego `docker compose exec api sh -c "alembic upgrade head && python -m app.db.seed_demo"`.

### Semilla de la demo y cuentas de prueba

`app.db.seed_demo` siembra las categorías por defecto, la organización **ECI** con el código de convenio
**`ECI-2026`** y un usuario por plan. Se puede correr las veces que haga falta: al usuario demo le reconstruye
los datos para que quede siempre a mitad de periodo. Al terminar imprime las cuentas:

| Correo | Contraseña | Plan |
|---|---|---|
| `demo@demo.payandcheck.com` | `Demo2026!` | Premium, con presupuesto a mitad de periodo, gastos fijos, movimientos, una meta y una alerta de riesgo |
| `gratis@demo.payandcheck.com` | `Demo2026!` | Gratis |
| `institucional@demo.payandcheck.com` | `Demo2026!` | Institucional (canjeó `ECI-2026`) |
| `familiar.titular@demo.payandcheck.com` | `Demo2026!` | Familiar, titular (el código familiar lo imprime la semilla) |
| `familiar.integrante@demo.payandcheck.com` | `Demo2026!` | Familiar, integrante |

Son cuentas de demostración: no usar esta semilla con datos reales de personas.

### Tests y lint

```bash
cd backend
uv run ruff check .
uv run pytest -q
```

La suite es hermética: usa SQLite en memoria y simula Groq, así que no necesita `.env`, Postgres ni internet.
Las migraciones de Alembic no se ejercitan ahí; se comprueban con `alembic upgrade head` contra un Postgres.

## Correr la app

Requisitos: Flutter (canal stable), JDK 17 y el Android SDK; versiones exactas en
[mobile/README.md](mobile/README.md). Con el backend corriendo:

```bash
cd mobile
flutter pub get

# Emulador de Android (10.0.2.2 es el localhost del PC visto desde el emulador; es el valor por defecto)
flutter run

# Teléfono físico por USB, con depuración USB activada
adb reverse tcp:8000 tcp:8000
flutter run --dart-define=API_BASE_URL=http://localhost:8000

# Contra el backend desplegado
flutter run --dart-define=API_BASE_URL=https://<tu-backend>
```

Para el login con Google se agrega `--dart-define=GOOGLE_SERVER_CLIENT_ID=<client id web>`; sin él, el botón
"Continuar con Google" no aparece. Pruebas: `flutter analyze` y `flutter test`.

## Instalar el APK

La app se distribuye como un APK firmado adjunto a un GitHub Release (ver
[ADR-007](docs/decisiones/007-distribucion-apk.md)). No está en Google Play, así que Android pide permitir la
instalación desde "orígenes desconocidos".

1. En el teléfono, abrir la página del último release
   (<https://github.com/DiegoFernandoChavarroCastillo/pay_and_check/releases/latest>, o escanear el QR de la
   presentación) y descargar `pay-and-check-<versión>.apk`.
2. Abrir el archivo descargado desde la notificación o desde la app *Archivos*.
3. Android avisa que esa app no tiene permiso para instalar apps desconocidas. Tocar **Configuración**,
   activar **Permitir de esta fuente** y volver.
   - En Android 7 o anterior el permiso es general: *Ajustes → Seguridad → Orígenes desconocidos*.
   - La ruta exacta cambia según la marca; también se encuentra en *Ajustes → Apps → Acceso especial →
     Instalar apps desconocidas*.
4. Tocar **Instalar**. Si Google Play Protect muestra una advertencia, elegir **Más detalles → Instalar de
   todas formas**.
5. Abrir Pay&Check y entrar con una de las [cuentas de prueba](#semilla-de-la-demo-y-cuentas-de-prueba) o
   crear una cuenta.

Una vez instalada se puede volver a desactivar el permiso del paso 3. Las versiones nuevas se instalan
encima de la anterior (los datos viven en el servidor); si Android dice que el paquete está en conflicto, hay
que desinstalar la versión vieja primero. Para compilar el APK uno mismo, ver
[mobile/README.md](mobile/README.md#generar-un-apk).

## Desplegar

`render.yaml` es un blueprint de Render; la base de datos vive en Neon. El contenedor aplica las migraciones y
siembra las categorías en cada arranque (`backend/start.sh`). Pasos, variables y CI en
[docs/setup.md](docs/setup.md).

## Documentación

| Documento | Qué contiene |
|---|---|
| [docs/README.md](docs/README.md) | Índice de toda la documentación técnica |
| [docs/api.md](docs/api.md) | Endpoints HTTP, autenticación y errores |
| [docs/ia.md](docs/ia.md) | Cómo se usa la IA: modelo, prompts, guardrails, textos de respaldo y lo que sale a Groq |
| [docs/decisiones/](docs/decisiones/) | Registro de decisiones de arquitectura (ADR) |
| [docs/seguridad.md](docs/seguridad.md) | Modelo de amenazas y controles |
| [docs/reglas-calculo.md](docs/reglas-calculo.md) | Fórmulas del presupuesto, casos especiales y ejemplos a mano |
| [docs/informe-adversarial.md](docs/informe-adversarial.md) | Resultados de la suite adversarial de *prompt injection* |
| [docs/planes.md](docs/planes.md) | Planes y cupo de IA |
| [docs/negocio/](docs/negocio/) | Modelo financiero y plantilla de finanzas a 36 meses |
| [docs/setup.md](docs/setup.md) | Puesta en marcha, variables de entorno, CI y despliegue |
| [mobile/README.md](mobile/README.md) | App móvil: pantallas, diseño, SMS simulados, APK |
