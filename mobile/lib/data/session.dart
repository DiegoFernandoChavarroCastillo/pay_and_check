import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_timezone/flutter_timezone.dart';
import 'package:google_sign_in/google_sign_in.dart';

import '../core/api/api_client.dart';
import '../core/config/app_config.dart';
import 'api.dart';
import 'models.dart';

/// Zona horaria IANA del teléfono (ej. "America/Bogota"), o null si no se pudo leer.
final deviceTimezoneProvider = Provider<Future<String?> Function()>((ref) {
  return () async {
    try {
      return (await FlutterTimezone.getLocalTimezone()).identifier;
    } catch (_) {
      return null;
    }
  };
});

/// Usuario con sesión iniciada, o null.
final sessionProvider = AsyncNotifierProvider<SessionController, User?>(SessionController.new);

class SessionController extends AsyncNotifier<User?> {
  Api get _api => ref.read(apiProvider);
  TokenStorage get _storage => ref.read(tokenStorageProvider);
  bool _googleListo = false;

  @override
  Future<User?> build() async {
    final expirada = ref.watch(sessionExpiredProvider);
    void cerrar() => state = const AsyncData(null);
    expirada.addListener(cerrar);
    ref.onDispose(() => expirada.removeListener(cerrar));

    if (await _storage.read() == null) return null;
    try {
      return await _conZonaHorariaDelTelefono(await _api.me());
    } on DioException catch (e) {
      // Token inválido: sin sesión. Cualquier otro error (sin red) se propaga
      // para que la app ofrezca reintentar en vez de cerrar la sesión.
      if (e.response?.statusCode == 401) return null;
      rethrow;
    }
  }

  /// El backend calcula "hoy" con la zona horaria del usuario: se mantiene
  /// igual a la del teléfono.
  Future<User> _conZonaHorariaDelTelefono(User user) async {
    final zona = await ref.read(deviceTimezoneProvider)();
    if (zona == null || zona == user.zonaHoraria) return user;
    try {
      return await _api.updateMe({'zona_horaria': zona});
    } on DioException {
      return user;
    }
  }

  Future<void> _entrar(Map<String, dynamic> tokens) async {
    await _storage.save(tokens['access_token'] as String, tokens['refresh_token'] as String);
    state = AsyncData(await _conZonaHorariaDelTelefono(await _api.me()));
  }

  Future<void> login(String email, String password) async => _entrar(await _api.login(email, password));

  Future<void> register(String nombre, String email, String password) async {
    await _api.register(nombre, email, password);
    await login(email, password);
  }

  /// Devuelve false si el usuario canceló el selector de cuentas.
  Future<bool> loginWithGoogle() async {
    final google = GoogleSignIn.instance;
    if (!_googleListo) {
      await google.initialize(serverClientId: googleServerClientId);
      _googleListo = true;
    }
    final GoogleSignInAccount cuenta;
    try {
      cuenta = await google.authenticate();
    } on GoogleSignInException catch (e) {
      if (e.code == GoogleSignInExceptionCode.canceled) return false;
      rethrow;
    }
    final idToken = cuenta.authentication.idToken;
    if (idToken == null) throw StateError('Google no devolvió un id_token.');
    await _entrar(await _api.loginWithGoogle(idToken));
    return true;
  }

  Future<void> updateProfile(Map<String, dynamic> cambios) async {
    state = AsyncData(await _api.updateMe(cambios));
  }

  Future<void> logout() async {
    await _storage.clear();
    if (_googleListo) {
      try {
        await GoogleSignIn.instance.signOut();
      } catch (_) {}
    }
    state = const AsyncData(null);
  }

  Future<void> deleteAccount() async {
    await _api.deleteMe();
    await logout();
  }
}
