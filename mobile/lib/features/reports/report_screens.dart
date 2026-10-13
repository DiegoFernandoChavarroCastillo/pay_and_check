import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/charts.dart';
import '../../core/format.dart';
import '../../core/motion.dart';
import '../../core/theme.dart';
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
          final coach = context.tokens.coach;
          return ListView(
            padding: const EdgeInsets.all(16),
            children: staggered([
              Padding(
                padding: const EdgeInsets.only(left: 4, bottom: 12),
                child: Text(
                  '${shortDate(context, reporte.semanaInicio)} – ${shortDate(context, reporte.semanaFin)}',
                  style: theme.textTheme.titleMedium,
                ),
              ),
              Padding(
                padding: const EdgeInsets.only(bottom: AppTokens.gap),
                child: BentoRow(
                  children: [
                    _Figure(label: l.weekSpent, value: reporte.gastoTotal, color: theme.colorScheme.primaryContainer),
                    _Figure(label: l.weekPace, value: reporte.ritmoEsperado),
                  ],
                ),
              ),
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
                color: coach.container,
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Row(
                      children: [
                        const CoachAvatar(size: 40),
                        const SizedBox(width: 12),
                        Text(l.coachSays, style: theme.textTheme.titleMedium?.copyWith(color: coach.onContainer)),
                      ],
                    ),
                    const SizedBox(height: 12),
                    Text(
                      reporte.recomendaciones,
                      style: theme.textTheme.bodyLarge?.copyWith(color: coach.onContainer),
                    ),
                  ],
                ),
              ),
            ]),
          );
        },
      ),
    );
  }
}

/// Una cifra del reporte como tarjeta pequeña.
class _Figure extends StatelessWidget {
  const _Figure({required this.label, required this.value, this.color});

  final String label;
  final double value;
  final Color? color;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return BentoTile(
      color: color,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(label, style: theme.textTheme.labelLarge),
          const SizedBox(height: 4),
          FittedBox(
            fit: BoxFit.scaleDown,
            alignment: Alignment.centerLeft,
            child: AnimatedMoney(value: value, style: theme.textTheme.headlineSmall?.copyWith(fontFeatures: kTabular)),
          ),
        ],
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
  final _paginador = PageController(viewportFraction: 0.88);
  int _pagina = 0;

  @override
  void dispose() {
    _paginador.dispose();
    super.dispose();
  }


  void _mover(int delta) {
    final fecha = DateTime(_mes.$1, _mes.$2 + delta);
    setState(() {
      _mes = (fecha.year, fecha.month);
      _pagina = 0;
    });
    if (_paginador.hasClients) _paginador.jumpToPage(0);
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
              IconButton.filledTonal(
                tooltip: l.previousMonth,
                icon: const Icon(Icons.chevron_left),
                onPressed: () => _mover(-1),
              ),
              const SizedBox(width: 12),
              Text(monthName(context, _mes.$1, _mes.$2), style: theme.textTheme.titleMedium),
              const SizedBox(width: 12),
              IconButton.filledTonal(
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
                final tokens = context.tokens;
                // Cada página tiene su color: el resumen se siente como pasar historias.
                final Accent propio = (
                  color: scheme.primary,
                  container: scheme.primaryContainer,
                  onContainer: scheme.onPrimaryContainer,
                );
                final acentos = [propio, tokens.coach, tokens.goals, tokens.income, tokens.challenges];
                return Column(
                  children: [
                    Expanded(
                      child: PageView.builder(
                        controller: _paginador,
                        itemCount: paginas.length,
                        onPageChanged: (i) => setState(() => _pagina = i),
                        itemBuilder: (context, i) {
                          final (icono, valor, texto) = paginas[i];
                          final acento = acentos[i % acentos.length];
                          final esCoach = i == paginas.length - 1;
                          return Padding(
                            padding: const EdgeInsets.fromLTRB(6, 8, 6, 12),
                            child: BentoTile(
                              color: acento.container,
                              padding: const EdgeInsets.all(28),
                              child: Expanded(
                                child: SizedBox(
                                  width: double.infinity,
                                  child: Column(
                                    mainAxisAlignment: MainAxisAlignment.center,
                                    children: [
                                      if (esCoach)
                                        const CoachAvatar(size: 96)
                                      else
                                        IconBadge(
                                          icon: icono,
                                          size: 88,
                                          color: acento.color,
                                          foreground: acento.container,
                                        ),
                                      const SizedBox(height: 24),
                                      // La cifra entra creciendo cuando su página es la que se ve.
                                      if (valor.isNotEmpty)
                                        AnimatedScale(
                                          scale: i == _pagina ? 1 : 0.7,
                                          duration: motion(context, const Duration(milliseconds: 500)),
                                          curve: kSpring,
                                          child: FittedBox(
                                            child: Text(
                                              valor,
                                              style: theme.textTheme.displayMedium?.copyWith(
                                                color: acento.onContainer,
                                                fontFeatures: kTabular,
                                              ),
                                            ),
                                          ),
                                        ),
                                      const SizedBox(height: 16),
                                      Text(
                                        texto,
                                        style: theme.textTheme.titleLarge?.copyWith(color: acento.onContainer),
                                        textAlign: TextAlign.center,
                                      ),
                                    ],
                                  ),
                                ),
                              ),
                            ),
                          );
                        },
                      ),
                    ),
                    Semantics(
                      label: '${_pagina + 1} / ${paginas.length}',
                      child: Padding(
                        padding: const EdgeInsets.only(bottom: 20, top: 4),
                        child: Row(
                          mainAxisAlignment: MainAxisAlignment.center,
                          children: [
                            for (var i = 0; i < paginas.length; i++)
                              AnimatedContainer(
                                duration: motion(context, const Duration(milliseconds: 250)),
                                curve: kMotionCurve,
                                margin: const EdgeInsets.symmetric(horizontal: 3),
                                width: i == _pagina ? 20 : 8,
                                height: 8,
                                decoration: BoxDecoration(
                                  color: i == _pagina ? scheme.primary : scheme.surfaceContainerHighest,
                                  borderRadius: BorderRadius.circular(4),
                                ),
                              ),
                          ],
                        ),
                      ),
                    ),
                  ],
                );
              },
            ),
          ),
        ],
      ),
    );
  }
}
