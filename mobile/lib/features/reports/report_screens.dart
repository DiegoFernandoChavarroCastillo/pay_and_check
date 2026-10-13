import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/charts.dart';
import '../../core/format.dart';
import '../../core/widgets.dart';
import '../../data/models.dart';
import '../../data/providers.dart';
import '../coach/coach_widgets.dart';
import 'analytics_screen.dart';

/// Reporte de la semana en curso: gasto por categoría frente al ritmo esperado.
class WeeklyReportScreen extends ConsumerWidget {
  const WeeklyReportScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final l = context.l;
    final theme = Theme.of(context);
    return Scaffold(
      appBar: AppBar(title: Text(l.weeklyReport)),
      body: AsyncView(
        value: ref.watch(weeklyReportProvider),
        onRetry: () => ref.invalidate(weeklyReportProvider),
        builder: (reporte) {
          if (reporte == null) {
            return Center(child: EmptyView(icon: Icons.insights_outlined, text: l.noBudgetTitle));
          }
          final bajoRitmo = reporte.diferencia <= 0;
          return ListView(
            padding: const EdgeInsets.all(16),
            children: [
              Text(
                '${shortDate(context, reporte.semanaInicio)} – ${shortDate(context, reporte.semanaFin)}',
                style: theme.textTheme.titleMedium,
              ),
              const SizedBox(height: 12),
              SectionCard(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    LabeledProgress(
                      label: l.weekSpent,
                      value: '${money(reporte.gastoTotal)} / ${money(reporte.ritmoEsperado)}',
                      progress: reporte.ritmoEsperado <= 0 ? 0 : reporte.gastoTotal / reporte.ritmoEsperado,
                    ),
                    Text(
                      bajoRitmo
                          ? l.weekUnderPace(money(-reporte.diferencia))
                          : l.weekOverPace(money(reporte.diferencia)),
                    ),
                  ],
                ),
              ),
              if (reporte.porCategoria.isNotEmpty)
                SectionCard(
                  title: l.byCategory,
                  child: CategoryDonut(slices: slicesOf(reporte.porCategoria), otherLabel: l.otherCategories),
                ),
              SectionCard(
                title: l.coachSays,
                child: Text(reporte.recomendaciones, style: theme.textTheme.bodyLarge),
              ),
            ],
          );
        },
      ),
    );
  }
}

/// Resumen mensual tipo "historias": una tarjeta por dato destacado.
class WrappedScreen extends ConsumerStatefulWidget {
  const WrappedScreen({super.key});

  @override
  ConsumerState<WrappedScreen> createState() => _WrappedScreenState();
}

class _WrappedScreenState extends ConsumerState<WrappedScreen> {
  late (int, int) _mes = (DateTime.now().year, DateTime.now().month);

  void _mover(int delta) {
    final fecha = DateTime(_mes.$1, _mes.$2 + delta);
    setState(() => _mes = (fecha.year, fecha.month));
  }

  List<(IconData, String, String)> _paginas(Wrapped w) {
    final l = context.l;
    return [
      (Icons.payments_outlined, money(w.gastoTotal), l.wrappedSpent(w.numGastos)),
      (Icons.event_available_outlined, '${w.diasConRegistro}', l.wrappedDays),
      if (w.categoriaTop != null)
        (Icons.pie_chart_outline, w.categoriaTop!, l.wrappedTopCategory(w.categoriaTopPct ?? 0)),
      if (w.gastoMayor != null)
        (Icons.north_east, money(w.gastoMayorMonto ?? 0), l.wrappedBiggest(w.gastoMayor!)),
      if (w.variacionPct != null)
        (
          w.variacionPct! <= 0 ? Icons.trending_down : Icons.trending_up,
          '${w.variacionPct! > 0 ? '+' : ''}${w.variacionPct}%',
          l.wrappedVsLastMonth,
        ),
      if (w.aportadoAMetas > 0) (Icons.flag_outlined, money(w.aportadoAMetas), l.wrappedGoals),
      (Icons.emoji_events_outlined, '${w.puntosGanados}', l.wrappedPoints),
      if (w.insignias.isNotEmpty) (Icons.military_tech_outlined, '${w.insignias.length}', w.insignias.join(' · ')),
      if (w.animoFrecuente != null)
        (Icons.mood, moodEmojis[w.animoFrecuente] ?? '', l.wrappedMood(moodLabel(l, w.animoFrecuente!))),
      (Icons.auto_awesome, '', w.fraseCoach),
    ];
  }

  @override
  Widget build(BuildContext context) {
    final l = context.l;
    final theme = Theme.of(context);
    final scheme = theme.colorScheme;
    final ahora = DateTime.now();
    final esMesActual = _mes == (ahora.year, ahora.month);

    return Scaffold(
      appBar: AppBar(title: Text(l.wrappedTitle)),
      body: Column(
        children: [
          Row(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              IconButton(tooltip: l.previousMonth, icon: const Icon(Icons.chevron_left), onPressed: () => _mover(-1)),
              Text(monthName(context, _mes.$1, _mes.$2), style: theme.textTheme.titleMedium),
              IconButton(
                tooltip: l.nextMonth,
                icon: const Icon(Icons.chevron_right),
                onPressed: esMesActual ? null : () => _mover(1),
              ),
            ],
          ),
          Expanded(
            child: AsyncView(
              value: ref.watch(wrappedProvider(_mes)),
              onRetry: () => ref.invalidate(wrappedProvider(_mes)),
              builder: (w) {
                if (w.numGastos == 0) {
                  return Center(child: EmptyView(icon: Icons.auto_stories_outlined, text: l.wrappedEmpty));
                }
                final paginas = _paginas(w);
                return PageView.builder(
                  controller: PageController(viewportFraction: 0.88),
                  itemCount: paginas.length,
                  itemBuilder: (context, i) {
                    final (icono, valor, texto) = paginas[i];
                    return Card(
                      margin: const EdgeInsets.fromLTRB(6, 8, 6, 24),
                      color: i.isEven ? scheme.primaryContainer : scheme.secondaryContainer,
                      child: Padding(
                        padding: const EdgeInsets.all(28),
                        child: Column(
                          mainAxisAlignment: MainAxisAlignment.center,
                          children: [
                            Icon(icono, size: 56, color: scheme.primary),
                            const SizedBox(height: 24),
                            if (valor.isNotEmpty)
                              FittedBox(
                                child: Text(
                                  valor,
                                  style: theme.textTheme.displayMedium?.copyWith(fontWeight: FontWeight.w700),
                                ),
                              ),
                            const SizedBox(height: 16),
                            Text(texto, style: theme.textTheme.titleLarge, textAlign: TextAlign.center),
                            const Spacer(),
                            Text('${i + 1} / ${paginas.length}', style: theme.textTheme.labelMedium),
                          ],
                        ),
                      ),
                    );
                  },
                );
              },
            ),
          ),
        ],
      ),
    );
  }
}
