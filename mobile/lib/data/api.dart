import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../core/api/api_client.dart';
import '../core/config/app_config.dart';
import 'models.dart';

final apiProvider = Provider<Api>((ref) => Api(ref.watch(dioProvider)));

typedef Json = Map<String, dynamic>;

/// Todas las llamadas al backend, una por endpoint.
class Api {
  Api(this._dio);

  final Dio _dio;

  Future<Json> _json(Future<Response<dynamic>> llamada) async => (await llamada).data as Json;

  Future<List<T>> _lista<T>(Future<Response<dynamic>> llamada, T Function(Json) f) async =>
      ((await llamada).data as List).map((e) => f(e as Json)).toList();

  // --- Sesión y perfil ---
  Future<Json> login(String email, String password) =>
      _json(_dio.post('/auth/login', data: {'email': email, 'password': password}));

  /// Solo se llama con la casilla de la política marcada: el backend responde 422 sin ella.
  Future<void> register(String nombre, String email, String password, {String? idioma}) => _dio.post(
        '/auth/register',
        data: {
          'nombre': nombre,
          'email': email,
          'password': password,
          'idioma': ?idioma,
          'acepta_politica': true,
          'politica_version': politicaVersion,
        },
      );

  Future<User> acceptPolicy() async => User.fromJson(
        await _json(_dio.put('/auth/me/consent', data: {'politica_version': politicaVersion})),
      );

  Future<User> setSmsConsent(bool acepta) async =>
      User.fromJson(await _json(_dio.put('/auth/me/consent/sms', data: {'acepta': acepta})));

  Future<Json> loginWithGoogle(String idToken) => _json(_dio.post('/auth/google', data: {'id_token': idToken}));

  Future<User> me() async => User.fromJson(await _json(_dio.get('/auth/me')));

  Future<User> updateMe(Json cambios) async => User.fromJson(await _json(_dio.patch('/auth/me', data: cambios)));

  Future<void> deleteMe() => _dio.delete('/auth/me');

  Future<List<Plan>> plans() => _lista(_dio.get('/plans'), Plan.fromJson);

  Future<Subscription> subscription() async => Subscription.fromJson(await _json(_dio.get('/me/subscription')));

  /// Cambio simulado: no hay pasarela de pago (docs/planes.md, D1).
  Future<Subscription> changePlan(String plan) async =>
      Subscription.fromJson(await _json(_dio.put('/me/subscription', data: {'plan': plan})));

  /// Código de convenio (activa Institucional) o código familiar.
  Future<Subscription> redeemCode(String codigo) async =>
      Subscription.fromJson(await _json(_dio.post('/me/subscription/redeem', data: {'codigo': codigo})));

  // --- Presupuesto ---
  /// `null` si el usuario no tiene un presupuesto que cubra hoy.
  Future<BudgetSummary?> activeSummary() async {
    try {
      return BudgetSummary.fromJson(await _json(_dio.get('/budgets/active/summary')));
    } on DioException catch (e) {
      if (e.response?.statusCode == 404) return null;
      rethrow;
    }
  }

  Future<void> createBudget(double monto, DateTime inicio, DateTime fin) => _dio.post(
        '/budgets',
        data: {'monto_total': monto, 'fecha_inicio': isoDate(inicio), 'fecha_fin': isoDate(fin)},
      );

  Future<void> updateBudget(int id, double monto, DateTime inicio, DateTime fin) => _dio.patch(
        '/budgets/$id',
        data: {'monto_total': monto, 'fecha_inicio': isoDate(inicio), 'fecha_fin': isoDate(fin)},
      );

  // --- Categorías ---
  Future<AffordCheck> simulate(double monto) async =>
      AffordCheck.fromJson(await _json(_dio.post('/budgets/active/simulate', data: {'monto': monto})));

  Future<CreditCheck> simulateCredit(double monto, int cuotas, double tasaEa) async => CreditCheck.fromJson(
        await _json(_dio.post('/budgets/simulate-credit', data: {'monto': monto, 'cuotas': cuotas, 'tasa_ea': tasaEa})),
      );

