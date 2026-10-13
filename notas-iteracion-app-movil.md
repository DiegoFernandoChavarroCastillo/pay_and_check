# Notas de la iteración — app móvil (fases 1 a 7 de `plan-app-movil.md`)

Fecha: 2026-10-11. Este documento recoge los bugs, problemas y decisiones técnicas de la iteración en la
que se construyeron el backend de las fases 3–5 y 7 y la app Flutter completa. El avance tarea por tarea
está en `plan-app-movil.md`.

## 1. Estado en una página

| Qué | Estado | Cómo se comprobó |
|---|---|---|
| Backend (coach, metas, retos, puntos, recibos, wrapped) | Hecho | 87 tests de `pytest` en verde, `ruff` limpio, y recorrido por HTTP real contra Postgres de los endpoints nuevos. La última migración (`7f2a9c4e1d05`) **no se ha aplicado en Postgres** |
| App Flutter (todas las pantallas del plan) | Hecho, **sin probar en un teléfono** | `flutter analyze` sin avisos, 16 tests (flujo de login → dashboard, confirmación de gastos, acción del coach, renovación de sesión) |
| APK de release firmado | **No generado** | El build se intentó tres veces y no terminó (ver sección 3, "Al compilar el APK"). Firma, ícono y workflow de release están configurados |
| Coach con IA real | **Sin probar** | No hay `GROQ_API_KEY` en este PC: todo lo de IA se probó con la IA simulada y con sus textos de respaldo |
| Login con Google | **Sin probar** | Falta crear el Client ID (requiere tu cuenta de Google) |
| Backend desplegado | **Pendiente** | Requiere tus cuentas de Render y Neon; queda listo `render.yaml` |

Lo más importante de esta tabla: **nadie ha visto la app correr en un teléfono y todavía no existe un APK**.
No había teléfono ni emulador en este PC, y el build de release no llegó a completarse. El código Dart pasa
el analizador y sus pruebas, y el segundo intento de build compiló todo el código nativo antes de fallar en
el último paso (ya corregido), pero hasta que un build termine no hay garantía de que el APK se genere. La
primera instalación real casi seguro revelará además ajustes visuales y de permisos.

## 2. Lo que necesito de ti para cerrar

1. **Compilar y probar el APK.** Con Docker Desktop y otros programas pesados cerrados, desde `mobile/`:
   `flutter build apk --release --dart-define=API_BASE_URL=http://localhost:8000`. Con el teléfono por USB,
   el backend local arriba y `adb reverse tcp:8000 tcp:8000`, instalarlo con
   `adb install build/app/outputs/flutter-apk/app-release.apk`. Si este PC sigue sin memoria suficiente, la
   alternativa es dejar que lo compile GitHub Actions (`mobile-release.yml`).
1. **Aplicar la última migración** en la base local: `docker compose up -d db`, luego en `backend/`
   `uv run alembic upgrade head` y `uv run python -m app.db.seed`.
2. **`GROQ_API_KEY`** en `backend/.env` (y en Render). Sin ella la app funciona, pero el registro por frase,
   voz o recibo responde error y el coach habla solo con sus plantillas.
3. **Client ID de Google** (web + Android). La huella SHA-1 del keystore de la app es
   `15:35:88:71:90:8A:1F:88:A3:51:3D:B2:9A:B7:50:1B:34:4C:5A:B9`. Pasos en `mobile/README.md`.
4. **Desplegar el backend** con `render.yaml` y recompilar el APK con esa URL.
5. **Copia de seguridad del keystore**: `mobile/android/upload-keystore.jks` y `mobile/android/key.properties`.
   Están fuera de git a propósito y solo existen en este PC. Si se pierden, quien ya tenga la app instalada
   no podrá actualizarla sin desinstalar.
6. **Commit**: no hice ningún commit ni push; todo está en el árbol de trabajo de `develop`.

## 3. Bugs encontrados y corregidos

### En el backend que ya existía

