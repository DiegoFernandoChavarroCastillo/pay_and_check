# Pay & Check — app móvil

App Flutter para Android, con una versión web de respaldo (iPhone y computador), que consume el backend de
`../backend`. El plan de construcción,
fase por fase, está en `../docs/historico/plan-app-movil.md`; el estado actual, los problemas y las decisiones técnicas, en
`../docs/historico/notas-iteracion-app-movil.md`.

## Pantallas

| Pestaña | Qué hay |
|---|---|
| Inicio | Disponible por día, gastado / ingresos / apartado, la semana en una dona, check-in, consejo del coach, meta y reto. Arriba, la racha y la campana de notificaciones |
| Movimientos | Gastos agrupados por día e ingresos; búsqueda y filtro por categoría |
| Coach | Consejos con acción de un toque y chat |
| Progreso | Nivel y puntos, metas, retos (activos, sugeridos e historial) e insignias |
| Perfil | Estilo del coach, recordatorio, presupuesto, categorías y sus límites, gastos fijos, reportes, idioma, apariencia, privacidad y borrado de cuenta |

El botón "Registrar" abre las formas de añadir un movimiento: escribir o dictar, foto de un recibo, galería,
formulario manual e ingreso. La campana abre **Notificaciones**: gastos fijos por pagar y movimientos
detectados en SMS del banco.

## Requisitos

- Flutter 3.47.7 (canal stable) y JDK 17.
- Android SDK con `platform-tools`, la plataforma 36 y build-tools 36.0.0 (`ANDROID_HOME` apuntando a él). Sin
  Android Studio basta con las *command-line tools* y `sdkmanager`.

`flutter doctor` debe marcar en verde "Android toolchain". Chrome solo hace falta para `flutter run -d chrome`
(la versión web se puede compilar sin él); CMake y el canal de Flutter no importan.

## Correr en desarrollo

Primero levantar el backend (ver `../README.md`). La app recibe su configuración al compilar:

| `--dart-define` | Para qué | Por defecto |
|---|---|---|
| `API_BASE_URL` | URL del backend | `http://10.0.2.2:8000` (el `localhost` del PC visto desde el emulador) |
| `GOOGLE_SERVER_CLIENT_ID` | Client ID **web** de Google, el mismo `GOOGLE_CLIENT_ID` del backend | vacío: se oculta "Continuar con Google" |

```bash
# Emulador de Android
flutter run

# Teléfono físico por USB, con depuración USB activada
adb reverse tcp:8000 tcp:8000
flutter run --dart-define=API_BASE_URL=http://localhost:8000

# Contra el backend desplegado
flutter run --dart-define=API_BASE_URL=https://<tu-backend>
```

Mientras `flutter run` está abierto, `r` recarga en caliente y `R` reinicia la app. Un archivo nuevo en
`assets/` (una fuente, por ejemplo) necesita detener y volver a lanzar.

## Verificar

```bash
flutter analyze
flutter test
```

Son 42 tests y no necesitan backend ni teléfono: `test/fakes.dart` trae un backend de mentira (`FakeApi`) y
SMS de mentira (`FakeSmsSource`). Si el PC anda corto de memoria y `flutter test` falla con "Connection closed
before test suite loaded", usa `flutter test -j 1`.

Las animaciones que no terminan nunca (el coach que respira, la racha que late) se apagan en las pruebas
desde `test/flutter_test_config.dart`; con ellas `pumpAndSettle` no acabaría.

## Notificaciones y gastos fijos

No hay servidor de push. Los avisos son notificaciones locales que la app deja programadas en el teléfono
(`lib/core/notifications.dart`):

- **Recordatorio del check-in**: diario, a la hora elegida en Perfil. Es de cada cuenta, no del teléfono.
- **Gastos fijos**: a las 9:00 del día que vencen. Se programan los próximos tres vencimientos de cada gasto
  fijo activo y se reprograman cada vez que cambian o se paga uno (`syncFixedReminders` en
  `features/transactions/manage_screens.dart`). Si la app no se abre en más de tres ciclos, dejan de llegar
  hasta abrirla.

Android puede atrasarlas unos minutos: son inexactas a propósito, para no pedir el permiso de alarmas exactas.
Para ver qué quedó programado:

```bash
adb shell dumpsys alarm | grep -A1 'pay_and_check/com.dexterous'
```

## Probar la lectura de SMS sin SIM

La app lee la bandeja del teléfono (permiso `READ_SMS`, pedido al abrir Notificaciones) y muestra los SMS de
los últimos 14 días que mencionen un monto y una palabra de transacción (`pareceMovimientoBancario` en
`features/sms/sms_inbox_screen.dart`). Para insertar un SMS de prueba con el teléfono por USB:

```bash
adb shell cmd appops set com.android.shell WRITE_SMS allow

adb shell "content insert --uri content://sms/inbox \
  --bind address:s:Nequi \
  --bind body:s:'Nequi: Pagaste 12.000 a Juan' \
  --bind date:l:$(date +%s)000 --bind read:i:0"

adb shell cmd appops set com.android.shell WRITE_SMS ignore
```

Sin la primera línea Android descarta el mensaje en silencio; la última devuelve el permiso a como estaba.
Después, refrescar en Notificaciones. Los SMS ya revisados se recuerdan por cuenta.

## Diseño

La app usa un estilo de mosaico ("bento"): tarjetas de distinto tamaño con esquinas amplias. Las piezas
comunes están en `lib/core/`:

- `theme.dart`: colores, tipografía (Plus Jakarta Sans, en `assets/fonts/`) y `AppTokens`, con el acento de
  cada zona (`context.tokens.coach`, `.goals`, `.challenges`, `.income`).
- `widgets.dart`: `BentoTile`, `BentoRow` (se apila sola en pantallas angostas o con letra grande),
  `ProgressRing`, `PillTabs`.
- `motion.dart`: animaciones. Todas pasan por `motion()` para respetar "quitar animaciones" del teléfono.

Para ver todas las pantallas sin teléfono, en claro, oscuro y con letra grande:

```bash
flutter test tool/screenshots_test.dart   # deja los PNG en build/screenshots/
```

Usa datos de mentira; los emojis salen como recuadros porque el entorno de pruebas no trae esa fuente.

## Textos y traducciones

Los textos viven en `lib/l10n/app_es.arb` (plantilla) y `lib/l10n/app_en.arb`. Edítalos ahí, con la misma clave
en los dos archivos, y regenera las clases:

```bash
flutter gen-l10n         # regenera lib/l10n/gen/ (no se versiona)
```

> **No ejecutes `tool/gen_arb.py`.** Fue la tabla original, pero quedó desactualizada: desde noviembre de 2026 más
> de 180 claves solo existen en los `.arb`, y el script las borraría.

## Generar un APK

```bash
flutter build apk --release --target-platform android-arm,android-arm64 --dart-define=API_BASE_URL=https://<tu-backend>
```

El APK queda en `build/app/outputs/flutter-apk/app-release.apk` y se instala con `adb install` o copiándolo
al teléfono.

**Firma.** Si existe `android/key.properties` (fuera de git), el APK se firma con ese keystore; si no, con la
llave de depuración, que solo sirve para probar en tu propio teléfono. El keystore de esta app es
`android/upload-keystore.jks`: **guarda una copia de ese archivo y de `key.properties` fuera del PC**. Si se
pierden, las personas que ya instalaron la app tendrán que desinstalarla para poder actualizar.

> La app se ha probado en un teléfono (Moto G6, Android 9) en modo depuración con `flutter run`. El build de
> **release** todavía no se ha completado en un PC de 12 GB de RAM; ver `../docs/historico/notas-iteracion-app-movil.md`.

**Si el build muere por memoria** ("Out of Memory" / "Exhausted heap space"): cierra Docker Desktop y
detén los procesos de Gradle que hayan quedado (`cd android && ./gradlew --stop`) antes de reintentar.

### Publicar una versión para probadores

`.github/workflows/mobile-release.yml` compila el APK firmado y lo adjunta a un GitHub Release al empujar un
tag `v*`:

```bash
git tag v0.1.0 && git push origin v0.1.0
```

Antes hay que cargar en GitHub (Settings → Secrets and variables → Actions):

- Secretos `ANDROID_KEYSTORE_BASE64` (`base64 -w0 android/upload-keystore.jks`), `ANDROID_KEYSTORE_PASSWORD`,
  `ANDROID_KEY_ALIAS` y `ANDROID_KEY_PASSWORD` (los tres últimos están en `android/key.properties`).
