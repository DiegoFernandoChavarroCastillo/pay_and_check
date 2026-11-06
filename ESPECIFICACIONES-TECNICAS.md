# Pay & Check — Especificaciones técnicas

Documento de presentación para Arquitectura de Software. Reúne en un solo lugar la arquitectura, los
lenguajes, los frameworks, la infraestructura y las decisiones técnicas del proyecto, cada una con el porqué.

---

## 1. Qué es el sistema

**Pay & Check** es una app de finanzas personales para Android con un *coach* financiero. Permite registrar
gastos e ingresos con muy poca fricción (texto, voz, foto de un recibo o SMS del banco), calcula cuánto se
puede gastar por día y acompaña con un coach con IA que nunca regaña, más retos, metas e insignias que se
verifican con datos reales.

| Dato | Valor |
|---|---|
| Tipo de sistema | Aplicación móvil cliente + API REST + base de datos relacional + servicio externo de IA |
| Plataforma cliente | Android (APK directo, sin tienda) |
| Backend en producción | Render (plan gratuito) + PostgreSQL en Neon |
| Tamaño aproximado | ~7.300 líneas de Python en el backend; app Flutter organizada en 9 módulos de funcionalidad |
| Pruebas | 108 tests del backend (pytest) + 42 tests de la app (flutter test) |
| Idiomas de la interfaz | Español e inglés |

---

## 2. Arquitectura general

### 2.1 Estilo arquitectónico

**Cliente-servidor con una API REST stateless y un backend monolítico modular.**

```
┌──────────────────────────────────────────────┐
│          App móvil (Flutter / Android)       │
│  Pantallas ─► Providers (Riverpod) ─► Api    │
│  ML Kit (OCR) · Voz · SMS (canal nativo)     │
│  Notificaciones locales · Almacén seguro     │
└───────────────────────┬──────────────────────┘
                        │ HTTPS + JSON
                        │ Authorization: Bearer <JWT>
                        ▼
┌──────────────────────────────────────────────┐
│          API REST (FastAPI, Python)          │
│  Routers   (capa HTTP, un módulo por dominio)│
│     │                                        │
│  Services  (lógica de negocio determinista)  │
│     │                 └──► groq_client ──────┼──► Groq (LLM)
│  Models    (SQLModel / ORM)                  │
└───────────────────────┬──────────────────────┘
                        │ SQL (psycopg2)
                        ▼
┌──────────────────────────────────────────────┐
│     PostgreSQL 16 (Neon en producción)       │
│     Esquema versionado con Alembic           │
└──────────────────────────────────────────────┘
```

| Decisión | Por qué |
|---|---|
| **Cliente-servidor con API REST** | Separa la app del lugar donde viven los datos y las reglas de negocio, así otro cliente (web, iOS) podría reutilizar la misma API sin tocar la lógica. |
| **Monolito modular en vez de microservicios** | Un equipo pequeño y un solo dominio no justifican la complejidad operativa de varios servicios; la separación se logra con módulos internos (un router, un schema y un service por dominio). |
| **API stateless con JWT** | El servidor no guarda sesiones, así que cualquier instancia puede atender cualquier petición y el despliegue escala horizontalmente sin estado compartido. |
| **Monorepo (`backend/` + `mobile/`)** | Un cambio de contrato de la API y su uso en la app viajan en el mismo commit, y cada parte tiene su propio pipeline de CI filtrado por carpeta. |
| **Sin tareas programadas en el servidor** | Retos vencidos, pagos fijos pendientes y puntos se recalculan "al vuelo" al consultar, lo que elimina workers, colas y crons y funciona en un hosting gratuito que se duerme. |
| **Sin servidor de push** | Los avisos son notificaciones locales programadas en el teléfono: no requieren infraestructura y llegan aunque no haya internet. |

### 2.2 Arquitectura del backend: capas

```
backend/app/
├── main.py        # Composición: crea la app, registra routers, CORS y manejadores de error
├── deps.py        # Dependencias inyectables (usuario autenticado)
├── core/          # Configuración, seguridad (JWT, bcrypt), manejo de zona horaria
├── db/            # Motor y sesión de base de datos, semilla de categorías
├── models/        # Entidades persistentes (tablas)
├── schemas/       # DTOs de entrada y salida de la API (validación)
├── routers/       # Capa HTTP: un archivo por dominio
└── services/      # Lógica de negocio y acceso a la IA
```