  // --- Apoyos de la universidad, gastos previstos, vacas, gastos repetidos y familia ---
  Future<SupportList> support() async => SupportList.fromJson(await _json(_dio.get('/support')));

  Future<void> supportInterest(int id) => _dio.post('/support/$id/interest');

  Future<List<PlannedExpense>> planned() => _lista(_dio.get('/planned-expenses'), PlannedExpense.fromJson);

  Future<void> createPlanned(String descripcion, double monto, DateTime fecha) => _dio.post(
        '/planned-expenses',
        data: {'descripcion': descripcion, 'monto': monto, 'fecha': isoDate(fecha)},
      );

  Future<void> plannedDone(int id) => _dio.post('/planned-expenses/$id/done');

  Future<void> deletePlanned(int id) => _dio.delete('/planned-expenses/$id');

  /// Una vaca: registra la parte propia y deja la de los demás por cobrar. Devuelve el id del gasto creado.
  Future<int> splitExpense(Json datos) async => (await _json(_dio.post('/expenses/split', data: datos)))['expense_id'] as int;

  Future<ReceivableSummary> receivables() async => ReceivableSummary.fromJson(await _json(_dio.get('/receivables')));

  Future<void> receivablePaid(int id) => _dio.post('/receivables/$id/paid');

  Future<List<RepeatedSpend>> repeated() => _lista(_dio.get('/reports/repeated'), RepeatedSpend.fromJson);

  Future<void> shareProgress(bool comparte) =>
      _dio.put('/me/subscription/share-progress', data: {'comparte': comparte});

  Future<List<FamilyMemberProgress>> familyProgress() =>
      _lista(_dio.get('/me/family/progress'), FamilyMemberProgress.fromJson);

  Future<List<Category>> categories() => _lista(_dio.get('/categories'), Category.fromJson);

  Future<void> createCategory(String nombre, String tipo, double? limite) =>
      _dio.post('/categories', data: {'nombre': nombre, 'tipo': tipo, 'limite': limite});

  Future<void> updateCategory(int id, Json cambios) => _dio.patch('/categories/$id', data: cambios);

  // --- Gastos e ingresos ---
  Future<List<Expense>> expenses({int? categoryId}) => _lista(
        _dio.get('/expenses', queryParameters: {'category_id': ?categoryId}),
        Expense.fromJson,
      );

  Future<Expense> createExpense(Json datos) async => Expense.fromJson(await _json(_dio.post('/expenses', data: datos)));

  Future<void> updateExpense(int id, Json datos) => _dio.patch('/expenses/$id', data: datos);

  Future<void> deleteExpense(int id) => _dio.delete('/expenses/$id');

  Future<ExpenseDraft> parseText(String texto, {required String source}) async => ExpenseDraft.fromParse(
        await _json(_dio.post('/expenses/parse', data: {'texto': texto})),
        source: source,
        textoOriginal: texto,
      );

  Future<ExpenseDraft> parseReceipt(String textoOcr) async => ExpenseDraft.fromParse(
        await _json(_dio.post('/expenses/parse-receipt', data: {'texto_ocr': textoOcr})),
        source: 'ocr',
        textoOriginal: textoOcr,
      );

  Future<List<Income>> incomes() => _lista(_dio.get('/incomes'), Income.fromJson);

  Future<void> createIncome(double monto, String descripcion, DateTime fecha) =>
      _dio.post('/incomes', data: {'monto': monto, 'descripcion': descripcion, 'fecha': isoDate(fecha)});

  Future<void> deleteIncome(int id) => _dio.delete('/incomes/$id');

  Future<List<RecurringExpense>> recurring() => _lista(_dio.get('/recurring-expenses'), RecurringExpense.fromJson);

  /// Semanal con [diaSemana] (0 = lunes) o mensual con [diaMes] (1 a 31).
  Future<void> createRecurring(double monto, String descripcion, int categoryId, {int? diaSemana, int? diaMes}) =>
      _dio.post(
        '/recurring-expenses',
        data: {
          'monto': monto,
          'descripcion': descripcion,
          'category_id': categoryId,
          'frecuencia': diaMes == null ? 'semanal' : 'mensual',
          'dia_semana': ?diaSemana,
          'dia_mes': ?diaMes,
        },
      );

