# Notas de las iteraciones — app móvil

Última actualización: 13 de octubre de 2026. Este documento recoge el estado real del proyecto, lo que falta,
y los bugs, problemas y decisiones técnicas de cada iteración. El avance tarea por tarea está en
`plan-app-movil.md`.

Las secciones 3 a 7 son de la primera iteración (11 de octubre, en otro PC con Windows, sin teléfono ni
clave de Groq). Se conservan como historia; donde algo cambió después, se indica ahí mismo. Las secciones 8 y
9 son de la iteración del 12 y 13 de octubre.

## 1. Estado en una página

| Qué | Estado | Cómo se comprobó |
|---|---|---|
| Backend | Hecho | 108 tests de `pytest` en verde y `ruff` limpio. Todas las migraciones (hasta `d2b8c6e19f74`) aplicadas en el Postgres de Docker local |
| App Flutter | Hecha y **probada en un teléfono** | `flutter analyze` sin avisos y 42 tests. Recorrida en un Moto G6 (Android 9) en modo depuración con `flutter run`, contra el backend local |
| Coach e IA reales | Probados | Con una `GROQ_API_KEY` del plan gratuito: registro por texto y voz, SMS, consejos, chat, reacción y reporte semanal |
| Historia de usuario completa | Hecha | Cuenta de prueba "Juan" (universitario, presupuesto de 1.000.000): registro, tres semanas de movimientos, retos, metas, SMS y gastos fijos. Detalle en la sección 9 |
| APK de release firmado | **No generado** | Nunca se ha completado un build de release. En este PC además no está el keystore (quedó en el PC anterior) |
| Login con Google | **Sin probar** | Falta crear el Client ID (requiere tu cuenta de Google) |
| Backend desplegado | **Pendiente** | Requiere tus cuentas de Render y Neon; `render.yaml` está listo |
| Código en el repositorio remoto | **Pendiente** | Todo lo de esta iteración está en la rama local `feature/bento-ui`, sin push ni PR hacia `develop` |

Lo que **no** se ha visto en el teléfono: la foto de un recibo, el login con Google, una notificación llegando
(las alarmas quedan programadas en Android, pero todas caen a las 9:00 de días futuros), el modo oscuro, la app
en inglés y el borrado de cuenta. El modo oscuro y la letra grande sí están revisados en capturas generadas.

## 2. Lo que falta

**Para dejar el trabajo a salvo**

1. **Subir la rama.** `git push -u origin feature/bento-ui` y abrir el PR hacia `develop`.
2. **Recuperar el keystore** del PC anterior: `mobile/android/upload-keystore.jks` y
   `mobile/android/key.properties`. Están fuera de git a propósito. Sin ellos un APK se firma con la llave de
   depuración, que solo sirve para pruebas propias; y si se pierden, quien ya tenga la app instalada no podrá
   actualizarla sin desinstalar. La huella SHA-1 de ese keystore es
   `15:35:88:71:90:8A:1F:88:A3:51:3D:B2:9A:B7:50:1B:34:4C:5A:B9`.

**Para una beta con otras personas**

3. **Desplegar el backend** con `render.yaml` (Render + Neon) y compilar la app con esa URL.
4. **Plan de pago de Groq**, o al menos uno con más cuota: el gratuito limita a 8.000 tokens por minuto y un
   puñado de usuarios a la vez lo agota.
5. **Generar el APK de release**, en un equipo con más memoria o con el workflow `mobile-release.yml`.
6. **Client ID de Google** (web + Android) si se quiere el login con Google. Pasos en `mobile/README.md`.
7. **Una bienvenida** que explique el coach y pida el primer registro, y medir retención (cuántos siguen a los
   7 y 30 días). Es lo que decide si el producto es viable.

**Para publicar en Google Play**

8. **Declarar el permiso de SMS.** Play restringe `READ_SMS`; la política contempla una excepción para apps de
   presupuesto ("SMS-based money management"), sujeta a un formulario con video y a aprobación.
9. **Política de privacidad** y aviso de consentimiento: qué se lee, para qué, y que el texto de los
   movimientos aprobados se envía a Groq.

**Datos de prueba que quedaron**

- En la base local: la cuenta `juan.ramirez@example.com` (contraseña `Juan12345`) con su historia completa.
- En el teléfono de pruebas: varios SMS falsos de "Bancolombia" y "Nequi" en la app Mensajes.

## 3. Bugs encontrados y corregidos

### En el backend que ya existía

