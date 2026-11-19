import 'package:flutter/services.dart';

/// Funciones de Android que viven en `MainActivity.kt` (mismo canal que la bandeja de SMS): abrir las apps de
/// pago, el widget de la pantalla de inicio y lo que pidió el widget al abrir la app. Fuera de Android (o en las
/// pruebas) todo falla en silencio: son ayudas, nunca bloquean.
class NativeBridge {
  const NativeBridge._();

  static const _channel = MethodChannel('pay_and_check/sms');

  /// Apps de pago instaladas que la app sabe abrir: [(paquete, nombre)].
  static Future<List<(String, String)>> paymentApps() async {
    try {
      final crudos = await _channel.invokeListMethod<Map<Object?, Object?>>('paymentApps') ?? const [];
      return [for (final m in crudos) (m['package'] as String, m['nombre'] as String)];
    } catch (_) {
      return const [];
    }
  }

  static Future<bool> openApp(String paquete) async {
    try {
      return await _channel.invokeMethod<bool>('openApp', {'package': paquete}) ?? false;
    } catch (_) {
      return false;
    }
  }

  /// Escribe en el widget el número del día. Se llama cada vez que carga el resumen.
  static Future<void> updateWidget({required String monto, required String etiqueta, required String detalle}) async {
    try {
      await _channel.invokeMethod<void>('updateWidget', {'monto': monto, 'etiqueta': etiqueta, 'detalle': detalle});
    } catch (_) {}
  }

  /// "registrar" si la app se abrió desde el botón del widget (se lee una sola vez).
  static Future<String?> launchAction() async {
    try {
      return await _channel.invokeMethod<String>('launchAction');
    } catch (_) {
      return null;
    }
  }

  /// Avisa cuando el widget abre la app que ya estaba abierta.
  static void onWidgetAction(void Function(String accion) alRecibir) {
    try {
      _channel.setMethodCallHandler((call) async {
        if (call.method == 'widgetAction' && call.arguments is String) alRecibir(call.arguments as String);
      });
    } catch (_) {}
  }
}
