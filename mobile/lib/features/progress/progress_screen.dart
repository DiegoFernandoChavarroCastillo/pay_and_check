import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/format.dart';
import '../../core/motion.dart';
import '../../core/theme.dart';
import '../../core/widgets.dart';
import '../../data/api.dart';
import '../../data/models.dart';
import '../../data/providers.dart';
import '../../l10n/gen/app_localizations.dart';
import '../home/home_screen.dart' show StreakChip;
import 'goal_dialogs.dart';

/// Progreso: nivel y puntos, metas de ahorro, retos e insignias.
class ProgressScreen extends ConsumerWidget {
  const ProgressScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final l = context.l;
    return DefaultTabController(
      length: 3,
      // La cabecera se desplaza con el contenido: con la letra grande no cabría fija.
      child: NestedScrollView(
        headerSliverBuilder: (context, _) => [
          SliverToBoxAdapter(
            child: Column(
              children: [
                Padding(
                  padding: const EdgeInsets.fromLTRB(16, 16, 16, 0),
                  child: AsyncView(
                    value: ref.watch(gamificationProvider),
                    onRetry: () => ref.invalidate(gamificationProvider),
                    builder: (perfil) => _LevelHeader(perfil: perfil),
                  ),
                ),
                PillTabs(labels: [l.goals, l.challenges, l.badges]),
              ],
            ),
          ),
        ],
        body: const TabBarView(children: [_Goals(), _Challenges(), _Badges()]),
      ),
    );
  }
}

String _pct(double? ratio) => ratio == null ? '—' : '${(ratio * 100).round()}%';

class _LevelHeader extends StatelessWidget {
  const _LevelHeader({required this.perfil});

  final GamificationProfile perfil;

  @override
  Widget build(BuildContext context) {
    final l = context.l;
    final theme = Theme.of(context);
    final scheme = theme.colorScheme;
    final siguiente = perfil.puntosSiguiente;
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        BentoTile(
          padding: const EdgeInsets.all(20),
          gradient: LinearGradient(
            begin: Alignment.topLeft,
            end: Alignment.bottomRight,
            colors: [scheme.primaryContainer, Color.lerp(scheme.primaryContainer, scheme.tertiaryContainer, 0.7)!],
          ),
          child: Row(
            children: [
              ExcludeSemantics(
                child: ProgressRing(
                  size: 84,
                  stroke: 8,
                  progress: perfil.progresoNivel,
                  color: scheme.primary,
                  track: scheme.onPrimaryContainer.withValues(alpha: 0.12),
                  child: AnimatedCount(
                    value: perfil.nivelNumero,
                    style: theme.textTheme.headlineMedium?.copyWith(color: scheme.onPrimaryContainer),
                  ),
                ),
              ),
              const SizedBox(width: 16),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      l.levelTitle(perfil.nivelNumero, perfil.nivelNombre),
                      style: theme.textTheme.titleLarge?.copyWith(color: scheme.onPrimaryContainer),
                    ),
                    const SizedBox(height: 2),
                    AnimatedCount(
                      value: perfil.puntos,
                      format: l.pointsTotal,
                      style: theme.textTheme.bodyLarge?.copyWith(
                        color: scheme.onPrimaryContainer,
                        fontFeatures: kTabular,
                        fontWeight: FontWeight.w600,
                      ),
                    ),
                    Text(
                      siguiente == null ? l.maxLevel : l.pointsToNext(siguiente - perfil.puntos),
                      style: theme.textTheme.bodySmall?.copyWith(color: scheme.onPrimaryContainer),
                    ),
                    if (perfil.rachaActual > 0) ...[
                      const SizedBox(height: 8),
                      StreakChip(dias: perfil.rachaActual),
                    ],
                  ],
                ),
              ),
            ],
          ),
        ),
        const SizedBox(height: AppTokens.gap),
        BentoRow(
          children: [
            // Gastar más de lo que entró no se muestra como un porcentaje negativo enorme: no hubo ahorro, 0%.
            _Metric(
              label: l.metricSavings,
              value: _pct(perfil.ratioAhorro?.clamp(0, 1).toDouble()),
              tooltip: l.metricSavingsHint,
            ),
            _Metric(label: l.metricConsistency, value: _pct(perfil.consistencia), tooltip: l.metricConsistencyHint),
            _Metric(
              label: l.metricImprovement,
              // Solo se muestra cuando hay mejora: un mes más flojo no se marca en negativo (cero culpa).
              value: (perfil.mejoraMensual ?? -1) < 0 ? '—' : '+${(perfil.mejoraMensual! * 100).round()} pts',
              tooltip: l.metricImprovementHint,
            ),
          ],
        ),
      ],
    );
  }
}