- **Gastos fijos duplicados por peticiones simultáneas.** `sync_recurring_expenses` se ejecuta en
  `GET /expenses` y en `GET /budgets/active/summary`. La app pide ambos a la vez al abrir, y las dos
  peticiones podían generar el mismo gasto semanal. Antes no se notaba porque nadie llamaba los dos endpoints
  en paralelo. Se agregó una restricción única `(recurring_expense_id, fecha)` (migración `7f2a9c4e1d05`, que
  además limpia duplicados si los hubiera) y el servicio descarta el segundo intento.
  *Después (13 de octubre): los gastos fijos ya no se generan solos, así que esa sincronización no existe.
  La restricción única se conserva y ahora evita que un pago confirmado dos veces se cobre dos veces.*
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
  *Después: se añadió `fl_chart` para la dona y la tendencia (sección 7).*
- **Capa de datos compartida.** El plan pedía `data/domain/ui` dentro de cada feature. Los modelos, las
  llamadas a la API y los providers quedaron juntos en `mobile/lib/data/`, y cada feature solo tiene sus
  pantallas. Con un backend único y pantallas que comparten casi todos los datos (el dashboard usa los de
  todas), repartirlos por feature habría duplicado código.
- **El onboarding no es una ruta aparte.** Si no hay presupuesto activo, Inicio invita a crearlo y esa
  pantalla pregunta también el estilo del coach.
- **Modelo del coach sin cambiar.** El plan proponía evaluar `openai/gpt-oss-120b`. Sin `GROQ_API_KEY` no se
  pudo evaluar nada, así que el coach usa el mismo modelo que el parseo; es una constante (`COACH_MODEL` en
  `backend/app/services/groq_client.py`). *Después: con clave real el modelo pequeño resultó suficiente si
  redacta con razonamiento `medium`; sigue sin evaluarse el modelo grande.*

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
  *Después: los gastos fijos ya no son automáticos; confirmar uno sí cuenta como registro.*
- **Todo se calcula al consultar, sin tareas programadas.** Igual que los gastos fijos del backend original.
  Consecuencia: un reto vencido se marca como cumplido o fallido la próxima vez que el usuario abre la app.
- **Las categorías por defecto no admiten límite.** Son un registro compartido por todos los usuarios, así
  que el coach solo propone "poner límite" sobre categorías propias; para las demás propone un reto.
  *Después: cada persona puede ponerles su propio límite (tabla `category_limits`) y el coach lo propone para
  cualquier categoría sin límite.*
- **El refresh token no se puede revocar.** Es un JWT sin estado: cerrar sesión lo borra del teléfono, pero
  uno robado serviría hasta expirar (30 días). Revocarlos exige una tabla de tokens; no se hizo.
- **Recibos: la foto no sale del teléfono.** El texto se reconoce con ML Kit en el dispositivo y al backend
  viaja solo el texto. No hay almacenamiento de imágenes.
- **SMS: lectura bajo demanda.** No hay servicio en segundo plano: la app lee los SMS de los últimos 14 días
  cuando abres esa pantalla, muestra los que parecen movimientos bancarios y nada se envía hasta que eliges
  registrar uno. El filtro es por palabras clave y no se ha probado con SMS reales de bancos colombianos.
  *Después: la bandeja pasó a ser el apartado Notificaciones, con una campana en el inicio; se lee al abrir
  la app y al volver a ella. Sigue sin haber servicio en segundo plano y sin probarse con SMS reales.*
- **Recordatorio local e inexacto.** El recordatorio del check-in es una notificación programada en el
  teléfono, sin servidor de push, y Android puede atrasarla unos minutos (a cambio no pide el permiso
  especial de alarmas exactas). *Después: los avisos de gastos fijos usan el mismo mecanismo.*
- **Textos en una sola tabla.** Español e inglés están lado a lado en `mobile/tool/gen_arb.py`; de ahí se
  generan los archivos de traducción. Los mensajes de error que vienen del backend siguen solo en español.
- **Nombre e identificador provisionales.** "Pay & Check" y `com.diegochavarro.pay_and_check`. El
  identificador se puede cambiar sin costo hasta que se cree el Client ID Android de Google o se reparta el
  primer APK; después, cambiarlo equivale a publicar otra app.

## 5. Problemas abiertos y limitaciones conocidas

- **Sin sincronización bancaria.** Los movimientos entran a mano, por IA o por SMS. Las finanzas abiertas son
  obligatorias en Colombia desde abril de 2026, pero su implementación va por etapas.
- **Sin notificaciones desde el servidor.** Todos los avisos se programan en el teléfono. Un SMS del banco
  que llega con la app cerrada no avisa: aparece al abrirla.
- **El filtro de SMS no se ha probado con mensajes reales** de bancos colombianos, solo con textos de prueba.
- **La IA se equivoca a veces.** Clasificó un Rappi como transporte antes de afinar el prompt. Por eso todo
  lo que propone pasa por una confirmación con opción de editar.
