import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/charts.dart';
import '../../core/format.dart';
import '../../core/motion.dart';
import '../../core/theme.dart';
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
                StreakChip(dias: perfil.rachaActual),
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
    final theme = Theme.of(context);
    return SectionCard(
      child: Padding(
        padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 16),
        child: Column(
          children: [
            const CoachAvatar(size: 96),
            const SizedBox(height: 16),
            Text(l.noBudgetTitle, textAlign: TextAlign.center, style: theme.textTheme.titleLarge),
            const SizedBox(height: 8),
            Text(l.noBudgetBody, textAlign: TextAlign.center, style: theme.textTheme.bodyLarge),
            const SizedBox(height: 20),
            FilledButton(
              onPressed: () => Navigator.push(
                context,
                MaterialPageRoute<void>(builder: (_) => const BudgetScreen(onboarding: true)),
              ),
              child: Text(l.createBudget),
            ),
          ],
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

    final tokens = context.tokens;
    final periodo = summary.budget.fechaFin.difference(summary.budget.fechaInicio).inDays + 1;
    final bolsa = summary.budget.montoTotal + summary.ingresosTotal;
    // Apiladas, las tarjetas pequeñas miden lo que necesitan; lado a lado, se reparten el alto.
    final apila = BentoRow.stacks(context);
    Widget alto(Widget hijo) => apila ? hijo : Expanded(child: hijo);

    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: staggered([
        // La cifra que importa hoy, con el avance del periodo alrededor de los días que quedan.
        Padding(
          padding: const EdgeInsets.only(bottom: AppTokens.gap),
          child: BentoTile(
            padding: const EdgeInsets.all(20),
            gradient: LinearGradient(
              begin: Alignment.topLeft,
              end: Alignment.bottomRight,
              colors: [scheme.primaryContainer, Color.lerp(scheme.primaryContainer, scheme.tertiaryContainer, 0.7)!],
            ),
            child: Row(
              children: [
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        l.availablePerDay,
                        style: theme.textTheme.titleMedium?.copyWith(color: scheme.onPrimaryContainer),
                      ),
                      const SizedBox(height: 4),
                      FittedBox(
                        fit: BoxFit.scaleDown,
                        alignment: Alignment.centerLeft,
                        child: AnimatedMoney(
                          value: summary.disponiblePorDia,
                          style: theme.textTheme.displayMedium?.copyWith(
                            color: scheme.onPrimaryContainer,
                            fontFeatures: kTabular,
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
                const SizedBox(width: 12),
                ExcludeSemantics(
                  child: ProgressRing(
                    size: 72,
                    progress: periodo <= 0 ? 0 : 1 - summary.diasRestantes / periodo,
                    color: scheme.primary,
                    track: scheme.onPrimaryContainer.withValues(alpha: 0.12),
                    child: AnimatedCount(
                      value: summary.diasRestantes,
                      style: theme.textTheme.titleLarge?.copyWith(color: scheme.onPrimaryContainer),
                    ),
                  ),
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
                  color: tokens.goals.container,
                  child: Row(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Icon(Icons.lightbulb_outline, color: tokens.goals.onContainer),
                      const SizedBox(width: 12),
                      Expanded(
                        child: Text(
                          l.riskBody(shortDate(context, summary.fechaAgotamiento!)),
                          style: theme.textTheme.bodyMedium?.copyWith(color: tokens.goals.onContainer),
                        ),
                      ),
                    ],
                  ),
                )
              : const SizedBox(width: double.infinity),
        ),
        Padding(
          padding: const EdgeInsets.only(bottom: AppTokens.gap),
          child: BentoRow(
            flex: const [5, 4],
            children: [
              _Stat(
                label: l.spent,
                value: summary.gastadoTotal,
                icon: Icons.shopping_bag_outlined,
                large: true,
                progress: bolsa <= 0 ? null : summary.gastadoTotal / bolsa,
              ),
              Column(
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  alto(_Stat(label: l.extraIncome, value: summary.ingresosTotal, icon: Icons.south_west, accent: tokens.income)),
                  const SizedBox(height: AppTokens.gap),
                  alto(
                    _Stat(
                      label: l.setAsideTotal,
                      value: summary.apartadoTotal,
                      icon: Icons.savings_outlined,
                      accent: tokens.goals,
                    ),
                  ),
                ],
              ),
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
        if (metas.isNotEmpty || retos.isNotEmpty)
          Padding(
            padding: const EdgeInsets.only(bottom: AppTokens.gap),
            child: BentoRow(
              children: [
                if (metas.isNotEmpty)
                  BentoTile(
                    title: l.activeGoal,
                    color: tokens.goals.container,
                    foreground: tokens.goals.onContainer,
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Row(
                          children: [
                            ProgressRing(
                              size: 56,
                              stroke: 6,
                              progress: metas.first.progreso,
                              color: tokens.goals.color,
                              track: tokens.goals.onContainer.withValues(alpha: 0.12),
                              child: Text(
                                '${(metas.first.progreso * 100).round()}%',
                                style: theme.textTheme.labelMedium?.copyWith(
                                  color: tokens.goals.onContainer,
                                  fontWeight: FontWeight.w700,
                                ),
                              ),
                            ),
                            const SizedBox(width: 12),
                            Expanded(
                              child: Text(
                                metas.first.nombre,
                                maxLines: 2,
                                overflow: TextOverflow.ellipsis,
                                style: theme.textTheme.titleSmall?.copyWith(color: tokens.goals.onContainer),
                              ),
                            ),
                          ],
                        ),
                        const SizedBox(height: 10),
                        // Los dos montos van en un renglón; si no caben, se encogen en vez de partirse.
                        FittedBox(
                          fit: BoxFit.scaleDown,
                          alignment: Alignment.centerLeft,
                          child: Text(
                            '${money(metas.first.aportado)} / ${money(metas.first.montoObjetivo)}',
                            style: theme.textTheme.bodySmall?.copyWith(
                              color: tokens.goals.onContainer,
                              fontFeatures: kTabular,
                            ),
                          ),
                        ),
                      ],
                    ),
                  ),
                if (retos.isNotEmpty)
                  BentoTile(
                    title: l.activeChallenge,
                    color: tokens.challenges.container,
                    foreground: tokens.challenges.onContainer,
                    child: Text(
                      retos.first.descripcion,
                      maxLines: 4,
                      overflow: TextOverflow.ellipsis,
                      style: theme.textTheme.bodyMedium?.copyWith(color: tokens.challenges.onContainer),
                    ),
                  ),
              ],
            ),
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

    void abrir() => Navigator.push(context, MaterialPageRoute<void>(builder: (_) => const AnalyticsScreen()));

    return SectionCard(
      title: l.thisWeek,
      onTap: abrir,
      trailing: TextButton(onPressed: abrir, child: Text(l.seeAnalytics)),
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
  const _Stat({
    required this.label,
    required this.value,
    required this.icon,
    this.accent,
    this.large = false,
    this.progress,
  });

  final String label;
  final double value;
  final IconData icon;
  final Accent? accent;
  final bool large;

  /// Parte del dinero del periodo que representa este monto.
  final double? progress;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final monto = FittedBox(
      fit: BoxFit.scaleDown,
      alignment: Alignment.centerLeft,
      child: AnimatedMoney(
        value: value,
        style: (large ? theme.textTheme.headlineSmall : theme.textTheme.titleMedium)?.copyWith(fontFeatures: kTabular),
      ),
    );
    final etiqueta = Text(
      label,
      style: theme.textTheme.labelLarge?.copyWith(color: theme.colorScheme.onSurfaceVariant),
      maxLines: 1,
      overflow: TextOverflow.ellipsis,
    );
    final insignia = IconBadge(
      icon: icon,
      size: large ? 40 : 36,
      color: accent?.container,
      foreground: accent?.onContainer,
    );
    return MergeSemantics(
      child: BentoTile(
        padding: EdgeInsets.all(large ? 16 : 12),
        child: large
            ? Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  insignia,
                  const SizedBox(height: 16),
                  etiqueta,
                  monto,
                  if (progress != null) ...[
                    const SizedBox(height: 10),
                    TweenAnimationBuilder<double>(
                      tween: Tween(begin: 0, end: progress!.clamp(0, 1).toDouble()),
                      duration: motion(context, const Duration(milliseconds: 600)),
                      curve: kMotionCurve,
                      builder: (context, v, _) => LinearProgressIndicator(
                        value: v,
                        minHeight: 8,
                        borderRadius: BorderRadius.circular(4),
                      ),
                    ),
                  ],
                ],
              )
            : Row(
                children: [
                  insignia,
                  const SizedBox(width: 10),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      mainAxisAlignment: MainAxisAlignment.center,
                      children: [etiqueta, monto],
                    ),
                  ),
                ],
              ),
      ),
    );
  }
}

/// La racha de días con registro, con una llama que late.
class StreakChip extends StatelessWidget {
  const StreakChip({super.key, required this.dias});

  final int dias;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final acento = context.tokens.challenges;
    return Container(
      padding: const EdgeInsets.fromLTRB(10, 6, 14, 6),
      decoration: BoxDecoration(color: acento.container, borderRadius: BorderRadius.circular(20)),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Breathing(amount: 0.14, child: Icon(Icons.local_fire_department, size: 20, color: acento.color)),
          const SizedBox(width: 4),
          Text(
            context.l.streakDays(dias),
            style: theme.textTheme.labelLarge?.copyWith(color: acento.onContainer, fontWeight: FontWeight.w700),
          ),
        ],
      ),
    );
  }
}