- **Gastos fijos duplicados por peticiones simultáneas.** `sync_recurring_expenses` se ejecuta en
  `GET /expenses` y en `GET /budgets/active/summary`. La app pide ambos a la vez al abrir, y las dos
  peticiones podían generar el mismo gasto semanal. Antes no se notaba porque nadie llamaba los dos endpoints
  en paralelo. Se agregó una restricción única `(recurring_expense_id, fecha)` (migración `7f2a9c4e1d05`, que
  además limpia duplicados si los hubiera) y el servicio descarta el segundo intento.
- **"Hoy" según el reloj del servidor.** Todo usaba `date.today()`, que en producción es UTC: desde las 7 pm
  en Colombia el backend ya consideraba que era mañana (presupuesto activo, disponible por día, gastos fijos).
  Ahora cada usuario tiene `zona_horaria` y la app la sincroniza con la del teléfono al iniciar sesión.
- **La sesión duraba 60 minutos y no se podía renovar.** Inusable en un teléfono. Se agregó refresh token
  (`POST /auth/refresh`) y la app renueva sola ante un 401.
- **Tests que fallaban según el día del mes.** Tres archivos creaban el presupuesto de prueba hasta el día
  28: del 29 al 31 de cada mes los tests habrían fallado sin que el código estuviera mal.
- **El contexto de Docker incluía `.venv` y `.env`.** No había `.dockerignore`: el `COPY . .` metía al build
  el entorno virtual del host (de otro sistema operativo en este PC) y los secretos locales. Los secretos no
  llegaban a la imagen final, pero sí a la etapa de build. Se agregó `backend/.dockerignore`.
- **El backend no arrancaba sin `GOOGLE_CLIENT_ID` ni `GROQ_API_KEY`.** Eran obligatorias aunque la función
  no se usara. Ahora son opcionales; sin Client ID el login con Google rechaza todo token de forma explícita
  (no se valida contra una audiencia vacía).
- **`.gitignore` ignoraba el código de la app.** La plantilla de Python de la raíz ignora `lib/`, que es
  donde vive todo el código Flutter. Se agregó la excepción `!mobile/lib/`.

### En el código nuevo, detectados por los tests o las pruebas contra Postgres

- **Puntos duplicados / error 500 por peticiones simultáneas.** Mismo origen que el de los gastos fijos: la
  app pide perfil y retos a la vez y ambas sincronizan la gamificación. El test que lo simula mostró que el
  choque ocurre incluso antes del `commit` (en un autoflush), así que la protección envuelve toda la
  sincronización, no solo el guardado.
- **"Mejora mensual" falsa.** Un mes sin ningún gasto registrado contaba como "ahorro del 100 %", y el mes
  siguiente aparecía como un retroceso de 35 puntos. Un periodo sin registros ahora es "sin datos".
- **Patrón de fin de semana con un solo dato.** Un único gasto en sábado generaba el consejo "gastas 1.000
  los fines de semana frente a 0 entre semana". Ahora exige al menos dos días de fin de semana con gasto.
- **Reto sugerido que no se podía aceptar.** El coach sugería "20 % menos en X" aunque no hubiera gasto en X
  la semana anterior, y aceptarlo daba error. Si no hay gasto la semana previa, la referencia pasa a ser el
  promedio semanal del último mes.
- **Reto ya cumplido que mostraba "6 de 3".** Un reto de acumular seguía contando días después de cumplirse.
- **Guardrails del coach.** Las pruebas confirman que una respuesta de la IA con lenguaje culposo o con una
  recomendación de inversión se descarta y se reemplaza por el texto de respaldo.

### Al compilar el APK

El APK **no se llegó a generar**. Hubo tres intentos:

1. **Sin memoria.** La plantilla de Flutter le da 8 GB a Gradle; este PC tiene 12 GB y, con Docker Desktop
   abierto, el compilador de Dart murió por falta de memoria. Se bajó a 3 GB
   (`mobile/android/gradle.properties`) y se cerró Docker.
2. **R8 abortó en el último paso**, después de compilar todo el código Dart y nativo, por clases de ML Kit
   para chino, japonés, coreano y devanagari, que son opcionales y la app no usa. Se agregó
   `mobile/android/app/proguard-rules.pro`. Esta corrección **no está comprobada**: el intento siguiente no
   llegó tan lejos.