- **El chat puede proponer montos propios.** Su filtro de cifras reintenta una vez y acepta lo que salga.
- **El resumen mensual y la "mejora mensual" comparan meses**; el primero ya solo compara periodos
  equivalentes, la métrica de Progreso todavía no (y por eso no se muestra cuando es negativa).
- **Un aviso de gasto fijo por cada vencimiento de los próximos tres.** Si la app no se abre en más de tres
  ciclos, dejan de llegar hasta abrirla.
- **El refresh token no se puede revocar** (JWT sin estado, 30 días).
- **Editar el objetivo de un reto no existe**, ni retos de más de 7 días: solo aceptar y abandonar.
- **Ligas, retos colaborativos, Gmail y bancos** siguen fuera, como en el plan.
- **Íconos antiguos en Android 7.** El ícono es adaptativo (Android 8+).
- **Los mensajes de error del backend** llegan solo en español, aunque la app esté en inglés.
- **Solo Android.** No hay versión de iOS.

## 6. Entorno de desarrollo

El proyecto se ha trabajado en dos equipos. La primera iteración, en un PC con Windows; desde el 12 de
octubre, en uno con CachyOS (Linux, 12 GB de RAM) donde se instaló:

- Con `pacman`: `docker`, `docker-compose`, `docker-buildx` y `jdk17-openjdk`.
- En la carpeta personal: Flutter 3.47.7 (`~/flutter`), el Android SDK de línea de comandos (`~/Android/Sdk`,
  con `platform-tools`, plataforma 36 y build-tools 36.0.0) y `uv` (`~/.local/bin`). Las rutas y `ANDROID_HOME`
  quedaron configuradas en fish.

Con 12 GB de RAM, `flutter run`, Docker y los tests a la vez van justos: si algo muere sin mensaje útil, casi
siempre es memoria.

## 7. Iteración de UX: gráficas y animaciones

Plan en `C:\Users\chava\.claude\plans\wobbly-puzzling-kahan.md`. Estado: backend con 92 tests y `ruff` limpio;
app con `flutter analyze` limpio y 26 tests. **No se ha visto corriendo en el emulador** (no había memoria
para levantarlo junto con el build): falta la revisión visual.
*Después: la app ya se vio en un teléfono (sección 9) y este diseño se reemplazó por el de la sección 8; las
gráficas y `motion.dart` se conservan.*

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

Plan aprobado el 12 de octubre de 2026. Se revisó primero con capturas generadas
(`flutter test tool/screenshots_test.dart`) y después en el teléfono, en modo claro: inicio, movimientos,
coach, progreso, perfil, análisis y la hoja de registrar. La fluidez de las animaciones, la vibración y el
confeti no se pueden juzgar en capturas y siguen sin una revisión a ojo.

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

- **La barra inferior flota de verdad**: el contenido de las pestañas pasa por detrás (`extendBody`), y cada
  lista suma ese espacio a su margen (`bottomInset`). Con el teclado abierto se desactiva, para que el campo
  del chat quede justo encima del teclado.

### Pendiente

- Juzgar a ojo la fluidez del coach y del confeti en equipos modestos, y el modo oscuro en el teléfono.
- El selector de categoría del formulario muestra todas las categorías como chips; con muchas categorías
  propias puede ocupar varias filas.

## 9. Iteración del 12 y 13 de octubre: pruebas reales, correcciones y funciones nuevas

Primera vez que la app corrió en un teléfono y con la IA real. Casi todo lo de esta sección salió de usarla.

### Funciones nuevas

- **Ingresos por texto, voz o SMS.** La extracción devuelve el tipo de movimiento. "Recibí un pago de
  200.000 de mis papás" abre el formulario de ingreso ya lleno, en vez de fallar por no ser un gasto.
- **Notificaciones.** Una campana en el inicio cuenta lo pendiente y abre la lista: gastos fijos por pagar y
  movimientos detectados en SMS. "Aprobar" pide a la IA interpretar el SMS y muestra la propuesta en la misma
  tarjeta; "Guardar" lo registra sin cambiar de pantalla, y "Editar" abre el formulario.
- **Gastos fijos semanales o mensuales con recordatorio.** Ya no se registran solos: el día que vencen
  quedan por pagar, avisa una notificación a las 9:00 y "Ya lo pagué" crea el gasto. "Omitir" salta ese
  vencimiento. El día 31 vence el último día en los meses más cortos.
- **Límite propio sobre categorías por defecto.**
- **Más retos e insignias**: de 3 a 6 tipos de reto y de 12 a 23 insignias, cada familia con su ícono.
- **La cuenta nace en el idioma del teléfono**, y el recordatorio y los SMS revisados son de cada cuenta.

