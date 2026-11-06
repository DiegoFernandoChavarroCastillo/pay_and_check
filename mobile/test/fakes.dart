import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:pay_and_check/app.dart';
import 'package:pay_and_check/core/theme.dart';
import 'package:pay_and_check/core/api/api_client.dart';
import 'package:pay_and_check/core/settings.dart';
import 'package:pay_and_check/data/api.dart';
import 'package:pay_and_check/data/models.dart';
import 'package:pay_and_check/data/session.dart';
import 'package:pay_and_check/features/sms/sms_inbox_screen.dart';
import 'package:pay_and_check/l10n/gen/app_localizations.dart';
import 'package:shared_preferences/shared_preferences.dart';

class MemoryTokenStorage implements TokenStorage {
  MemoryTokenStorage([this.tokens]);

  ({String access, String refresh})? tokens;

  @override
  Future<({String access, String refresh})?> read() async => tokens;

  @override
  Future<void> save(String access, String refresh) async => tokens = (access: access, refresh: refresh);

  @override
  Future<void> clear() async => tokens = null;
}

const userJson = {
  'id': 1,
  'email': 'ana@test.com',
  'nombre': 'Ana Pérez',
  'coach_tone': 'motivador',
  'idioma': 'es',
  'zona_horaria': 'America/Bogota',
};

const summaryJson = {
  'budget': {'id': 1, 'monto_total': '500000.00', 'fecha_inicio': '2026-03-01', 'fecha_fin': '2026-06-30'},
  'gastado_total': '38000.00',
  'ingresos_total': '0.00',
  'apartado_total': '20000.00',
  'disponible_total': '442000.00',
  'dias_restantes': 31,
  'disponible_por_dia': '14258.06',
  'disponible_por_semana': '99806.45',
  'en_riesgo': false,
  'fecha_proyectada_agotamiento': null,
  'desglose_por_categoria': [
    {'categoria': 'entretenimiento', 'tipo': 'opcional', 'gastado': '30000.00', 'limite': null, 'excedido': false},
  ],
};

const gamificationJson = {
  'puntos': 40,
  'nivel': {'numero': 1, 'nombre': 'Aprendiz', 'puntos_nivel': 0, 'puntos_siguiente': 100},
  'racha_actual': 3,
  'mejor_racha': 3,
  'metricas': {'ratio_ahorro': '0.6476', 'consistencia': '1.0000', 'mejora_mensual': null},
  'insignias': [
    {'codigo': 'primer_registro', 'nombre': 'Primer paso', 'descripcion': 'Registraste tu primer gasto.', 'desbloqueada': true},
  ],
  'eventos_recientes': <Map<String, dynamic>>[],
  'nuevos_puntos': 0,
  'nuevas_insignias': <String>[],
};

const insightJson = {
  'tipo': 'fin_de_semana',
  'mensaje': 'Los fines de semana se te va más en entretenimiento.',
  'descripcion': 'Gastas 20.000 por día los fines de semana, frente a 250 entre semana.',
  'datos': <String, dynamic>{},
  'accion': {
    'tipo': 'crear_reto',
    'etiqueta': 'Aceptar reto: 20% menos en entretenimiento',
    'payload': {'plantilla': 'reducir_categoria', 'category_id': 3, 'porcentaje': 20},
  },
};

/// Tres semanas: sin gastos, 40.000 y 60.000 (la actual, repartida en 7 categorías).
final trendsJson = {
  'semanas': [
    {'semana_inicio': '2026-03-02', 'semana_fin': '2026-03-08', 'total': '0.00', 'por_categoria': <dynamic>[]},
    {
      'semana_inicio': '2026-03-09',
      'semana_fin': '2026-03-15',
      'total': '40000.00',
      'por_categoria': [
        {'categoria': 'comida', 'monto': '40000.00'},
      ],
    },
    {
      'semana_inicio': '2026-03-16',
      'semana_fin': '2026-03-22',
      'total': '60000.00',
      'por_categoria': [
        {'categoria': 'comida', 'monto': '24000.00'},
        {'categoria': 'transporte', 'monto': '15000.00'},
        {'categoria': 'entretenimiento', 'monto': '9000.00'},
        {'categoria': 'salud', 'monto': '6000.00'},
        {'categoria': 'ropa', 'monto': '3000.00'},
        {'categoria': 'hogar', 'monto': '1800.00'},
        {'categoria': 'regalos', 'monto': '1200.00'},
      ],
    },
  ],
  'dias': [
    for (var i = 0; i < 14; i++)
      {'fecha': '2026-03-${(9 + i).toString().padLeft(2, '0')}', 'total': i == 0 ? '40000.00' : '0.00'},
  ],
  'promedio_semanal': '33333.33',
  'variacion_vs_semana_anterior_pct': 50,
};

