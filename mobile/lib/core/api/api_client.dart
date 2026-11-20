import 'package:dio/dio.dart';
import 'package:flutter/foundation.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';

import '../config/app_config.dart';

/// Dónde viven los tokens de sesión. Es una interfaz para poder reemplazarla
/// en tests (el almacén seguro real necesita el sistema operativo).
abstract class TokenStorage {
  Future<({String access, String refresh})?> read();
  Future<void> save(String access, String refresh);
  Future<void> clear();
}

class SecureTokenStorage implements TokenStorage {
  static const _storage = FlutterSecureStorage();
  static const _access = 'access_token';
  static const _refresh = 'refresh_token';

  @override
  Future<({String access, String refresh})?> read() async {
    final access = await _storage.read(key: _access);
    final refresh = await _storage.read(key: _refresh);
    if (access == null || refresh == null) return null;
    return (access: access, refresh: refresh);
  }

  @override
  Future<void> save(String access, String refresh) async {
    await _storage.write(key: _access, value: access);
    await _storage.write(key: _refresh, value: refresh);
  }

  @override
  Future<void> clear() async {
    await _storage.delete(key: _access);
    await _storage.delete(key: _refresh);
  }
}

final tokenStorageProvider = Provider<TokenStorage>((ref) => SecureTokenStorage());

/// Se incrementa cuando el refresh token deja de servir: la sesión terminó.
final sessionExpiredProvider = Provider<ValueNotifier<int>>((ref) {
  final notifier = ValueNotifier(0);
  ref.onDispose(notifier.dispose);
  return notifier;
});

/// Cliente HTTP único de la app, con el token de sesión y su renovación.
final dioProvider = Provider<Dio>((ref) {
  final dio = Dio(
    BaseOptions(
      baseUrl: apiBaseUrl,
      connectTimeout: const Duration(seconds: 10),
      // El backend gratuito puede tardar en "despertar" y la IA en responder.
      receiveTimeout: const Duration(seconds: 45),
    ),
  );
  dio.interceptors.add(
    AuthInterceptor(
      dio: dio,
      storage: ref.watch(tokenStorageProvider),
      onSessionExpired: () => ref.read(sessionExpiredProvider).value++,
    ),
  );
  ref.onDispose(dio.close);
  return dio;
});

/// Agrega el access token a cada petición y, ante un 401, lo renueva una vez
/// con el refresh token y reintenta. `QueuedInterceptor` procesa los errores
/// en fila, así varias peticiones simultáneas no renuevan a la vez.
class AuthInterceptor extends QueuedInterceptor {
  AuthInterceptor({required this.dio, required this.storage, required this.onSessionExpired, Dio? refreshDio})
      : _refreshDio = refreshDio ?? Dio(BaseOptions(baseUrl: dio.options.baseUrl));

  final Dio dio;

  /// Cliente aparte para renovar el token: sin este interceptor, para no entrar en bucle.
  final Dio _refreshDio;
  final TokenStorage storage;
  final VoidCallback onSessionExpired;

  static const _publicas = ['/auth/login', '/auth/register', '/auth/google', '/auth/refresh', '/health'];
  static const _reintentado = 'reintentado';

  bool _esPublica(RequestOptions options) => _publicas.any(options.path.startsWith);

  @override
  Future<void> onRequest(RequestOptions options, RequestInterceptorHandler handler) async {
    if (!_esPublica(options)) {
      final tokens = await storage.read();
      if (tokens != null) options.headers['Authorization'] = 'Bearer ${tokens.access}';
    }
    handler.next(options);
  }

  @override
  Future<void> onError(DioException err, ErrorInterceptorHandler handler) async {
    final options = err.requestOptions;
    final renovable =
        err.response?.statusCode == 401 && !_esPublica(options) && options.extra[_reintentado] != true;
    if (!renovable) return handler.next(err);

    final tokens = await storage.read();
    if (tokens == null) {
      onSessionExpired();
      return handler.next(err);
    }

    try {
      final respuesta = await _refreshDio.post<Map<String, dynamic>>(
        '/auth/refresh',
        data: {'refresh_token': tokens.refresh},
      );
      final nuevos = respuesta.data!;
      await storage.save(nuevos['access_token'] as String, nuevos['refresh_token'] as String);

      options.extra[_reintentado] = true;
      options.headers['Authorization'] = 'Bearer ${nuevos['access_token']}';
      handler.resolve(await dio.fetch<dynamic>(options));
    } on DioException catch (e) {
      if (e.response?.statusCode == 401) {
        await storage.clear();
        onSessionExpired();
      }
      handler.next(err);
    }
  }
}