### Bugs encontrados y corregidos

- **Registro por IA fallando de forma intermitente** (error 400 `json_validate_failed`). El modo JSON de Groq
  hacía que el modelo devolviera vacío. Se quitó; el JSON se pide en el prompt.
- **"1000,000" se registraba como 1.000.** El dictado escribe así los miles. El prompt ahora aclara que un
  punto o coma seguido de tres dígitos separa miles.
- **El correo distinguía mayúsculas.** El teclado del teléfono capitalizó la primera letra al registrarse y
  después no se podía entrar. Se normaliza en la API, con migración para las cuentas existentes.
- **El coach inventaba cifras** ("9.625×2=19.250, considera reducir 2.000") y le restaba el gasto recién
  registrado a un disponible que ya lo tenía descontado. Nuevo guardrail: un texto con números que no estén
  en el dato de origen se descarta.
- **El reporte semanal recomendó "una inversión de bajo riesgo".** Ese texto no pasaba por las reglas del
  coach. Ahora sí, con un respaldo determinista.
- **Los consejos copiaban el dato literal.** Causado al bajar el razonamiento del modelo a `low` para arreglar
  el registro. Se dejó `low` solo para extraer y `medium` para redactar.
- **Fechas en formato ISO en los consejos** ("se agotará el 2026-10-13"). Ahora van en palabras, también en
  el contexto que recibe la IA.
- **"Ahorro: −2317 %"** en Progreso cuando se gasta mucho más que los ingresos registrados. Se muestra entre
  0 % y 100 %; la mejora mensual negativa tampoco se muestra.
- **El promedio semanal contaba semanas vacías** anteriores al primer gasto.
- **El resumen mensual comparaba meses incompletos** ("43 % más" contra un mes de diez días).
- **El reto "3 días sin gasto opcional" era casi imposible**: todas las categorías por defecto eran
  opcionales y un pasaje de bus rompía el día. Transporte, salud y servicios pasaron a gasto fijo.
- **Rappi clasificado como transporte.** El prompt ahora pide clasificar por lo comprado.
- **En la app**: el chat se desbordaba con el teclado abierto; los avisos se pisaban entre sí (ahora van en
  cola); textos cortados (correo en Perfil, "Confianza" en el check-in, "Autoconocimiento", descripciones de
  ingresos); la última etiqueta de la gráfica de tendencia; tres botones que no cabían en una tarjeta de SMS.

### Decisiones

- **Aprobar un SMS son dos toques, no uno.** Se ve el monto y la categoría que entendió la IA antes de que
  quede registrado.
- **Los gastos fijos esperan confirmación.** Programarlos no es pagarlos; lo que descuenta del disponible es
  confirmar. El gasto queda con la fecha en que vencía.
- **Avisos programados en el teléfono, no enviados desde un servidor.** No requieren infraestructura y llegan
  sin internet. Escuchar los SMS entrantes con la app cerrada se analizó y se descartó por ahora: es poco
  código, pero añade un permiso más y el trámite de Google Play.
- **El filtro de cifras es estricto en consejos, reacción y reporte, y suave en el chat**, donde la persona
  puede pedir una cuenta.
- **Los límites de las categorías por defecto viven en una tabla aparte** (`category_limits`), porque esas
  categorías son un registro compartido.
- **Las insignias no dan puntos** y ninguna depende de montos absolutos.

### La historia de usuario de Juan

Recorrido completo con una cuenta nueva: registro desde el teléfono; presupuesto de 1.000.000 para un mes;
31 gastos, 3 ingresos, una categoría propia con límite, una meta y un gasto fijo cargados por la API con
fechas de las tres semanas anteriores; y, desde el teléfono, check-in, gasto por texto, reto aceptado, chat,
aporte a la meta, SMS aprobado con la categoría corregida y gasto fijo pagado.

Lo que la app no deja fechar en el pasado (19 check-ins y 3 retos de semanas anteriores, y la fecha de
registro) se insertó directamente en la base de datos. El resultado de cada reto lo decidió la lógica real:
dos cumplidos y uno no logrado. Las cifras se cruzaron a mano con la API en cada paso y cuadraron.

### Viabilidad de mercado (resumen)

Análisis rápido, no un estudio formal. El ángulo propio es registrar con poca fricción en el español de aquí,
un solo número claro (disponible por día) y un coach sin culpa con retos verificados. El competidor real no
son otras apps de gastos sino lo que ya trae la billetera o el banco. Lo que falta demostrar es la retención
al mes y que alguien pague; lo razonable es una beta de 30 a 50 personas antes de construir más. Como
segmento, universitarios y jóvenes con su primer ingreso; como ingreso, más probable por instituciones
(universidades, bienestar financiero) que por suscripción directa.

