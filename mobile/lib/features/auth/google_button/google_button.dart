/// Botón oficial de "Continuar con Google" en la versión web. En Android no existe (la app usa su propio botón
/// y el selector nativo), por eso se importa de forma condicional: el paquete web no compila para Android.
library;

export 'google_button_stub.dart' if (dart.library.js_interop) 'google_button_web.dart';