| Decisión | Por qué |
|---|---|
| **Arquitectura en capas (routers → services → models)** | Cada capa tiene una sola responsabilidad: el router traduce HTTP, el service decide reglas de negocio y el modelo persiste; así la lógica se prueba sin pasar por HTTP. |
| **Schemas separados de los modelos** | Lo que entra y sale por la API no es lo mismo que lo que se guarda (por ejemplo, nunca se devuelve el hash de la contraseña), y separarlos evita exponer la base de datos por accidente. |
| **Inyección de dependencias con `Depends` de FastAPI** | La sesión de base de datos y el usuario actual se inyectan en cada endpoint, lo que permite reemplazarlos en los tests (SQLite en memoria) sin cambiar el código. |
| **Un módulo por dominio** (auth, budgets, expenses, incomes, categories, recurring_expenses, checkins, coach, goals, gamification, reports) | Cada funcionalidad queda aislada y es fácil de ubicar, de probar y de extender sin tocar las demás. |
| **Toda la comunicación con la IA en `services/groq_client.py` y los prompts solo en `services/prompts.py`** | Aísla al proveedor externo detrás de un único punto (patrón *gateway/adapter*), así cambiar de modelo o de proveedor afecta un solo archivo. |
| **Configuración por variables de entorno (`pydantic-settings`)** | Sigue los principios *12-factor*: el mismo código corre en local, CI y producción cambiando solo el entorno, y los secretos nunca entran al repositorio. |
| **Manejadores globales de errores** | Toda respuesta de error tiene el mismo formato JSON y los errores inesperados se registran en el log sin filtrar detalles internos al cliente. |
| **Endpoint `/health` que consulta la base** | Render lo usa para saber si el servicio está realmente vivo (incluida la conexión a la base), no solo si el proceso arrancó. |

### 2.3 Arquitectura de la app móvil

```
mobile/lib/
├── main.dart, app.dart   # Arranque, rutas, tema e idioma
├── core/                 # Cliente HTTP, configuración, tema, formato, notificaciones, gráficas, animaciones
├── data/                 # Modelos, llamadas a la API (Api), sesión y providers de datos
├── l10n/                 # Textos en español e inglés
└── features/             # Una carpeta por funcionalidad (solo pantallas)
    ├── auth/ shell/ home/ budget/ transactions/
    ├── coach/ progress/ reports/ profile/ sms/
```

| Decisión | Por qué |
|---|---|
| **Organización por funcionalidad (*feature-first*)** | Las pantallas de cada parte del producto están juntas, así se navega el código igual que se navega la app. |
| **Capa de datos compartida (`data/`) en vez de una por feature** | Con un solo backend y pantallas que comparten casi todos los datos (el inicio usa los de todas), repartir modelos y llamadas por feature habría duplicado código. |
| **Clase `Api` como única puerta al backend** | Las pantallas nunca hablan HTTP directamente; eso permite sustituir el backend por un `FakeApi` en los tests. |
| **`TokenStorage` como interfaz** | El almacén seguro real necesita el sistema operativo; abstraerlo deja probar la sesión sin teléfono. |
| **Funcionalidades nativas detrás de un `MethodChannel` aislado (SMS)** | La lectura de SMS es lo único que requiere código Kotlin y un permiso sensible, así que vive en un solo módulo que se puede quitar sin afectar el resto. |

---

## 3. Lenguajes

| Lenguaje | Dónde | Por qué |
|---|---|---|
| **Python 3.12** | Backend | Tiene el ecosistema más maduro para APIs con IA y validación de datos, y su tipado opcional (`type hints`) se aprovecha en FastAPI y Pydantic. |
| **Dart 3** | App móvil | Es el lenguaje de Flutter; tiene tipado fuerte con *null safety*, que evita en compilación los errores de valores nulos. |
| **Kotlin** | `MainActivity.kt` (canal de SMS) | Es el lenguaje oficial de Android y se necesitaba solo para leer la bandeja de SMS, algo que Flutter no ofrece. |
| **SQL (PostgreSQL)** | Base de datos y migraciones | El dominio es financiero y relacional (usuarios, presupuestos, gastos, categorías), y SQL garantiza integridad y consultas agregadas exactas. |
| **YAML / Shell / Dockerfile** | CI, despliegue y arranque | Son los formatos estándar de GitHub Actions, Render, Docker Compose y contenedores. |

---

## 4. Backend: frameworks y librerías

