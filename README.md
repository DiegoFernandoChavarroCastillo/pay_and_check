# Pay&Check

App de finanzas personales con un coach financiero, para Android y, como respaldo para iPhone y computador, en
la web. Registra gastos e ingresos con muy poca
fricción (texto, voz, foto de un recibo o SMS del banco), dice **cuánto se puede gastar hoy** y acompaña con un
coach que no regaña y con retos e insignias verificados con datos reales.

El repo es un monorepo con dos piezas:

- `backend/`: API REST en Python 3.12 + FastAPI + SQLModel/Alembic + PostgreSQL. IA con [Groq](https://console.groq.com/).
- `mobile/`: app Flutter. Se compila para Android (APK) y para web (Vercel); detalle en
  [mobile/README.md](mobile/README.md).

## Pruébala

| Dónde | Cómo |
|---|---|
| **Android** | Descargar e instalar <https://github.com/PAY-CHECK-SWNT/pay_and_check/releases/latest/download/pay-and-check.apk> (ver [Instalar el APK](#instalar-el-apk)) |
| **iPhone o computador** | Abrir <https://pay-and-check-seven.vercel.app>. En iPhone, Safari → Compartir → *Agregar a pantalla de inicio* |

Las dos usan el mismo backend (`https://paycheck-swnt.duckdns.org`, en AWS) y las mismas cuentas. La versión web
no tiene lo que solo existe en Android: recibos por foto, captura de SMS y notificaciones del banco,
recordatorios y widget ([ADR-010](docs/decisiones/010-version-web-respaldo.md)). Cómo está montado todo:
[docs/despliegue.md](docs/despliegue.md). Lo que falta: [docs/pendientes.md](docs/pendientes.md).

## Qué hace hoy

- **Presupuesto del periodo** y el número central de la app: el disponible por día.
- **Registro de movimientos**: manual, por frase escrita o dictada, por foto de un recibo (el texto se reconoce
  en el teléfono) y desde SMS del banco. La IA solo propone un borrador; la persona lo confirma.
- **Gastos fijos** semanales o mensuales: el día que vencen llega un aviso y quedan por pagar hasta que la
  persona confirma; ahí se descuentan.
- **Coach**: check-in emocional diario, consejos con una acción de un toque, chat, reacción al registrar y
  reporte semanal. Nunca regaña, no recomienda inversiones y no puede inventar cifras.
- **Progreso**: metas de ahorro con dinero realmente apartado, 6 tipos de reto, 23 insignias, puntos y niveles.
- **Reportes**: análisis por semana con gráficas, reporte semanal y resumen mensual (compartible como tarjeta,
  sin montos), y gastos que se repiten (hormiga y suscripciones) con su costo al semestre.
- **Decidir antes de gastar**: «¿Me alcanza?» de contado o a cuotas (cuota, intereses y cómo baja el número del
  día), gastos grandes que vienen (matrícula, libros) con cuánto apartar por semana, y metas con aporte semanal.
- **Vacas**: «lo pagué por varias personas» registra solo la parte propia y deja el resto en «Te deben».
- **Captura automática**: notificaciones de Nequi, Daviplata y bancos, y SMS (planes pagos).
- **Universidad y familia**: panel web de Bienestar Universitario (agregado, anonimato k ≥ 5), apoyos de la
  universidad sugeridos cuando el mes viene difícil, y progreso agregado para quien paga el plan Familiar.
- **Widget de Android** con el número del día y un botón para registrar.
- **Versión web** con diseño adaptable: en un computador o una tableta, menú lateral e Inicio en dos columnas.
- **Planes** Gratis, Premium, Familiar e Institucional (simulados, sin pasarela de pago): se diferencian por
  funciones, no solo por cupo de IA (ver [docs/planes.md](docs/planes.md)).

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

### Datos de demostración y cuentas de prueba

`app.db.seed_demo` siembra las categorías por defecto, la universidad (Escuela Colombiana de Ingeniería) con el
código de convenio **`ECI-2026`**, sus apoyos y el token de su panel, y una cuenta por plan. Se puede correr las
veces que haga falta: borra y vuelve a crear las cuentas demo con fechas relativas a hoy, y conserva la
universidad, así la URL del panel no cambia. Al terminar imprime las cuentas y la URL del panel:

| Correo | Contraseña | Plan |
|---|---|---|
| `valentina@demo.payandcheck.app` | `Demo2026!` | Institucional (canjeó `ECI-2026`). **Cuenta principal:** ocho semanas de historia, gastos fijos, meta, gastos que vienen, una vaca, suscripciones y gastos hormiga; el mes va justo y aparecen la alerta y los apoyos |
| `laura@demo.payandcheck.app` | `Demo2026!` | Premium, con presupuesto a mitad de periodo, dos gastos fijos, movimientos, una meta y una alerta de riesgo |
| `andres@demo.payandcheck.app` | `Demo2026!` | Gratis, sin datos (muestra el bloqueo de la captura automática) |
| `papa@demo.payandcheck.app` | `Demo2026!` | Familiar, titular (código `FAM-DEMO-2026`); ve el progreso de Camilo |
| `camilo@demo.payandcheck.app` | `Demo2026!` | Familiar, integrante que comparte su progreso |
| `estudiante01…30@demo.payandcheck.app` | `Demo2026!` | Institucional, sintéticos para que el panel de Bienestar tenga datos (k ≥ 5) |

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
   (<https://github.com/PAY-CHECK-SWNT/pay_and_check/releases/latest>, o escanear el código QR) y
   descargar `pay-and-check-<versión>.apk`.
2. Abrir el archivo descargado desde la notificación o desde la app *Archivos*.
3. Android avisa que esa app no tiene permiso para instalar apps desconocidas. Tocar **Configuración**,
   activar **Permitir de esta fuente** y volver.
   - En Android 7 o anterior el permiso es general: *Ajustes → Seguridad → Orígenes desconocidos*.
   - La ruta exacta cambia según la marca; también se encuentra en *Ajustes → Apps → Acceso especial →
     Instalar apps desconocidas*.
4. Tocar **Instalar**. Si Google Play Protect muestra una advertencia, elegir **Más detalles → Instalar de
   todas formas**.
5. Abrir Pay&Check y entrar con una de las [cuentas de prueba](#datos-de-demostración-y-cuentas-de-prueba) o
   crear una cuenta.

Una vez instalada se puede volver a desactivar el permiso del paso 3. Las versiones nuevas se instalan
encima de la anterior (los datos viven en el servidor); si Android dice que el paquete está en conflicto, hay
que desinstalar la versión vieja primero. Para compilar el APK uno mismo, ver
[mobile/README.md](mobile/README.md#generar-un-apk).

## Desplegar

| Pieza | Dónde | Cómo se publica |
|---|---|---|
| API | AWS EC2 detrás de Caddy (HTTPS); Render de respaldo | A mano en la instancia ([ADR-011](docs/decisiones/011-backend-aws-ec2.md)); `render.yaml` para Render |
| Base de datos | Neon (PostgreSQL) | Migraciones al arrancar la API (`backend/start.sh`) |
| App Android | GitHub Releases | `git tag vX.Y.Z && git push origin vX.Y.Z` |
| Versión web | Vercel | Sola, en cada push a `main` que toque `mobile/` |

Detalle, variables, Google Sign-In y verificación en [docs/despliegue.md](docs/despliegue.md);
puesta en marcha local y CI en [docs/setup.md](docs/setup.md).

## Documentación

| Documento | Qué contiene |
|---|---|
| [docs/README.md](docs/README.md) | Índice de toda la documentación técnica |
| [docs/despliegue.md](docs/despliegue.md) | Producción: AWS, Vercel, Releases y Google Sign-In |
| [docs/pendientes.md](docs/pendientes.md) | Trabajo pendiente y deuda técnica |
| [docs/negocio/analisis-financiero.md](docs/negocio/analisis-financiero.md) | Costos medidos de IA, proveedores comparados, escenarios a 36 meses y decisiones de planes y precios |
| [docs/api.md](docs/api.md) | Endpoints HTTP, autenticación y errores |
| [docs/ia.md](docs/ia.md) | Cómo se usa la IA: modelo, prompts, guardrails, textos de respaldo y lo que sale a Groq |
| [docs/decisiones/](docs/decisiones/) | Registro de decisiones de arquitectura (ADR) |
| [docs/seguridad.md](docs/seguridad.md) | Modelo de amenazas y controles |
| [docs/reglas-calculo.md](docs/reglas-calculo.md) | Fórmulas del presupuesto, casos especiales y ejemplos a mano |
| [docs/informe-adversarial.md](docs/informe-adversarial.md) | Resultados de la suite adversarial de *prompt injection* |
| [docs/planes.md](docs/planes.md) | Planes y cupo de IA |
| [docs/setup.md](docs/setup.md) | Puesta en marcha, variables de entorno y CI |
| [mobile/README.md](mobile/README.md) | App: pantallas, diseño (también para pantallas anchas), SMS simulados, APK y versión web |