- Variables `API_BASE_URL` y, si hay login con Google, `GOOGLE_SERVER_CLIENT_ID`.

## Versión web (Vercel)

La misma app compilada para el navegador, para quien no tiene Android (los iPhone del jurado, por ejemplo). En
un iPhone, Safari → Compartir → "Agregar a pantalla de inicio" la abre a pantalla completa con el ícono. En un
computador se ve como una columna del ancho de un celular (`WebFrame` en `lib/app.dart`).

Lo que solo existe en Android se oculta con `kIsWeb`: foto y galería de recibos (ML Kit), captura de SMS y
notificaciones del banco, recordatorios (notificaciones locales), widget y botones para abrir Nequi/Daviplata.
Notificaciones queda solo con los gastos fijos por pagar.

**Google en web.** El navegador no deja abrir el selector de cuentas desde un botón propio: se muestra el botón
oficial de Google (`features/auth/google_button/`, importado de forma condicional porque no compila para
Android) y la sesión llega por `GoogleSignIn.instance.authenticationEvents`. Usa `--dart-define=GOOGLE_WEB_CLIENT_ID`
(por defecto, `GOOGLE_SERVER_CLIENT_ID`): ese cliente OAuth *web* debe tener el dominio de la web en "Orígenes
autorizados de JavaScript", y su ID debe estar en `GOOGLE_CLIENT_ID` del backend, que acepta varios separados por
coma. El dictado por voz depende del navegador: bien en Chrome, irregular en Safari.

```bash
flutter build web --release --dart-define=API_BASE_URL=https://pay-and-check-api.onrender.com
cd build/web && python3 -m http.server 5173   # probar en http://localhost:5173
```

El backend tiene que estar en **HTTPS** (el navegador bloquea llamadas `http://` desde una página `https://`) y
tener el dominio de la web en `CORS_ORIGINS`. El puerto 5173 sirve para probar en local porque ya está en
`CORS_ORIGINS` por defecto.

**Despliegue.** `.github/workflows/web-deploy.yml` compila y publica en Vercel en cada push a `main` que toque
`mobile/` (o a mano, desde Actions → Web deploy → Run workflow). Necesita el secreto `VERCEL_TOKEN` y las
variables `VERCEL_ORG_ID` y `VERCEL_PROJECT_ID`; `WEB_API_BASE_URL` es opcional (por defecto, Render). El
`vercel.json` vive en `web/` para que `flutter build web` lo copie junto a la app.

## Login con Google

En Google Cloud Console hacen falta dos credenciales OAuth del mismo proyecto:

1. **Aplicación web**: su Client ID va en `GOOGLE_CLIENT_ID` (backend) y en `GOOGLE_SERVER_CLIENT_ID` (app).
2. **Android**: paquete `com.diegochavarro.pay_and_check` y la huella SHA-1 del keystore
   (`keytool -list -v -keystore android/upload-keystore.jks`). No se copia a ningún lado: Google la usa para
   reconocer la app.

## Estructura

```
lib/
├── main.dart, app.dart   # arranque, rutas y sesión
├── core/                 # configuración, cliente HTTP con renovación de sesión, tema, formato, avisos,
│                         # gráficas (charts.dart) y animaciones (motion.dart)
├── data/                 # modelos, llamadas a la API, sesión y providers de datos
├── l10n/                 # textos en español e inglés
└── features/             # una carpeta por funcionalidad
    ├── auth/  shell/  home/  budget/
    ├── transactions/     # movimientos, registro por texto/voz/recibo, categorías, gastos fijos
    ├── coach/            # check-in, consejos accionables y chat
    ├── progress/         # metas, retos, insignias y nivel
    ├── reports/          # análisis con gráficas, reporte semanal y resumen mensual
    ├── profile/          # ajustes, privacidad y borrado de cuenta
    └── sms/              # Notificaciones: pagos fijos por hacer y SMS bancarios por revisar
                          # (lectura de SMS por canal nativo en MainActivity.kt)
test/                     # pruebas; fakes.dart es el backend de mentira
tool/
├── gen_arb.py            # textos en español e inglés
└── screenshots_test.dart # capturas de las pantallas con datos de mentira
```
