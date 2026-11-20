/// URL base del backend. Se fija al compilar con
/// `--dart-define=API_BASE_URL=https://...`.
///
/// El valor por defecto apunta al backend local visto desde el emulador de
/// Android (`10.0.2.2` es el `localhost` del PC). En un teléfono físico por
/// USB, `adb reverse tcp:8000 tcp:8000` y `API_BASE_URL=http://localhost:8000`.
const String apiBaseUrl = String.fromEnvironment(
  'API_BASE_URL',
  defaultValue: 'http://10.0.2.2:8000',
);

/// Client ID *web* de Google (el mismo `GOOGLE_CLIENT_ID` del backend). Se
/// fija con `--dart-define=GOOGLE_SERVER_CLIENT_ID=...`. Si está vacío, la
/// app oculta el botón "Continuar con Google".
const String googleServerClientId = String.fromEnvironment('GOOGLE_SERVER_CLIENT_ID');

/// Versión de la política de privacidad que muestra la app. Debe ser la misma
/// `POLITICA_VERSION` del backend (`app/core/config.py`): al cambiar el texto
/// se suben las dos y cada cuenta la vuelve a aceptar al entrar.
const String politicaVersion = '2026-11';

/// Correo para ejercer los derechos sobre los datos (Ley 1581 de 2012). Se fija
/// con `--dart-define=PRIVACY_CONTACT=...`; si está vacío, la política remite a
/// las opciones de Perfil.
const String contactoPrivacidad = String.fromEnvironment('PRIVACY_CONTACT');