class _Metric extends StatelessWidget {
  const _Metric({required this.label, required this.value, required this.tooltip});

  final String label;
  final String value;
  final String tooltip;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Tooltip(
      message: tooltip,
      triggerMode: TooltipTriggerMode.tap,
      showDuration: const Duration(seconds: 5),
      child: BentoTile(
        padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 12),
        child: SizedBox(
          width: double.infinity,
          child: Column(
            children: [
              FittedBox(
                fit: BoxFit.scaleDown,
                child: Text(value, style: theme.textTheme.titleLarge?.copyWith(fontFeatures: kTabular)),
              ),
              const SizedBox(height: 2),
              Text(
                label,
                style: theme.textTheme.labelSmall?.copyWith(color: theme.colorScheme.onSurfaceVariant),
                textAlign: TextAlign.center,
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _Goals extends ConsumerWidget {
  const _Goals();

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final l = context.l;
    return AsyncView(
      value: ref.watch(goalsProvider),
      onRetry: () => ref.invalidate(goalsProvider),
      builder: (metas) => ListView(
        padding: EdgeInsets.fromLTRB(16, 16, 16, 16 + bottomInset(context)),
        children: [
          if (metas.isEmpty) EmptyView(icon: Icons.flag_outlined, text: l.noGoals),
          for (final meta in metas) _GoalCard(key: ValueKey(meta.id), meta: meta),
          OutlinedButton.icon(
            onPressed: () => showGoalDialog(context, ref),
            icon: const Icon(Icons.add),
            label: Text(l.newGoal),
          ),
        ],
      ),
    );
  }
}

class _GoalCard extends ConsumerStatefulWidget {
  const _GoalCard({super.key, required this.meta});

  final Goal meta;

  @override
  ConsumerState<_GoalCard> createState() => _GoalCardState();
}

class _GoalCardState extends ConsumerState<_GoalCard> {
  bool _celebrar = false;

  @override
  void didUpdateWidget(_GoalCard old) {
    super.didUpdateWidget(old);
    // La meta se acaba de cumplir en esta sesión: se celebra una vez.
    if (!old.meta.cumplida && widget.meta.cumplida) _celebrar = true;
  }

  @override
  Widget build(BuildContext context) {
    final l = context.l;
    final theme = Theme.of(context);
    final acento = context.tokens.goals;
    final meta = widget.meta;
    final api = ref.read(apiProvider);
    final tarjeta = SectionCard(
      color: meta.cumplida ? acento.container : null,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              ProgressRing(
                size: 68,
                progress: meta.progreso,
                color: acento.color,
                track: meta.cumplida ? acento.onContainer.withValues(alpha: 0.12) : null,
                child: meta.cumplida
                    ? Icon(Icons.verified, color: acento.color)
                    : Text(
                        '${(meta.progreso * 100).round()}%',
                        style: theme.textTheme.labelLarge?.copyWith(fontWeight: FontWeight.w700),
                      ),
              ),
              const SizedBox(width: 16),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(meta.nombre, style: theme.textTheme.titleMedium),
                    const SizedBox(height: 2),
                    Text(
                      '${money(meta.aportado)} / ${money(meta.montoObjetivo)}',
                      style: theme.textTheme.bodyLarge?.copyWith(fontFeatures: kTabular, fontWeight: FontWeight.w600),
                    ),
                    Text(
                      meta.cumplida ? l.goalReached : l.goalVerified,
                      style: theme.textTheme.bodySmall?.copyWith(color: theme.colorScheme.onSurfaceVariant),
                    ),
                  ],
                ),
              ),
            ],
          ),
          if (meta.aportes.isNotEmpty) const SizedBox(height: 8),
          for (final aporte in meta.aportes)
            ListTile(
              dense: true,
              contentPadding: EdgeInsets.zero,
              title: Text('${money(aporte.monto)} · ${shortDate(context, aporte.fecha)}'),
              trailing: IconButton(
                tooltip: l.undoContribution,
                icon: const Icon(Icons.undo),
                onPressed: () async {
                  final ok = await guarded(context, () => api.deleteContribution(meta.id, aporte.id));
                  if (ok) refreshData(ref);
                },
              ),
            ),
          Row(
            mainAxisAlignment: MainAxisAlignment.end,
            children: [
              TextButton(
                onPressed: () async {
                  if (!await confirm(context, title: l.deleteGoalTitle, body: l.deleteGoalBody, action: l.delete)) {
                    return;
                  }
                  if (!context.mounted) return;
                  final ok = await guarded(context, () => api.deleteGoal(meta.id));
                  if (ok) refreshData(ref);
                },
                child: Text(l.delete),
              ),
              const SizedBox(width: 8),
              if (!meta.cumplida)
                FilledButton.tonal(
                  onPressed: () => showContributeDialog(context, ref, meta),
                  child: Text(l.setAside),
                ),
            ],
          ),
        ],
      ),
    );
    if (!_celebrar) return tarjeta;
    final tokens = context.tokens;
    return Stack(
      children: [
        tarjeta,
        Positioned.fill(
          child: ConfettiBurst(
            colors: [theme.colorScheme.primary, acento.color, tokens.challenges.color, tokens.coach.color],
          ),
        ),
      ],
    );
  }
}