3. **Detenido por el sistema.** Claude Code canceló el build porque el PC volvió a quedarse con muy poca
   memoria libre. No lo relancé por mi cuenta.

Cada intento tarda entre 7 y 10 minutos en este equipo.

## 4. Decisiones técnicas

### Las que cambian lo que decía el plan

- **Sin `fl_chart`.** El desglose por categoría, metas y retos usan barras de progreso nativas. Son las
  únicas gráficas que la app necesita hoy y evitan una dependencia más sin haber visto la app en pantalla.
- **Capa de datos compartida.** El plan pedía `data/domain/ui` dentro de cada feature. Los modelos, las
  llamadas a la API y los providers quedaron juntos en `mobile/lib/data/`, y cada feature solo tiene sus
  pantallas. Con un backend único y pantallas que comparten casi todos los datos (el dashboard usa los de
  todas), repartirlos por feature habría duplicado código.
- **El onboarding no es una ruta aparte.** Si no hay presupuesto activo, Inicio invita a crearlo y esa
  pantalla pregunta también el estilo del coach.
- **Modelo del coach sin cambiar.** El plan proponía evaluar `openai/gpt-oss-120b`. Sin `GROQ_API_KEY` no se
  pudo evaluar nada, así que el coach usa el mismo modelo que el parseo; es una constante (`COACH_MODEL` en
  `backend/app/services/groq_client.py`).

### Las que conviene que conozcas

- **La IA redacta, no calcula.** Patrones, puntos, retos y metas se calculan con código determinista. La IA
  recibe esas cifras ya hechas y solo las redacta en el tono elegido. Si falla o rompe una regla, el usuario
  ve el texto determinista: la app nunca se queda sin respuesta.
- **Las metas son "apartados" virtuales.** No hay banco conectado, así que "mover dinero a una meta" lo
  descuenta del disponible del presupuesto. Solo se puede apartar dinero que existe y una meta se cumple
  únicamente cuando lo apartado alcanza el objetivo. Borrar la meta devuelve el dinero.
- **Puntos por constancia, no por monto.** 5 por día con registro (uno o veinte gastos dan lo mismo), 5 por
  check-in, hitos de racha, 30 por semana cerrada por debajo del ritmo, 50 por mejorar el ahorro frente al
  mes anterior, y los del reto o meta cumplidos. Los gastos fijos automáticos no dan puntos.
- **Todo se calcula al consultar, sin tareas programadas.** Igual que los gastos fijos del backend original.
  Consecuencia: un reto vencido se marca como cumplido o fallido la próxima vez que el usuario abre la app.
- **Las categorías por defecto no admiten límite.** Son un registro compartido por todos los usuarios, así
  que el coach solo propone "poner límite" sobre categorías propias; para las demás propone un reto.
- **El refresh token no se puede revocar.** Es un JWT sin estado: cerrar sesión lo borra del teléfono, pero
  uno robado serviría hasta expirar (30 días). Revocarlos exige una tabla de tokens; no se hizo.
- **Recibos: la foto no sale del teléfono.** El texto se reconoce con ML Kit en el dispositivo y al backend
  viaja solo el texto. No hay almacenamiento de imágenes.
- **SMS: lectura bajo demanda.** No hay servicio en segundo plano: la app lee los SMS de los últimos 14 días
  cuando abres esa pantalla, muestra los que parecen movimientos bancarios y nada se envía hasta que eliges
  registrar uno. El filtro es por palabras clave y no se ha probado con SMS reales de bancos colombianos.
- **Recordatorio local e inexacto.** El recordatorio del check-in es una notificación programada en el
  teléfono, sin servidor de push, y Android puede atrasarla unos minutos (a cambio no pide el permiso
  especial de alarmas exactas).
- **Textos en una sola tabla.** Español e inglés están lado a lado en `mobile/tool/gen_arb.py`; de ahí se
  generan los archivos de traducción. Los mensajes de error que vienen del backend siguen solo en español.
- **Nombre e identificador provisionales.** "Pay & Check" y `com.diegochavarro.pay_and_check`. El
  identificador se puede cambiar sin costo hasta que se cree el Client ID Android de Google o se reparta el
  primer APK; después, cambiarlo equivale a publicar otra app.

