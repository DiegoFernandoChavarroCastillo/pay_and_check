import 'dart:convert';
import 'dart:typed_data';

import 'package:dio/dio.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:pay_and_check/core/api/api_client.dart';
import 'package:pay_and_check/core/format.dart';
import 'package:pay_and_check/data/models.dart';
import 'package:pay_and_check/features/sms/sms_inbox_screen.dart';

import 'fakes.dart';

/// Responde según una función y anota las peticiones recibidas.
class FakeAdapter implements HttpClientAdapter {
  FakeAdapter(this.responder);

  final (int, Object) Function(RequestOptions options) responder;
  final peticiones = <RequestOptions>[];

  /// El token con que llegó cada petición. Se copia al recibirla porque el
  /// reintento reutiliza (y modifica) el mismo `RequestOptions`.
  final autorizaciones = <Object?>[];

  @override
  Future<ResponseBody> fetch(RequestOptions options, Stream<Uint8List>? requestStream, Future<void>? cancelFuture) async {
    peticiones.add(options);
    autorizaciones.add(options.headers['Authorization']);
    final (status, body) = responder(options);
    return ResponseBody.fromString(
      jsonEncode(body),
      status,
      headers: {
        Headers.contentTypeHeader: [Headers.jsonContentType],
      },
    );
  }

  @override
  void close({bool force = false}) {}
}

