import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/charts.dart';
import '../../core/format.dart';
import '../../core/motion.dart';
import '../../core/widgets.dart';
import '../../data/models.dart';
import '../../data/providers.dart';
import '../../data/session.dart';
import '../budget/budget_screen.dart';
import '../coach/coach_widgets.dart';
import '../reports/analytics_screen.dart';

/// Dashboard: cuánto se puede gastar hoy, el check-in y lo que propone el coach.
class HomeScreen extends ConsumerWidget {
  const HomeScreen({super.key, required this.onOpenCoach});

  final VoidCallback onOpenCoach;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final l = context.l;
    final theme = Theme.of(context);
    final nombre = ref.watch(sessionProvider).value?.nombre.split(' ').first ?? '';
    final summary = ref.watch(summaryProvider);
    final perfil = ref.watch(gamificationProvider).value;

    return RefreshIndicator(
      onRefresh: () async {
        refreshData(ref);
        ref.invalidate(insightsProvider);
        await ref.read(summaryProvider.future);
      },
      child: ListView(
        padding: const EdgeInsets.fromLTRB(16, 16, 16, 96),
        children: [
          Row(
            children: [
              Expanded(child: Text(l.homeGreeting(nombre), style: theme.textTheme.headlineSmall)),
              if (perfil != null && perfil.rachaActual > 0)
                Chip(
                  avatar: const Icon(Icons.local_fire_department, size: 18),
                  label: Text(l.streakDays(perfil.rachaActual)),
                ),
            ],
          ),
          const SizedBox(height: 16),
          AsyncView(
            value: summary,
            onRetry: () => ref.invalidate(summaryProvider),
            builder: (s) => s == null ? const _NoBudget() : _Dashboard(summary: s, onOpenCoach: onOpenCoach),
          ),
        ],
      ),
    );
  }
}

class _NoBudget extends StatelessWidget {
  const _NoBudget();

  @override
  Widget build(BuildContext context) {
    final l = context.l;
    return SectionCard(
      child: EmptyView(
        icon: Icons.account_balance_wallet_outlined,
        text: '${l.noBudgetTitle}\n\n${l.noBudgetBody}',
        action: FilledButton(
          onPressed: () => Navigator.push(
            context,
            MaterialPageRoute<void>(builder: (_) => const BudgetScreen(onboarding: true)),
          ),
          child: Text(l.createBudget),
        ),
      ),
    );
  }
}

class _Dashboard extends ConsumerWidget {
  const _Dashboard({required this.summary, required this.onOpenCoach});

  final BudgetSummary summary;
  final VoidCallback onOpenCoach;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final l = context.l;
    final theme = Theme.of(context);
    final scheme = theme.colorScheme;
    final insights = ref.watch(insightsProvider).value ?? const <Insight>[];
    final metas = (ref.watch(goalsProvider).value ?? const <Goal>[]).where((g) => !g.cumplida);
    final retos = (ref.watch(challengesProvider).value ?? const <Challenge>[]).where((c) => c.activo);