| Tecnología | Para qué | Por qué |
|---|---|---|
| **FastAPI** | Framework web de la API | Genera la documentación OpenAPI (`/docs`) automáticamente, valida las peticiones con los tipos de Python y tiene inyección de dependencias integrada. |
| **Uvicorn** | Servidor ASGI | Es el servidor recomendado para FastAPI, liviano y de alto rendimiento. |
| **SQLModel** (sobre SQLAlchemy) | ORM | Una misma clase sirve de modelo de tabla y de tipo Pydantic, lo que reduce código repetido y mantiene la validación coherente con la base. |
| **Alembic** | Migraciones del esquema | Versiona cada cambio de la base (9 migraciones) para aplicarlo de forma reproducible e idempotente en local, CI y producción. |
| **Pydantic / pydantic-settings** | Validación de datos y configuración | Rechaza datos inválidos en el borde de la API y carga la configuración desde el entorno con tipos verificados. |
| **psycopg2** | Driver de PostgreSQL | Es el driver estándar y más estable de PostgreSQL para Python. |
| **python-jose** | Firma y verificación de JWT | Implementa el estándar JWT para emitir tokens de acceso y de renovación sin guardar estado en el servidor. |
| **passlib + bcrypt** | Hash de contraseñas | bcrypt es un algoritmo lento a propósito y con sal, lo que hace inviable descifrar contraseñas aunque se filtre la base. |
| **google-auth** | Login con Google | Verifica la firma del token de Google contra las llaves oficiales, sin confiar en lo que diga el cliente. |
| **groq (SDK)** | Cliente del modelo de lenguaje | Groq ofrece inferencia muy rápida y un plan gratuito, suficiente para desarrollo, con modelos abiertos (`openai/gpt-oss-20b`). |
| **tzdata** | Zonas horarias | "Hoy" depende de la zona horaria de cada persona (por defecto `America/Bogota`) y no de la del servidor, que corre en UTC. |
| **uv** | Gestor de dependencias y entorno | Es mucho más rápido que pip y el `uv.lock` fija versiones exactas, así todos los entornos instalan lo mismo. |
| **Ruff** | Linter | Un solo linter muy rápido que reemplaza a varios (flake8, isort, pyupgrade) y se ejecuta en CI. |
| **pytest + pytest-mock** | Pruebas | Es el estándar de Python; los *fixtures* permiten preparar una base limpia y simular la IA en cada test. |

---

## 5. App móvil: frameworks y librerías

| Tecnología | Para qué | Por qué |
|---|---|---|
| **Flutter 3.47** | Framework de la interfaz | Un solo código produce una app nativa compilada, con buen rendimiento, recarga en caliente para iterar rápido y la puerta abierta a iOS sin reescribir. |
| **Riverpod** | Manejo de estado | Expone los datos como *providers* declarativos que se recalculan al cambiar la sesión, se invalidan en bloque tras un cambio y se reemplazan fácilmente en los tests. |
| **go_router** | Navegación | Centraliza las rutas y redirige según el estado de la sesión (login, splash o inicio) en un solo lugar. |
| **Dio** | Cliente HTTP | Soporta interceptores, que se usan para añadir el token a cada petición y renovarlo automáticamente ante un 401 sin que las pantallas se enteren. |
| **flutter_secure_storage** | Guardar los tokens | Usa el Keystore de Android, que cifra los tokens en vez de dejarlos en texto plano. |
| **shared_preferences** | Preferencias no sensibles | Para ajustes como el tema o los SMS ya revisados, que no necesitan cifrado. |
| **google_mlkit_text_recognition** | OCR de recibos | Reconoce el texto en el propio teléfono: es gratis, funciona sin internet y la foto nunca sale del dispositivo. |
| **image_picker** | Cámara y galería | Es el plugin oficial para obtener la foto del recibo. |
| **speech_to_text** | Registro por voz | Usa el reconocimiento de voz del sistema, sin costo y sin un servicio propio. |
| **flutter_local_notifications + timezone + flutter_timezone** | Recordatorios | Programa avisos en el teléfono (check-in diario, gastos fijos) a la hora local correcta sin necesitar un servidor de push. |
| **google_sign_in** | Login con Google | Es el plugin oficial; entrega el token que luego verifica el backend. |
| **fl_chart** | Gráficas | Dibuja la dona por categorías y la tendencia semanal con widgets de Flutter, sin vistas web. |
| **intl + flutter_localizations (ARB)** | Idiomas y formato | Traduce la interfaz (español e inglés) y formatea montos y fechas según el idioma. |
| **flutter_lints** | Análisis estático | Aplica las reglas de estilo oficiales y se verifica en CI con `flutter analyze`. |
| **Plus Jakarta Sans (fuente empaquetada)** | Tipografía | Licencia libre (OFL) y empaquetada en la app, así se ve igual en todos los teléfonos y sin conexión. |