## 5. Problemas abiertos y limitaciones conocidas

- **Sin prueba en dispositivo** (ya dicho): voz, cámara, OCR, notificaciones, SMS y login con Google solo se
  pueden validar en un teléfono.
- **Íconos antiguos en Android 7.** El ícono nuevo es adaptativo (Android 8+). En Android 7 se verá el ícono
  por defecto de Flutter.
- **Editar el objetivo de un reto no existe**, ni retos de más de 7 días: solo aceptar y abandonar.
- **Ligas, retos colaborativos, Gmail y bancos** siguen fuera, como en el plan.
- **Base local sin categorías y una migración atrás.** Al limpiar los datos de prueba se vaciaron también
  las categorías por defecto de la base de Docker local, y la migración `7f2a9c4e1d05` (restricción única de
  gastos fijos) se escribió después de apagar Docker para liberar memoria. Esa migración usa una sentencia
  propia de Postgres para limpiar duplicados y solo se ha ejercitado indirectamente (los tests corren sobre
  SQLite, que crea las tablas desde los modelos): hay que verla pasar en Postgres.
- **Aviso al compilar** sobre `CupertinoIcons`: algún componente de Flutter los referencia y el paquete no
  está incluido. No afecta a las pantallas actuales.

## 6. Qué se instaló en este PC

`uv`, JDK 17 (Microsoft OpenJDK), Flutter 3.47.7 en `C:\Users\chava\dev\flutter` y el Android SDK de línea de
comandos en `%LOCALAPPDATA%\Android\Sdk` (sin Android Studio). Se agregaron al usuario las variables
`ANDROID_HOME` y `JAVA_HOME` y las rutas de Flutter y `platform-tools` al `PATH`; hay que abrir una terminal
nueva para verlas.

## 7. Iteración de UX: gráficas y animaciones

Plan en `C:\Users\chava\.claude\plans\wobbly-puzzling-kahan.md`. Estado: backend con 92 tests y `ruff` limpio;
app con `flutter analyze` limpio y 26 tests. **No se ha visto corriendo en el emulador** (no había memoria
para levantarlo junto con el build): falta la revisión visual.

### Qué se añadió

- **`GET /reports/trends?semanas=8`** (`backend/app/services/trends.py`): gasto por semana y por categoría, más
  el día a día de las dos últimas semanas. Sin IA y sin migración.
- **Pantalla "Análisis"** (`mobile/lib/features/reports/analytics_screen.dart`): torta de la semana por
  categorías, comparación con la semana anterior y tendencia por semanas o por días. Se abre desde la tarjeta
  "Esta semana" del inicio y desde Perfil → Resúmenes.
- **`mobile/lib/core/charts.dart`** (`CategoryDonut`, `TrendLine`) y **`mobile/lib/core/motion.dart`**
  (`AnimatedMoney`, `FadeSlideIn`, `motion()`), con `fl_chart` como única dependencia nueva.
- Animaciones: montos que cuentan, barras de progreso que crecen, entrada escalonada de tarjetas, fundido de
  carga a datos y entre pestañas, transición entre pantallas, emoji del check-in, diálogo de insignia nueva y
  vibración al guardar un gasto.

### Decisiones

- **La tendencia no se filtra por presupuesto**, solo por usuario y fechas: si no, la línea se cortaba al
  cambiar de periodo. `/reports/weekly` sí sigue atado al presupuesto activo.
- **El reporte semanal no sirve como fuente de las gráficas**: llama a Groq en cada consulta. Por eso el
  endpoint nuevo es aparte y solo numérico.
- **Colores por nombre de categoría**, no por posición: una categoría conserva su color de una semana a otra.
  La paleta evita el rojo y el verde "de semáforo" (principio de cero culpa).
- **La torta muestra 5 categorías y agrupa el resto en "Otras"** (3 en la tarjeta del inicio).
- **En la vista por días, los días que aún no llegan no se dibujan**: no son un gasto de cero.
- **Todas las animaciones pasan por `motion()`**, que devuelve duración cero si el teléfono tiene activado
  "quitar animaciones".
