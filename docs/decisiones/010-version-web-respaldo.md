# ADR-010 · Versión web en Vercel como respaldo de la app Android

- **Estado:** aceptada
- **Fecha:** 2026-11-21
- **Relacionada con:** [ADR-007](007-distribucion-apk.md) (distribución por APK)

## Contexto

La app es Flutter solo para Android y se distribuye como APK ([ADR-007](007-distribucion-apk.md)). Las personas
con iPhone, y quienes quieren usarla desde un computador, no pueden instalar el APK. Una app de iOS exige cuenta
de Apple Developer, Xcode y la revisión de Apple, que no caben en el plazo del piloto.

## Decisión

- Compilar **la misma base de código** para el navegador (`flutter build web`) y publicarla en **Vercel**:
  <https://pay-and-check-seven.vercel.app>. Mismo diseño, mismos textos y mismo backend.
- Ocultar con `kIsWeb` lo que en un navegador no existe:

  | Función | En web |
  |---|---|
  | Foto y galería de recibos (ML Kit) | Oculta: ML Kit no tiene versión web. Mandar la foto al backend rompería la promesa de privacidad «la foto no sale de tu teléfono» |
  | Captura de SMS y notificaciones del banco | Oculta: ningún navegador puede leerlas. Notificaciones queda solo con los gastos fijos por pagar |
  | Recordatorios (check-in y gastos fijos) | Ocultos: no hay notificaciones locales |
  | Widget y «Abrir Nequi/Daviplata» | No aplican (canal nativo; fallan en silencio) |
  | Dictado por voz | Disponible; bien en Chrome, irregular en Safari |
  | Google Sign-In | Con el **botón oficial de Google** (`google_sign_in_web`, import condicional en `features/auth/google_button/`): el navegador no deja abrir el selector desde un botón propio |

- **Diseño adaptable** (`lib/core/responsive.dart`), según el ancho y no la plataforma: menos de 600 px es la app
  de siempre; desde 600 px las pestañas pasan a un riel lateral, Inicio se reparte en dos columnas y las
  pantallas que se abren encima se centran.
- Vercel no compila Flutter: se compila en GitHub Actions (`web-deploy.yml`) y se suben los archivos
  estáticos. Ver [despliegue.md](../despliegue.md#versión-web-en-vercel).

## Alternativas consideradas

- **App de iOS nativa (TestFlight).** Exige cuenta de Apple (US$99 al año), un Mac y revisión de Apple. Fuera del
  plazo.
- **Una web aparte (React).** Duplica pantallas y reglas. La web de Flutter reutiliza todo.
- **OCR en el navegador (Tesseract.js) o en el backend.** El primero es lento y menos preciso que ML Kit; el
  segundo saca la foto del teléfono. Se prefirió ocultar la función.
- **Servir la web desde el backend.** Vercel da HTTPS, CDN y despliegues inmediatos sin cargar la instancia.

## Consecuencias

- El backend debe estar en **HTTPS** (contenido mixto) y tener el dominio de Vercel en `CORS_ORIGINS`.
- El cliente OAuth web necesita el dominio de Vercel en *Orígenes autorizados de JavaScript*.
- La primera carga baja unos 5 MB (el motor de Flutter). Después queda en caché.
- En web la sesión se guarda en el almacenamiento del navegador (`flutter_secure_storage` web), menos protegido
  que el almacén cifrado de Android. Es aceptable para el piloto (ver [seguridad.md](../seguridad.md)).
- Toda pantalla nueva debe verse bien en los dos anchos. `tool/screenshots_test.dart` saca capturas de celular,
  tableta (1024×768) y PC (1440×900).
- **No se ha probado en un iPhone real** al 21 nov 2026 (pendiente en [pendientes.md](../pendientes.md)).