---

## 6. Datos y persistencia

| Decisión | Por qué |
|---|---|
| **PostgreSQL 16** | Base relacional con transacciones ACID y tipos `NUMERIC` exactos, imprescindibles para manejar dinero sin errores de redondeo. |
| **Neon como Postgres gestionado** | Ofrece un plan gratuito sin administrar servidores, y la cadena de conexión funciona igual que la de un Postgres local. |
| **Montos con `Decimal`, nunca `float`** | Los `float` acumulan errores de redondeo; con `Decimal` las sumas de dinero son exactas al centavo. |
| **Restricciones en la base** (por ejemplo `ck_challenges_tipo_valido`, gasto fijo único por fecha) | La integridad la garantiza la base además del código, así ni un bug ni dos peticiones simultáneas dejan datos inválidos. |
| **Migraciones aplicadas al arrancar (`start.sh`)** | El despliegue siempre deja el esquema al día sin pasos manuales; `alembic upgrade` y la semilla son idempotentes. |
| **Categorías por defecto compartidas + límites por persona en una tabla aparte (`category_limits`)** | Las categorías por defecto son un registro común, así que el límite propio de cada persona no puede vivir en ellas sin afectar a los demás. |
| **`pool_pre_ping` y `pool_recycle`** | Neon cierra las conexiones inactivas; comprobarlas antes de usarlas evita errores 500 tras un rato sin tráfico. |
| **Sin almacenamiento de imágenes** | Al backend solo llega el texto reconocido del recibo, lo que ahorra infraestructura (S3) y protege la privacidad. |

**Entidades principales:** `User`, `Budget`, `Category`, `CategoryLimit`, `Expense`, `Income`,
`RecurringExpense`, `EmotionalCheckin`, `CoachMessage`, `Goal`, `GoalContribution`, `Challenge`,
`Achievement`, `PointEvent` (y `Group`, reservada para un futuro modo grupal).

---

## 7. Inteligencia artificial

| Decisión | Por qué |
|---|---|
| **"La IA redacta, no calcula"** | Toda cifra (disponible, patrones, puntos, retos) sale de código determinista y probado; el modelo solo redacta el texto, porque un LLM puede equivocarse en cuentas y aquí se trata de dinero. |
| **Guardrails sobre cada respuesta** | Se descarta el texto si trae lenguaje culposo, asesoría de inversión o cifras que no estaban en los datos de origen (`inventa_cifras`), porque se detectó en pruebas reales que el modelo inventaba números. |
| **Texto de respaldo determinista** | Si Groq falla, tarda o falta la API key, la app muestra un texto calculado y nunca se queda sin respuesta. |
| **La IA propone y la persona confirma** | Todo gasto interpretado por la IA (texto, voz, recibo o SMS) pasa por una pantalla de confirmación editable, porque el modelo a veces clasifica mal. |
| **JSON pedido en el prompt y extraído por el backend, sin el "modo JSON" de Groq** | Con este modelo el modo JSON devolvía respuestas vacías de forma intermitente; extraerlo del texto resultó más confiable. |
| **Razonamiento `low` para extraer y `medium` para redactar** | Extraer un gasto es mecánico y debe ser rápido y barato; redactar un consejo necesita más elaboración o el modelo solo copia el dato. |
| **Modelo como constante (`MODEL`, `COACH_MODEL`)** | Cambiar de modelo, o usar uno más grande solo para el coach, es cambiar una línea. |
| **OCR en el teléfono + estructura con el LLM** | ML Kit lee el texto sin costo y sin enviar la foto; el LLM de texto que ya se usaba lo convierte en comercio, fecha, total y categoría. |

---

## 8. Seguridad y privacidad