void main() {
  group('formato', () {
    test('money usa punto de miles y sin decimales', () {
      expect(money(14258.06), r'$ 14.258');
      expect(money(0), r'$ 0');
    });

    test('parseMoney entiende lo que la gente escribe', () {
      expect(parseMoney('12.500'), 12500);
      expect(parseMoney(r'$ 5000'), 5000);
      expect(parseMoney('12,5'), 12.5);
      expect(parseMoney(''), isNull);
      expect(parseMoney('0'), isNull);
      expect(parseMoney('abc'), isNull);
    });

    test('isoDate rellena con ceros', () {
      expect(isoDate(DateTime(2026, 3, 7)), '2026-03-07');
    });
  });

  group('modelos', () {
    test('el resumen convierte montos y fechas', () {
      final s = BudgetSummary.fromJson(summaryJson);
      expect(s.disponiblePorDia, 14258.06);
      expect(s.budget.fechaFin, DateTime(2026, 6, 30));
      expect(s.desglose.single.limite, isNull);
    });

    test('el progreso de nivel va de 0 a 1 y se llena en el nivel máximo', () {
      final perfil = GamificationProfile.fromJson(gamificationJson);
      expect(perfil.progresoNivel, 0.4);

      final maximo = GamificationProfile.fromJson({
        ...gamificationJson,
        'nivel': {'numero': 6, 'nombre': 'Leyenda', 'puntos_nivel': 3000, 'puntos_siguiente': null},
      });
      expect(maximo.progresoNivel, 1);
    });
  });

  test('los recordatorios de un gasto fijo caen en sus próximos vencimientos', () {
    RecurringExpense fijo(Map<String, dynamic> extra) => RecurringExpense.fromJson({
          'id': 1, 'category_id': 1, 'monto': '1000', 'descripcion': 'x', 'activo': true, 'dia_semana': 0, ...extra,
        });

    // Semanal, cada lunes. El 11 de marzo de 2026 es miércoles.
    final semanal = fijo({'frecuencia': 'semanal', 'dia_semana': 0});
    expect(semanal.proximosVencimientos(DateTime(2026, 3, 11), 3), [
      DateTime(2026, 3, 16), DateTime(2026, 3, 23), DateTime(2026, 3, 30),
    ]);
    // Si hoy es el día, hoy cuenta.
    expect(semanal.proximosVencimientos(DateTime(2026, 3, 9), 1), [DateTime(2026, 3, 9)]);

    // Mensual, día 5: pasado el 5, el siguiente es el del mes que viene (y cruza de año).
    final mensual = fijo({'frecuencia': 'mensual', 'dia_mes': 5});
    expect(mensual.proximosVencimientos(DateTime(2026, 11, 6), 3), [
      DateTime(2026, 12, 5), DateTime(2027, 1, 5), DateTime(2027, 2, 5),
    ]);

    // Día 31: en los meses más cortos vence el último día.
    final finDeMes = fijo({'frecuencia': 'mensual', 'dia_mes': 31});
    expect(finDeMes.proximosVencimientos(DateTime(2026, 1, 31), 4), [
      DateTime(2026, 1, 31), DateTime(2026, 2, 28), DateTime(2026, 3, 31), DateTime(2026, 4, 30),
    ]);
  });

  test('el filtro de SMS reconoce movimientos bancarios y descarta lo demás', () {
    expect(pareceMovimientoBancario(r'Bancolombia: compra por $45.900 en EXITO 10:32'), isTrue);
    expect(pareceMovimientoBancario('Nequi: Pagaste 12.000 a Juan'), isTrue);
    expect(pareceMovimientoBancario('Tu código de verificación es 482913'), isFalse);
    expect(pareceMovimientoBancario('Hola, ¿nos vemos para la compra del regalo?'), isFalse);
  });

  group('renovación de sesión', () {
    late MemoryTokenStorage storage;
    late int expiradas;

    Dio crear({required FakeAdapter api, required FakeAdapter refresh}) {
      final dio = Dio(BaseOptions(baseUrl: 'http://test'))..httpClientAdapter = api;
      final refreshDio = Dio(BaseOptions(baseUrl: 'http://test'))..httpClientAdapter = refresh;
      dio.interceptors.add(
        AuthInterceptor(dio: dio, storage: storage, onSessionExpired: () => expiradas++, refreshDio: refreshDio),
      );
      return dio;
    }

    setUp(() {
      storage = MemoryTokenStorage((access: 'viejo', refresh: 'r1'));
      expiradas = 0;
    });

    test('ante un 401 renueva el token una vez y repite la petición', () async {
      final api = FakeAdapter(
        (o) => o.headers['Authorization'] == 'Bearer nuevo' ? (200, {'ok': true}) : (401, {'detail': 'expiró'}),
      );
      final refresh = FakeAdapter((o) => (200, {'access_token': 'nuevo', 'refresh_token': 'r2'}));

      final respuesta = await crear(api: api, refresh: refresh).get<Map<String, dynamic>>('/budgets/active');

      expect(respuesta.data, {'ok': true});
      expect(api.autorizaciones, ['Bearer viejo', 'Bearer nuevo']);
      expect(refresh.peticiones.single.data, {'refresh_token': 'r1'});
      expect(storage.tokens, (access: 'nuevo', refresh: 'r2'));
      expect(expiradas, 0);
    });

    test('si el refresh token tampoco sirve, cierra la sesión', () async {
      final api = FakeAdapter((o) => (401, {'detail': 'expiró'}));
      final refresh = FakeAdapter((o) => (401, {'detail': 'refresh inválido'}));

      await expectLater(
        crear(api: api, refresh: refresh).get<dynamic>('/budgets/active'),
        throwsA(isA<DioException>()),
      );
      expect(storage.tokens, isNull);
      expect(expiradas, 1);
      expect(api.peticiones, hasLength(1));
    });

    test('un 401 del login no intenta renovar ni lleva token', () async {
      final api = FakeAdapter((o) => (401, {'detail': 'Credenciales inválidas.'}));
      final refresh = FakeAdapter((o) => (200, <String, dynamic>{}));

      await expectLater(
        crear(api: api, refresh: refresh).post<dynamic>('/auth/login', data: {'email': 'a', 'password': 'b'}),
        throwsA(isA<DioException>()),
      );
      expect(api.peticiones.single.headers.containsKey('Authorization'), isFalse);
      expect(refresh.peticiones, isEmpty);
      expect(storage.tokens, isNotNull);
    });
  });
}
