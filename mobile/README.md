# Pay & Check — app móvil

App Flutter (solo Android por ahora) que consume el backend de `../backend`. El plan de construcción,
fase por fase, está en `../plan-app-movil.md`; los problemas y decisiones técnicas de la última iteración,
en `../notas-iteracion-app-movil.md`.

## Requisitos

- Flutter 3.47 (canal stable) y JDK 17.
- Android SDK con `platform-tools` (`ANDROID_HOME` apuntando a él).

`flutter doctor` debe marcar en verde "Flutter" y "Android toolchain".

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

## Verificar

```bash
flutter analyze
flutter test
```

Los tests no necesitan backend ni teléfono: `test/fakes.dart` trae un backend de mentira (`FakeApi`).
Si el PC anda corto de memoria y `flutter test` falla con "Connection closed before test suite loaded", usa
`flutter test -j 1`.

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

Todos los textos (español e inglés) viven en una sola tabla en `tool/gen_arb.py`. Tras cambiarla:

```bash
python tool/gen_arb.py   # regenera lib/l10n/app_es.arb y app_en.arb
flutter gen-l10n         # regenera lib/l10n/gen/ (no se versiona)
```

## Generar un APK

```bash
flutter build apk --release --dart-define=API_BASE_URL=https://<tu-backend>
```

El APK queda en `build/app/outputs/flutter-apk/app-release.apk` y se instala con `adb install` o copiándolo
al teléfono.

**Firma.** Si existe `android/key.properties` (fuera de git), el APK se firma con ese keystore; si no, con la
llave de depuración, que solo sirve para probar en tu propio teléfono. El keystore de esta app es
`android/upload-keystore.jks`: **guarda una copia de ese archivo y de `key.properties` fuera del PC**. Si se
pierden, las personas que ya instalaron la app tendrán que desinstalarla para poder actualizar.

> A la fecha de este README el build de release aún no se ha completado en este PC (12 GB de RAM); ver
> `../notas-iteracion-app-movil.md`.

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
    └── sms/              # bandeja de SMS bancarios (canal nativo en MainActivity.kt)
```