const trendsVacioJson = {
  'semanas': [
    {'semana_inicio': '2026-03-09', 'semana_fin': '2026-03-15', 'total': '0.00', 'por_categoria': <dynamic>[]},
    {'semana_inicio': '2026-03-16', 'semana_fin': '2026-03-22', 'total': '0.00', 'por_categoria': <dynamic>[]},
  ],
  'dias': <dynamic>[],
  'promedio_semanal': '0.00',
  'variacion_vs_semana_anterior_pct': null,
};

/// SMS de mentira: los que haya en [mensajes], con el permiso ya concedido.
class FakeSmsSource extends SmsSource {
  final mensajes = <SmsMessage>[];

  void llega(int id, String remitente, String cuerpo) => mensajes.add(
        SmsMessage.fromMap({'id': id, 'address': remitente, 'body': cuerpo, 'date': DateTime.now().millisecondsSinceEpoch}),
      );

  @override
  Future<bool> hasPermission() async => true;

  @override
  Future<bool> requestPermission() async => true;

  @override
  Future<List<SmsMessage>> read(DateTime desde) async => [...mensajes];
}

/// Backend de mentira: responde con datos fijos y anota lo que la app le envía.
class FakeApi extends Api {
  FakeApi({this.conPresupuesto = true, this.conGastos = true}) : super(Dio());

  bool conPresupuesto;
  bool conGastos;
  final sms = FakeSmsSource();
  final gastosCreados = <Json>[];
  final retosCreados = <Json>[];
  final checkinsHechos = <String>[];

  @override
  Future<Json> login(String email, String password) async {
    if (password != 'secret123') {
      throw DioException(
        requestOptions: RequestOptions(path: '/auth/login'),
        response: Response(
          requestOptions: RequestOptions(path: '/auth/login'),
          statusCode: 401,
          data: {'detail': 'Credenciales inválidas.'},
        ),
      );
    }
    return {'access_token': 'a', 'refresh_token': 'r'};
  }

  @override
  Future<User> me() async => User.fromJson(userJson);

  @override
  Future<BudgetSummary?> activeSummary() async => conPresupuesto ? BudgetSummary.fromJson(summaryJson) : null;

  @override
  Future<List<Category>> categories() async => [
        Category.fromJson({'id': 1, 'nombre': 'comida', 'owner_id': null, 'tipo': 'opcional', 'limite': null}),
        Category.fromJson({'id': 3, 'nombre': 'entretenimiento', 'owner_id': null, 'tipo': 'opcional', 'limite': null}),
      ];

  @override
  Future<List<Expense>> expenses({int? categoryId}) async => [];

  @override
  Future<List<Income>> incomes() async => [];

  final ingresosCreados = <Json>[];
  final categoriasEditadas = <(int, Json)>[];

  @override
  Future<void> updateCategory(int id, Json cambios) async => categoriasEditadas.add((id, cambios));


  @override
  Future<void> createIncome(double monto, String descripcion, DateTime fecha) async =>
      ingresosCreados.add({'monto': monto, 'descripcion': descripcion, 'fecha': isoDate(fecha)});

  /// Lo que "responde la IA" al interpretar un texto.
  Json parseo = {'tipo': 'gasto', 'monto': '5000', 'categoria': 'entretenimiento', 'descripcion': 'helado', 'fecha': '2026-03-10'};

  @override
  Future<ExpenseDraft> parseText(String texto, {required String source}) async =>
      ExpenseDraft.fromParse(parseo, source: source, textoOriginal: texto);

  @override
  Future<List<RecurringExpense>> recurring() async => [];

  /// Gastos fijos por pagar que "tiene" el backend, y lo que la app hizo con ellos.
  final pagosPendientes = <Json>[];
  final pagosConfirmados = <int>[];
  final pagosOmitidos = <int>[];
  final fijosCreados = <Json>[];