    final tendencias = ref.watch(trendsProvider).value;

    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: staggered([
        Card(
          color: scheme.primaryContainer,
          margin: const EdgeInsets.only(bottom: 12),
          child: Padding(
            padding: const EdgeInsets.all(20),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(l.availablePerDay, style: theme.textTheme.titleMedium?.copyWith(color: scheme.onPrimaryContainer)),
                const SizedBox(height: 4),
                FittedBox(
                  fit: BoxFit.scaleDown,
                  alignment: Alignment.centerLeft,
                  child: AnimatedMoney(
                    value: summary.disponiblePorDia,
                    style: theme.textTheme.displayMedium?.copyWith(
                      color: scheme.onPrimaryContainer,
                      fontWeight: FontWeight.w700,
                    ),
                  ),
                ),
                const SizedBox(height: 8),
                Text(
                  '${l.availableTotal(money(summary.disponibleTotal))} · ${l.daysLeft(summary.diasRestantes)}',
                  style: theme.textTheme.bodyMedium?.copyWith(color: scheme.onPrimaryContainer),
                ),
              ],
            ),
          ),
        ),
        // El aviso se despliega y se recoge en vez de aparecer de golpe.
        AnimatedSize(
          duration: motion(context),
          curve: kMotionCurve,
          alignment: Alignment.topCenter,
          child: summary.enRiesgo && summary.fechaAgotamiento != null
              ? SectionCard(
                  color: scheme.tertiaryContainer,
                  child: Row(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Icon(Icons.lightbulb_outline, color: scheme.onTertiaryContainer),
                      const SizedBox(width: 12),
                      Expanded(
                        child: Text(
                          l.riskBody(shortDate(context, summary.fechaAgotamiento!)),
                          style: theme.textTheme.bodyMedium?.copyWith(color: scheme.onTertiaryContainer),
                        ),
                      ),
                    ],
                  ),
                )
              : const SizedBox(width: double.infinity),
        ),
        Padding(
          padding: const EdgeInsets.only(bottom: 12),
          child: Row(
            children: [
              _Stat(label: l.spent, value: summary.gastadoTotal),
              const SizedBox(width: 8),
              _Stat(label: l.extraIncome, value: summary.ingresosTotal),
              const SizedBox(width: 8),
              _Stat(label: l.setAsideTotal, value: summary.apartadoTotal),
            ],
          ),
        ),
        if (tendencias != null) _WeekCard(trends: tendencias),
        const CheckinCard(),
        if (insights.isNotEmpty) ...[
          Padding(
            padding: const EdgeInsets.only(bottom: 8, top: 4),
            child: Row(
              children: [
                Expanded(child: Text(l.coachSays, style: theme.textTheme.titleMedium)),
                TextButton(onPressed: onOpenCoach, child: Text(l.seeAll)),
              ],
            ),
          ),
          InsightCard(insight: insights.first),
        ],
        if (metas.isNotEmpty)
          SectionCard(
            title: l.activeGoal,
            child: LabeledProgress(
              label: metas.first.nombre,
              value: '${money(metas.first.aportado)} / ${money(metas.first.montoObjetivo)}',
              progress: metas.first.progreso,
            ),
          ),
        if (retos.isNotEmpty)
          SectionCard(
            title: l.activeChallenge,
            child: Text(retos.first.descripcion),
          ),
        if (summary.desglose.isNotEmpty)
          SectionCard(
            title: l.byCategory,
            child: Column(
              children: [
                for (final c in [...summary.desglose]..sort((a, b) => b.gastado.compareTo(a.gastado)))
                  LabeledProgress(
                    label: c.limite == null ? c.categoria : '${c.categoria} · ${l.limitOf(money(c.limite!))}',
                    value: money(c.gastado),
                    // Con límite, la barra es el avance hacia él; sin límite, su peso en el gasto total.
                    progress: c.limite != null
                        ? c.gastado / c.limite!
                        : (summary.gastadoTotal <= 0 ? 0 : c.gastado / summary.gastadoTotal),
                    color: c.excedido ? scheme.tertiary : null,
                  ),
              ],
            ),
          ),
      ]),
    );
  }
}

/// En qué se ha ido el gasto de la semana, con acceso al análisis completo.
class _WeekCard extends StatelessWidget {
  const _WeekCard({required this.trends});

  final Trends trends;

  @override
  Widget build(BuildContext context) {
    final l = context.l;
    final theme = Theme.of(context);
    final semana = trends.semanaActual;
    final anterior = trends.semanas.length > 1 ? trends.semanas[trends.semanas.length - 2] : null;
    final cambio = anterior == null ? null : weekChangeText(l, semana.total, anterior.total);

    return SectionCard(
      title: l.thisWeek,
      trailing: TextButton(
        onPressed: () => Navigator.push(
          context,
          MaterialPageRoute<void>(builder: (_) => const AnalyticsScreen()),
        ),
        child: Text(l.seeAnalytics),
      ),
      child: semana.total <= 0
          ? Text(l.analyticsEmptyWeek)
          : Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                CategoryDonut(slices: slicesOf(semana.porCategoria), otherLabel: l.otherCategories, compact: true),
                if (cambio != null) ...[
                  const SizedBox(height: 12),
                  Row(
                    children: [
                      Icon(
                        weekChangeIcon(semana.total, anterior!.total),
                        size: 18,
                        color: theme.colorScheme.primary,
                      ),
                      const SizedBox(width: 8),
                      Expanded(child: Text(cambio, style: theme.textTheme.bodySmall)),
                    ],
                  ),
                ],
              ],
            ),
    );
  }
}

class _Stat extends StatelessWidget {
  const _Stat({required this.label, required this.value});

  final String label;
  final double value;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Expanded(
      child: Card(
        margin: EdgeInsets.zero,
        child: Padding(
          padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 14),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(label, style: theme.textTheme.labelMedium, maxLines: 1, overflow: TextOverflow.ellipsis),
              const SizedBox(height: 4),
              FittedBox(
                fit: BoxFit.scaleDown,
                child: AnimatedMoney(
                  value: value,
                  style: theme.textTheme.titleMedium?.copyWith(fontWeight: FontWeight.w600),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