class _Challenges extends ConsumerWidget {
  const _Challenges();

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final l = context.l;
    final theme = Theme.of(context);
    final retoAcento = context.tokens.challenges;
    final sugerencias = ref.watch(suggestionsProvider).value ?? const <ChallengeSuggestion>[];
    return AsyncView(
      value: ref.watch(challengesProvider),
      onRetry: () => ref.invalidate(challengesProvider),
      builder: (retos) {
        final activos = retos.where((r) => r.activo).toList();
        final pasados = retos.where((r) => !r.activo).toList();
        return ListView(
          padding: EdgeInsets.fromLTRB(16, 16, 16, 16 + bottomInset(context)),
          children: [
            if (activos.isEmpty && sugerencias.isEmpty) EmptyView(icon: Icons.emoji_events_outlined, text: l.noChallenges),
            for (final reto in activos) _ChallengeCard(reto: reto),
            if (sugerencias.isNotEmpty) ...[
              Padding(
                padding: const EdgeInsets.symmetric(vertical: 8),
                child: Text(l.suggestedChallenges, style: theme.textTheme.titleMedium),
              ),
              for (final s in sugerencias)
                SectionCard(
                  title: s.titulo,
                  color: retoAcento.container,
                  foreground: retoAcento.onContainer,
                  trailing: _Points(puntos: s.puntos),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(s.motivo, style: theme.textTheme.bodyMedium?.copyWith(color: retoAcento.onContainer)),
                      const SizedBox(height: 8),
                      Align(
                        alignment: Alignment.centerRight,
                        child: FilledButton(
                          style: FilledButton.styleFrom(backgroundColor: retoAcento.color),
                          onPressed: () async {
                            final ok = await guarded(
                              context,
                              () => ref.read(apiProvider).createChallenge(s.toPayload()),
                            );
                            if (ok) refreshData(ref);
                          },
                          child: Text(l.acceptChallenge),
                        ),
                      ),
                    ],
                  ),
                ),
            ],
            if (pasados.isNotEmpty) ...[
              Padding(
                padding: const EdgeInsets.symmetric(vertical: 8),
                child: Text(l.pastChallenges, style: theme.textTheme.titleMedium),
              ),
              for (final reto in pasados)
                ListTile(
                  contentPadding: EdgeInsets.zero,
                  leading: IconBadge(
                    icon: reto.estado == 'cumplido' ? Icons.verified : Icons.hourglass_disabled_outlined,
                    color: reto.estado == 'cumplido' ? null : theme.colorScheme.surfaceContainerHighest,
                    foreground: reto.estado == 'cumplido' ? null : theme.colorScheme.onSurfaceVariant,
                  ),
                  title: Text(reto.descripcion),
                  subtitle: Text(reto.estado == 'cumplido' ? l.challengeDone(reto.puntos) : l.challengeMissed),
                ),
            ],
          ],
        );
      },
    );
  }
}

class _ChallengeCard extends ConsumerWidget {
  const _ChallengeCard({required this.reto});

  final Challenge reto;