| Decisión | Por qué |
|---|---|
| **JWT de acceso (60 min) + refresh token (30 días)** | El token de acceso dura poco para limitar el daño si se filtra, y el de renovación evita pedir la contraseña cada hora. |
| **Tipo de token dentro del JWT (`access` / `refresh`)** | Impide usar un refresh token para autenticarse en la API o al revés. |
| **Renovación en un `QueuedInterceptor`** | Si varias peticiones reciben 401 a la vez, se renueva el token una sola vez en lugar de varias en paralelo. |
| **Contraseñas con bcrypt** | Hash lento y con sal; nunca se guarda ni se devuelve la contraseña. |
| **Correos normalizados a minúsculas** | Evita cuentas duplicadas por diferencias de mayúsculas. |
| **Cada consulta filtrada por el usuario autenticado** | Una persona no puede leer ni modificar datos de otra aunque adivine un id. |
| **Borrado total de la cuenta (`DELETE /auth/me`) y pantalla de privacidad** | La persona controla sus datos y ve qué se usa y para qué. |
| **SMS leídos bajo demanda y aprobados uno por uno** | Nada se envía al servidor hasta que la persona decide registrar ese movimiento. |
| **HTTPS en producción** | Tokens y datos financieros no viajan en texto plano. |
| **Contenedor como usuario no-root** | Si alguien comprometiera la app, no tendría privilegios de administrador en el contenedor. |
| **Secretos fuera de git** (`.env`, keystore, `key.properties`) | Se cargan como variables de entorno o secretos de GitHub, nunca en el código. |

**Limitación conocida:** el refresh token no se puede revocar antes de que expire (es un JWT sin estado);
revocarlo exigiría una tabla de tokens.

---

## 9. Infraestructura y despliegue

| Tecnología | Para qué | Por qué |
|---|---|---|
| **Docker (imagen multi-stage)** | Empaquetar el backend | La etapa de build instala dependencias con `uv` y la imagen final solo lleva el entorno resuelto y el código, así queda liviana y sin herramientas de compilación. |
| **Docker Compose** | Entorno local (API + Postgres 16) | Levanta todo con un comando e idéntico para cualquier desarrollador. |
| **Render (blueprint `render.yaml`)** | Hosting del backend | Despliega directo desde el `Dockerfile` con plan gratuito y la infraestructura queda descrita como código en el repositorio. |
| **Región Ohio (igual que Neon, AWS us-east-2)** | Ubicación del servidor | Cada petición hace varias consultas; tener la API y la base en la misma región reduce la latencia. |
| **`start.sh` como punto de entrada** | Arranque en producción | Migra, siembra y arranca en un script versionado, porque Render no interpretaba bien un comando con comillas en su configuración. |
| **`JWT_SECRET` generado por Render** | Secreto de firma | Se crea aleatorio y nunca lo escribe una persona. |
| **APK firmado con keystore propio** | Distribución de la app | Sin la misma llave en cada versión, las personas tendrían que desinstalar la app para actualizarla. |
| **APK directo (sin Play Store)** | Distribución en esta etapa | Evita el costo y el trámite de la tienda (en especial el del permiso de SMS) mientras el producto se valida con probadores. |
| **Configuración de la app por `--dart-define`** | URL del backend y Client ID de Google | La misma app se compila contra local, emulador o producción sin cambiar código. |

**Costo de operación actual:** cero. Contrapartida: el servicio gratuito de Render se duerme tras unos 15
minutos sin uso y la primera petición tarda cerca de un minuto (por eso la app espera hasta 45 s una
respuesta).

---

## 10. Calidad: pruebas y CI/CD

| Decisión | Por qué |
|---|---|
| **Tests del backend herméticos** (SQLite en memoria, IA simulada) | Corren en segundos, sin internet, sin base real ni API key, igual en el PC que en CI. |
| **Migraciones verificadas en Postgres real** | SQLite no ejercita Alembic, así que las migraciones se comprueban aparte en el Postgres de Docker. |
| **Tests de la app con `FakeApi` y `FakeSmsSource`** | Prueban pantallas y flujos sin backend ni teléfono. |
| **Capturas generadas por test (`tool/screenshots_test.dart`)** | Permiten revisar todas las pantallas en claro, oscuro y con letra grande sin un dispositivo. |
| **GitHub Actions: `backend-ci.yml`** | En cada push o PR que toca `backend/` corre `ruff` y `pytest`; un cambio roto no pasa desapercibido. |
| **GitHub Actions: `mobile-ci.yml`** | En cada push o PR que toca `mobile/` genera traducciones, corre `flutter analyze` y `flutter test`. |
| **GitHub Actions: `mobile-release.yml`** | Al empujar un tag `v*` compila el APK firmado y lo publica en un GitHub Release: la entrega a probadores es reproducible y es un enlace. |
| **Pipelines filtrados por carpeta** | En el monorepo, un cambio en la app no dispara las pruebas del backend y viceversa. |
| **Versiones fijadas** (`uv.lock`, `pubspec.lock`, Flutter 3.47.7 en CI) | El build de hoy y el de dentro de un mes usan exactamente las mismas dependencias. |