  Future<List<PendingPayment>> pendingPayments() =>
      _lista(_dio.get('/recurring-expenses/pending'), PendingPayment.fromJson);

  /// "Ya lo pagué": registra el gasto y lo descuenta del disponible.
  Future<Expense> payRecurring(int id) async =>
      Expense.fromJson(await _json(_dio.post('/recurring-expenses/$id/pay')));

  /// Salta este vencimiento sin registrar gasto.
  Future<void> skipRecurring(int id) => _dio.post('/recurring-expenses/$id/skip');

  Future<void> setRecurringActive(int id, bool activo) =>
      _dio.patch('/recurring-expenses/$id', data: {'activo': activo});

  Future<void> deleteRecurring(int id) => _dio.delete('/recurring-expenses/$id');

  // --- Coach ---
  Future<List<Checkin>> checkins() => _lista(_dio.get('/checkins'), Checkin.fromJson);

  Future<void> checkin(String animo, {String? nota}) => _dio.post('/checkins', data: {'animo': animo, 'nota': nota});

  Future<String> reaction(int expenseId) async =>
      (await _json(_dio.post('/coach/reaction', data: {'expense_id': expenseId})))['mensaje'] as String;

  Future<List<Insight>> insights({bool refresh = false}) =>
      _lista(_dio.get('/coach/insights', queryParameters: {'refresh': refresh}), Insight.fromJson);

  Future<List<ChatMessage>> chatHistory() => _lista(_dio.get('/coach/chat'), ChatMessage.fromJson);

  Future<ChatMessage> sendChat(String mensaje) async =>
      ChatMessage.fromJson(await _json(_dio.post('/coach/chat', data: {'mensaje': mensaje})));

  // --- Metas, retos y gamificación ---
  Future<List<Goal>> goals() => _lista(_dio.get('/goals'), Goal.fromJson);

  Future<void> createGoal(String nombre, double objetivo, DateTime? limite) => _dio.post(
        '/goals',
        data: {'nombre': nombre, 'monto_objetivo': objetivo, 'fecha_limite': limite == null ? null : isoDate(limite)},
      );

  Future<void> deleteGoal(int id) => _dio.delete('/goals/$id');

  Future<void> contribute(int goalId, double monto) =>
      _dio.post('/goals/$goalId/contributions', data: {'monto': monto});

  Future<void> deleteContribution(int goalId, int id) => _dio.delete('/goals/$goalId/contributions/$id');

  Future<List<Challenge>> challenges() => _lista(_dio.get('/challenges'), Challenge.fromJson);

  Future<List<ChallengeSuggestion>> challengeSuggestions() =>
      _lista(_dio.get('/challenges/suggestions'), ChallengeSuggestion.fromJson);

  Future<void> createChallenge(Json payload) => _dio.post('/challenges', data: payload);

  Future<void> abandonChallenge(int id) => _dio.delete('/challenges/$id');

  Future<GamificationProfile> gamification() async =>
      GamificationProfile.fromJson(await _json(_dio.get('/gamification/profile')));

  // --- Reportes ---
  /// `null` si no hay presupuesto activo sobre el cual reportar.
  Future<WeeklyReport?> weeklyReport() async {
    try {
      return WeeklyReport.fromJson(await _json(_dio.get('/reports/weekly')));
    } on DioException catch (e) {
      if (e.response?.statusCode == 404) return null;
      rethrow;
    }
  }

  Future<Trends> trends({int semanas = 8}) async =>
      Trends.fromJson(await _json(_dio.get('/reports/trends', queryParameters: {'semanas': semanas})));

  Future<Wrapped> wrapped(int anio, int mes) async => Wrapped.fromJson(
        await _json(
          _dio.get('/reports/monthly-wrapped', queryParameters: {'mes': '$anio-${mes.toString().padLeft(2, '0')}'}),
        ),
      );
}