  String _valor(AppLocalizations l) => reto.esTope
      ? '${money(reto.valorActual)} / ${money(reto.objetivo)}'
      : '${reto.valorActual.round()} / ${reto.objetivo.round()}';

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final l = context.l;
    final acento = context.tokens.challenges;
    final pasos = reto.objetivo.round();
    return SectionCard(
      title: reto.descripcion,
      trailing: _Points(puntos: reto.puntos),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // Los retos de pocas veces (3 check-ins, 5 días) se ven como pasos; los de monto, como barra.
          if (!reto.esTope && pasos >= 2 && pasos <= 10) ...[
            Row(
              children: [
                Expanded(child: Text(l.challengeProgress, style: Theme.of(context).textTheme.bodyMedium)),
                Text(_valor(l), style: Theme.of(context).textTheme.bodyMedium?.copyWith(fontWeight: FontWeight.w600)),
              ],
            ),
            const SizedBox(height: 8),
            Row(
              children: [
                for (var i = 0; i < pasos; i++)
                  Expanded(
                    child: AnimatedContainer(
                      duration: motion(context, Duration(milliseconds: 300 + 80 * i)),
                      curve: kMotionCurve,
                      height: 10,
                      margin: EdgeInsets.only(right: i == pasos - 1 ? 0 : 4),
                      decoration: BoxDecoration(
                        color: i < reto.valorActual.round()
                            ? acento.color
                            : Theme.of(context).colorScheme.surfaceContainerHighest,
                        borderRadius: BorderRadius.circular(5),
                      ),
                    ),
                  ),
              ],
            ),
            const SizedBox(height: 12),
          ] else
            LabeledProgress(
              label: reto.esTope ? l.challengeSpentSoFar : l.challengeProgress,
              value: _valor(l),
              progress: reto.progreso,
              color: acento.color,
            ),
          Row(
            children: [
              Expanded(
                child: Text(
                  l.endsOn(shortDate(context, reto.fechaFin)),
                  style: Theme.of(context).textTheme.bodySmall,
                ),
              ),
              TextButton(
                onPressed: () async {
                  if (!await confirm(context, title: l.abandonTitle, body: l.abandonBody, action: l.abandon)) return;
                  if (!context.mounted) return;
                  final ok = await guarded(context, () => ref.read(apiProvider).abandonChallenge(reto.id));
                  if (ok) refreshData(ref);
                },
                child: Text(l.abandon),
              ),
            ],
          ),
        ],
      ),
    );
  }
}

/// Puntos que da un reto, como etiqueta.
class _Points extends StatelessWidget {
  const _Points({required this.puntos});

  final int puntos;

  @override
  Widget build(BuildContext context) {
    final acento = context.tokens.goals;
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
      decoration: BoxDecoration(color: acento.container, borderRadius: BorderRadius.circular(12)),
      child: Text(
        context.l.pointsShort(puntos),
        style: Theme.of(context).textTheme.labelMedium?.copyWith(color: acento.onContainer, fontWeight: FontWeight.w700),
      ),
    );
  }
}

class _Badges extends ConsumerWidget {
  const _Badges();

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final l = context.l;
    final theme = Theme.of(context);
    final insignias = ref.watch(gamificationProvider).value?.insignias ?? const <BadgeInfo>[];
    final obtenidas = insignias.where((i) => i.desbloqueada).length;
    return ListView(
      padding: EdgeInsets.fromLTRB(16, 16, 16, 16 + bottomInset(context)),
      children: [
        Padding(
          padding: const EdgeInsets.only(bottom: 12),
          child: Text(
            l.badgesCount(obtenidas, '${insignias.length}'),
            style: theme.textTheme.titleMedium,
          ),
        ),
        // Medallones: los obtenidos a color, los pendientes atenuados y con candado.
        Wrap(
          spacing: AppTokens.gap,
          runSpacing: AppTokens.gap,
          children: [
            for (final (i, insignia) in insignias.indexed)
              FractionallySizedBox(
                widthFactor: BentoRow.stacks(context) ? 1 : 0.5 - 0.02,
                child: FadeSlideIn(index: i, child: BadgeTile(insignia: insignia)),
              ),
          ],
        ),
      ],
    );
  }
}

/// Una insignia como tarjeta: medallón, nombre y cómo se consigue.
class BadgeTile extends StatelessWidget {
  const BadgeTile({super.key, required this.insignia});

  final BadgeInfo insignia;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final scheme = theme.colorScheme;
    final acento = context.tokens.goals;
    final lista = insignia.desbloqueada;
    return Semantics(
      label: lista ? null : context.l.badgeLocked,
      child: BentoTile(
        color: lista ? acento.container : null,
        child: SizedBox(
          width: double.infinity,
          child: Column(
            children: [
              Container(
                width: 64,
                height: 64,
                decoration: BoxDecoration(
                  shape: BoxShape.circle,
                  color: lista ? acento.color : scheme.surfaceContainerHighest,
                ),
                child: Icon(
                  lista ? Icons.military_tech : Icons.lock_outline,
                  size: 34,
                  color: lista ? acento.container : scheme.outline,
                ),
              ),
              const SizedBox(height: 10),
              // Un nombre largo de una sola palabra ("Autoconocimiento") se encoge en vez de cortarse.
              FittedBox(
                fit: BoxFit.scaleDown,
                child: Text(
                  insignia.nombre,
                  textAlign: TextAlign.center,
                  style: theme.textTheme.titleSmall?.copyWith(
                    color: lista ? acento.onContainer : scheme.onSurfaceVariant,
                  ),
                ),
              ),
              const SizedBox(height: 2),
              Text(
                insignia.descripcion,
                textAlign: TextAlign.center,
                style: theme.textTheme.bodySmall?.copyWith(
                  color: (lista ? acento.onContainer : scheme.onSurfaceVariant).withValues(alpha: 0.8),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