- **El fundido entre pestañas anima el contenedor, no cada pestaña**: así el `IndexedStack` conserva el estado
  de las cinco.

### Lo que cambió frente al plan

- **No se añadió el deslizar-para-borrar en la lista de movimientos.** Los gastos se borran desde su
  formulario, con confirmación; un gesto de borrado en la lista sería una segunda forma de hacer lo mismo y
  más fácil de disparar por error.
- **El botón "Registrar" no necesitó animación propia**: `Scaffold` ya lo escala al aparecer y desaparecer.
- **El resumen mensual (Wrapped) quedó igual**: sus cifras mezclan montos, porcentajes y textos, y no encajan
  en `AnimatedMoney`.

### Problemas encontrados

- Con ~2 GB libres, `flutter analyze` y `flutter test` mueren sin mensaje útil ("analysis server exited",
  "Connection closed before test suite loaded"). No es un fallo del código: `flutter test -j 1` pasa.
- La tarjeta "Esta semana" empuja el check-in por debajo de la primera pantalla en teléfonos bajos. Si
  molesta, basta con intercambiar el orden de las dos tarjetas en `home_screen.dart`.

## 8. Rediseño "Bento suave"

Plan aprobado el 12 de octubre de 2026. Estado: `flutter analyze` limpio y 33 tests en verde. **Revisado solo
con capturas generadas** (`flutter test tool/screenshots_test.dart`), no en el teléfono: estaba bloqueado con
PIN durante la sesión. Falta ver en un dispositivo real las animaciones, la vibración y los emojis.

### Qué cambió

- **Sistema de diseño** en `mobile/lib/core/`: `AppTokens` (acentos por zona: coach lavanda, metas ámbar,
  retos coral, ingresos azul), tipografía Plus Jakarta Sans empaquetada, y las piezas `BentoTile`, `BentoRow`,
  `ProgressRing`, `PillTabs`, `IconBadge`. Animaciones nuevas en `motion.dart`: `Pressable`, `AnimatedCount`,
  `Shimmer`, `ConfettiBurst`, `Breathing`.
- **Inicio** en mosaico: disponible por día con anillo de días, gastado/ingresos/apartado, semana, check-in,
  coach, meta y reto.
- **Coach con presencia**: `CoachOrb`, una forma que respira y toma el color del ánimo del check-in de hoy.
  Aparece en el inicio, el chat, el login, la confirmación de un gasto y los reportes.
- **Navegación** flotante, hoja de registrar en mosaico, micrófono con ondas al dictar.
- **Progreso**: anillo de nivel, metas con anillo, retos por pasos, insignias como medallones.
- **Movimientos** agrupados por día con su total; formulario con el monto como protagonista y categorías
  en chips de color.
- **Resumen mensual** con un color por página e indicador de puntos.
- Sin dependencias nuevas de código: solo la fuente (licencia OFL, en `mobile/assets/fonts/`).

### Decisiones

- **El bento se usa en pantallas de resumen**, no en listas ni formularios.
- **El check-in y "Esta semana" ocupan el ancho completo**, no media tarjeta como en el boceto: cinco emojis
  con su etiqueta no caben en media pantalla con objetivos táctiles de 48 px, y la dona necesita su leyenda.
- **La dona completa va encima de su leyenda** (antes al lado): con la fuente nueva los montos no cabían.
- **La cabecera de Progreso se desplaza con el contenido**: fija, no cabía con la letra del teléfono al máximo.
- **Las animaciones en bucle se apagan en las pruebas** (`ambientMotionEnabled`, en
  `test/flutter_test_config.dart`): con ellas `pumpAndSettle` no termina.
- **La barra inferior y las pestañas acotan el tamaño de letra** (1.15× y 1.3×); el resto de la app sigue el
  ajuste del teléfono sin límite.
- **El confeti de una meta cumplida solo sale si se cumple durante la sesión**, no cada vez que se abre la
  pestaña.

### Pendiente

- Revisión visual en teléfono real, en especial la fluidez del coach y del confeti en equipos modestos.
- El selector de categoría del formulario muestra todas las categorías como chips; con muchas categorías
  propias puede ocupar varias filas.