  @override
  Future<List<PendingPayment>> pendingPayments() async => pagosPendientes.map(PendingPayment.fromJson).toList();

  @override
  Future<Expense> payRecurring(int id) async {
    pagosConfirmados.add(id);
    final pago = pagosPendientes.firstWhere((p) => p['recurring_id'] == id);
    pagosPendientes.remove(pago);
    return Expense.fromJson({
      'id': 900 + id,
      'category_id': pago['category_id'],
      'monto': pago['monto'],
      'descripcion': pago['descripcion'],
      'source': 'recurrente',
      'comercio': null,
      'fecha': pago['fecha'],
    });
  }

  @override
  Future<void> skipRecurring(int id) async {
    pagosOmitidos.add(id);
    pagosPendientes.removeWhere((p) => p['recurring_id'] == id);
  }

  @override
  Future<void> createRecurring(double monto, String descripcion, int categoryId, {int? diaSemana, int? diaMes}) async =>
      fijosCreados.add({'monto': monto, 'descripcion': descripcion, 'dia_semana': diaSemana, 'dia_mes': diaMes});

  @override
  Future<List<Checkin>> checkins() async => [];

  @override
  Future<void> checkin(String animo, {String? nota}) async => checkinsHechos.add(animo);

  @override
  Future<List<Insight>> insights({bool refresh = false}) async => [Insight.fromJson(insightJson)];

  @override
  Future<List<ChatMessage>> chatHistory() async => [];

  @override
  Future<List<Goal>> goals() async => [];

  @override
  Future<List<Challenge>> challenges() async => [];

  @override
  Future<List<ChallengeSuggestion>> challengeSuggestions() async => [];

  @override
  Future<void> createChallenge(Json payload) async => retosCreados.add(payload);

  @override
  Future<GamificationProfile> gamification() async => GamificationProfile.fromJson(gamificationJson);

  @override
  Future<Expense> createExpense(Json datos) async {
    gastosCreados.add(datos);
    return Expense.fromJson({
      'id': 99,
      'category_id': datos['category_id'],
      'monto': datos['monto'],
      'descripcion': datos['descripcion'],
      'source': datos['source'],
      'comercio': datos['comercio'],
      'fecha': datos['fecha'],
    });
  }

  @override
  Future<String> reaction(int expenseId) async => 'Buen registro.';

  @override
  Future<Trends> trends({int semanas = 8}) async => Trends.fromJson(conGastos ? trendsJson : trendsVacioJson);
}

Future<List<Object>> _overrides(FakeApi api, TokenStorage storage) async {
  SharedPreferences.setMockInitialValues({});
  final prefs = await SharedPreferences.getInstance();
  return [
    apiProvider.overrideWithValue(api),
    tokenStorageProvider.overrideWithValue(storage),
    sharedPreferencesProvider.overrideWithValue(prefs),
    deviceTimezoneProvider.overrideWithValue(() async => null),
    smsSourceProvider.overrideWithValue(api.sms),
  ];
}

/// La app completa contra el backend de mentira.
Future<Widget> appDePrueba(FakeApi api, {bool conSesion = true}) async {
  final storage = MemoryTokenStorage(conSesion ? (access: 'a', refresh: 'r') : null);
  return ProviderScope(
    retry: (_, _) => null,
    overrides: (await _overrides(api, storage)).cast(),
    child: const PayAndCheckApp(),
  );
}

/// Una sola pantalla, con sesión iniciada y textos en español.
Future<Widget> pantallaDePrueba(FakeApi api, Widget pantalla, {bool sinAnimaciones = false}) async {
  final storage = MemoryTokenStorage((access: 'a', refresh: 'r'));
  return ProviderScope(
    retry: (_, _) => null,
    overrides: (await _overrides(api, storage)).cast(),
    child: MaterialApp(
      theme: buildTheme(Brightness.light),
      darkTheme: buildTheme(Brightness.dark),
      locale: const Locale('es'),
      localizationsDelegates: AppLocalizations.localizationsDelegates,
      supportedLocales: AppLocalizations.supportedLocales,
      // Simula el ajuste "quitar animaciones" del teléfono.
      builder: (context, child) => MediaQuery(
        data: MediaQuery.of(context).copyWith(disableAnimations: sinAnimaciones),
        child: child!,
      ),
      home: pantalla,
    ),
  );
}
