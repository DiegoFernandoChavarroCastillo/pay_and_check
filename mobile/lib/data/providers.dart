import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'api.dart';
import 'models.dart';
import 'session.dart';

/// Hace que un provider de datos se recalcule al cambiar de usuario, para que
/// nunca queden a la vista datos de la sesión anterior.
Api _api(Ref ref) {
  ref.watch(sessionProvider.select((s) => s.value?.id));
  return ref.watch(apiProvider);
}

final summaryProvider = FutureProvider<BudgetSummary?>((ref) => _api(ref).activeSummary());
final categoriesProvider = FutureProvider<List<Category>>((ref) => _api(ref).categories());
final expensesProvider = FutureProvider<List<Expense>>((ref) => _api(ref).expenses());
final incomesProvider = FutureProvider<List<Income>>((ref) => _api(ref).incomes());
final recurringProvider = FutureProvider<List<RecurringExpense>>((ref) => _api(ref).recurring());
final pendingPaymentsProvider = FutureProvider<List<PendingPayment>>((ref) => _api(ref).pendingPayments());
final checkinsProvider = FutureProvider<List<Checkin>>((ref) => _api(ref).checkins());
final insightsProvider = FutureProvider<List<Insight>>((ref) => _api(ref).insights());
final goalsProvider = FutureProvider<List<Goal>>((ref) => _api(ref).goals());
final challengesProvider = FutureProvider<List<Challenge>>((ref) => _api(ref).challenges());
final suggestionsProvider = FutureProvider<List<ChallengeSuggestion>>((ref) => _api(ref).challengeSuggestions());
final gamificationProvider = FutureProvider<GamificationProfile>((ref) => _api(ref).gamification());
final trendsProvider = FutureProvider<Trends>((ref) => _api(ref).trends());
final weeklyReportProvider = FutureProvider.autoDispose<WeeklyReport?>((ref) => _api(ref).weeklyReport());
final wrappedProvider = FutureProvider.autoDispose.family<Wrapped, (int, int)>(
  (ref, mes) => _api(ref).wrapped(mes.$1, mes.$2),
);

/// Tras cualquier cambio en los datos del usuario se refresca todo lo que
/// depende de ellos: el disponible, los retos y los puntos se calculan en el
/// backend a partir de los mismos gastos.
void refreshData(WidgetRef ref) {
  ref
    ..invalidate(summaryProvider)
    ..invalidate(categoriesProvider)
    ..invalidate(expensesProvider)
    ..invalidate(incomesProvider)
    ..invalidate(recurringProvider)
    ..invalidate(pendingPaymentsProvider)
    ..invalidate(checkinsProvider)
    ..invalidate(goalsProvider)
    ..invalidate(challengesProvider)
    ..invalidate(suggestionsProvider)
    ..invalidate(gamificationProvider)
    ..invalidate(trendsProvider);
}