---

## 11. Diseño de la interfaz

| Decisión | Por qué |
|---|---|
| **Estilo "bento" (mosaico de tarjetas) en pantallas de resumen** | Permite ver de un vistazo disponible, semana, coach, meta y reto; en listas y formularios no se usa porque ahí estorba. |
| **Sistema de diseño propio en `core/`** (`AppTokens`, `BentoTile`, `BentoRow`, `ProgressRing`) | Colores, tipografía y componentes se definen una vez y se reutilizan, así la app es consistente y un cambio de estilo es local. |
| **Un color de acento por zona** (coach lavanda, metas ámbar, retos coral, ingresos azul) | Orienta a la persona sin texto extra; la paleta evita el rojo y el verde "de semáforo" para no transmitir culpa. |
| **Todas las animaciones pasan por `motion()`** | Respeta la opción "quitar animaciones" del teléfono (accesibilidad). |
| **`BentoRow` se apila en pantallas angostas o con letra grande** | La app sigue siendo usable con el tamaño de letra del sistema al máximo. |
| **Modo claro y oscuro** | Comodidad visual y accesibilidad. |
| **Textos de ambos idiomas en una sola tabla (`tool/gen_arb.py`)** | Español e inglés se editan lado a lado y no se desincronizan; los archivos ARB se generan. |

---

## 12. Reglas de negocio que definen la arquitectura

1. **Nada se auto-reporta.** Metas, retos, puntos e insignias se calculan desde los gastos y check-ins
   reales; el libro de puntos es idempotente, así recalcular nunca duplica puntos.
2. **Puntos por constancia, no por monto.** Se premia registrar, hacer check-in y cumplir el ritmo, para no
   castigar a quien gana menos.
3. **Las metas son "apartados" virtuales.** Sin banco conectado, el dinero apartado se descuenta del
   disponible del presupuesto; solo se puede apartar dinero que existe.
4. **Los gastos fijos esperan confirmación.** Programar un pago no es pagarlo: solo descuenta del disponible
   cuando la persona lo confirma.

---

## 13. Diferencias con la propuesta inicial

La visión original del producto (`mejoras.md`) sugería otro stack. Se adaptó para no añadir infraestructura
ni costo en la etapa de validación:

| Propuesta inicial | Lo construido | Por qué |
|---|---|---|
| React Native + Expo | Flutter | Compila a código nativo, usa un solo lenguaje tipado y tiene plugins maduros para lo que la app necesita (ML Kit, Google Sign-In, notificaciones, voz). |
| Node.js + NestJS | FastAPI (Python) | El backend del MVP ya existía en FastAPI, funcionaba y tenía tests; se extendió en lugar de reescribirlo. |
| OpenAI GPT-4o | Groq (`openai/gpt-oss-20b`) | Gratis y muy rápido; como la IA solo redacta, un modelo pequeño es suficiente. |
| Google Vision + S3 | ML Kit en el teléfono | Gratis, sin conexión y la foto no sale del dispositivo. |
| Firebase Cloud Messaging | Notificaciones locales | Solo se necesitan recordatorios; no hace falta un servidor de push. |
| Redis (caché/sesiones) | Sin Redis | Con JWT sin estado no hay sesiones que guardar, y el volumen actual no necesita caché. |
| Scheduler / ML en Python | Cálculo al consultar + reglas deterministas | Sin procesos en segundo plano; los resultados son explicables y probados. |
| Plaid / Belvo (bancos) | Registro manual, por IA y por SMS | La integración bancaria tiene costo y requisitos regulatorios fuera del alcance del MVP. |

---

## 14. Limitaciones conocidas y trabajo futuro

- Solo Android; no hay versión de iOS (Flutter la permitiría sin reescribir la app).
- Sin sincronización bancaria ni lectura de correos (Gmail exige una auditoría de seguridad de pago).
- El refresh token no es revocable antes de expirar.
- El plan gratuito de Groq limita a 8.000 tokens por minuto: alcanza para desarrollo, no para usuarios reales.
- El hosting gratuito se duerme y la primera petición tarda cerca de un minuto.
- La lectura de SMS no se ha probado con mensajes reales de bancos colombianos.
- Los mensajes de error del backend solo están en español.
- Pendiente: ligas sociales, retos colaborativos y modo grupal (la tabla `Group` ya está reservada).
