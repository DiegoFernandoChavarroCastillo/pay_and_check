import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/charts.dart';
import '../../core/format.dart';
import '../../core/motion.dart';
import '../../core/theme.dart';
import '../../core/widgets.dart';
import '../../data/models.dart';
import '../../data/providers.dart';
import '../../l10n/gen/app_localizations.dart';

List<Slice> slicesOf(List<CategoryAmount> categorias) => [
      for (final c in categorias) (label: c.categoria, value: c.monto),
    ];

/// Cambio de [actual] frente a [anterior] en palabras, o null si no hay con qué comparar.
String? weekChangeText(AppLocalizations l, double actual, double anterior) {
  if (anterior <= 0) return null;
  final pct = ((actual - anterior) / anterior * 100).round();
  if (pct == 0) return l.weekSameAsPrevious;
  return pct > 0 ? l.weekMoreThanPrevious(pct) : l.weekLessThanPrevious(-pct);
}

IconData weekChangeIcon(double actual, double anterior) => actual == anterior
    ? Icons.trending_flat
    : (actual > anterior ? Icons.trending_up : Icons.trending_down);

/// Análisis: en qué se fue el gasto de cada semana y cómo cambia en el tiempo.
class AnalyticsScreen extends ConsumerStatefulWidget {
  const AnalyticsScreen({super.key});

  @override
  ConsumerState<AnalyticsScreen> createState() => _AnalyticsScreenState();
}

class _AnalyticsScreenState extends ConsumerState<AnalyticsScreen> {
  /// Cuántas semanas atrás se está mirando; 0 es la actual.
  int _atras = 0;
  bool _porDias = false;

  @override
  Widget build(BuildContext context) {
    final l = context.l;
    return Scaffold(
      appBar: AppBar(title: Text(l.analytics)),
      body: AsyncView(
        value: ref.watch(trendsProvider),
        onRetry: () => ref.invalidate(trendsProvider),
        builder: (t) => t.sinGastos
            ? Center(child: EmptyView(icon: Icons.donut_small_outlined, text: l.analyticsEmpty))
            : _contenido(t),
      ),
    );
  }

  Widget _contenido(Trends t) {
    final l = context.l;
    final theme = Theme.of(context);
    final scheme = theme.colorScheme;
    final indice = (t.semanas.length - 1 - _atras).clamp(0, t.semanas.length - 1);
    final semana = t.semanas[indice];
    final anterior = indice > 0 ? t.semanas[indice - 1] : null;
    final cambio = anterior == null ? null : weekChangeText(l, semana.total, anterior.total);

    return ListView(
      padding: const EdgeInsets.all(16),
      children: staggered([
        Row(
          mainAxisAlignment: MainAxisAlignment.spaceBetween,
          children: [
            IconButton.filledTonal(
              tooltip: l.previousWeek,
              icon: const Icon(Icons.chevron_left),
              onPressed: indice == 0 ? null : () => setState(() => _atras++),
            ),
            Text(
              '${shortDate(context, semana.inicio)} – ${shortDate(context, semana.fin)}',
              style: theme.textTheme.titleMedium,
            ),
            IconButton.filledTonal(
              tooltip: l.nextWeek,
              icon: const Icon(Icons.chevron_right),
              onPressed: _atras == 0 ? null : () => setState(() => _atras--),
            ),
          ],
        ),
        const SizedBox(height: 4),
        SectionCard(
          title: l.byCategory,
          child: AnimatedSize(
            duration: motion(context),
            curve: kMotionCurve,
            alignment: Alignment.topCenter,
            child: AnimatedSwitcher(
              duration: motion(context, const Duration(milliseconds: 250)),
              child: semana.total <= 0
                  ? Padding(
                      key: ValueKey('vacia-$indice'),
                      padding: const EdgeInsets.symmetric(vertical: 24),
                      child: Center(child: Text(l.analyticsEmptyWeek, textAlign: TextAlign.center)),
                    )
                  : CategoryDonut(
                      key: ValueKey('dona-$indice'),
                      slices: slicesOf(semana.porCategoria),
                      otherLabel: l.otherCategories,
                    ),
            ),
          ),
        ),
        SectionCard(
          color: scheme.primaryContainer,
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(l.weekSpent, style: theme.textTheme.titleMedium),
              const SizedBox(height: 4),
              FittedBox(
                fit: BoxFit.scaleDown,
                alignment: Alignment.centerLeft,
                child: AnimatedMoney(
                  value: semana.total,
                  style: theme.textTheme.displaySmall?.copyWith(fontFeatures: kTabular),
                ),
              ),
              if (cambio != null) ...[
                const SizedBox(height: 8),
                Row(
                  children: [
                    Icon(weekChangeIcon(semana.total, anterior!.total), size: 20, color: scheme.primary),
                    const SizedBox(width: 8),
                    Expanded(child: Text(cambio)),
                  ],
                ),
              ],
              const SizedBox(height: 4),
              Text(
                l.weeklyAverage(money(t.promedioSemanal)),
                style: theme.textTheme.bodySmall?.copyWith(color: scheme.onSurfaceVariant),
              ),
            ],
          ),
        ),
        SectionCard(
          title: l.trend,
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              SegmentedButton<bool>(
                segments: [
                  ButtonSegment(value: false, label: Text(l.trendWeeks)),
                  ButtonSegment(value: true, label: Text(l.trendDays)),
                ],
                selected: {_porDias},
                onSelectionChanged: (s) => setState(() => _porDias = s.first),
              ),
              const SizedBox(height: 20),
              AnimatedSwitcher(
                duration: motion(context, const Duration(milliseconds: 250)),
                child: _porDias ? _dias(t) : _semanas(t),
              ),
            ],
          ),
        ),
      ]),
    );
  }

  Widget _semanas(Trends t) {
    final l = context.l;
    return TrendLine(
      key: const ValueKey('semanas'),
      series: [TrendSeries(name: l.weekSpent, values: [for (final s in t.semanas) s.total])],
      labels: [for (final s in t.semanas) shortDate(context, s.inicio)],
      reference: t.promedioSemanal,
      referenceLabel: l.average,
    );
  }

  /// Esta semana frente a la anterior, día por día (lunes a domingo).
  Widget _dias(Trends t) {
    final l = context.l;
    final hoy = today();
    final previa = t.dias.take(7).toList();
    // Los días que aún no llegan no se dibujan: no son un gasto de cero.
    final actual = t.dias.skip(7).where((d) => !d.fecha.isAfter(hoy)).toList();
    final series = [
      TrendSeries(name: l.thisWeek, values: [for (final d in actual) d.total]),
      TrendSeries(name: l.previousWeek, values: [for (final d in previa) d.total], secondary: true),
    ];
    return Column(
      key: const ValueKey('dias'),
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        TrendLine(
          series: series,
          labels: [for (final nombre in weekdayNames(context)) nombre.substring(0, 2)],
        ),
        const SizedBox(height: 8),
        TrendLegend(series: series),
      ],
    );
  }
}
