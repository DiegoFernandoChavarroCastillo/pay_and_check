import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/format.dart';
import '../../core/widgets.dart';
import '../../data/api.dart';
import '../../data/models.dart';
import '../../data/providers.dart';
import '../../l10n/gen/app_localizations.dart';
import 'goal_dialogs.dart';

/// Progreso: nivel y puntos, metas de ahorro, retos e insignias.
class ProgressScreen extends ConsumerWidget {
  const ProgressScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final l = context.l;
    return DefaultTabController(
      length: 3,
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
          TabBar(tabs: [Tab(text: l.goals), Tab(text: l.challenges), Tab(text: l.badges)]),
          const Expanded(child: TabBarView(children: [_Goals(), _Challenges(), _Badges()])),
        ],
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
    final siguiente = perfil.puntosSiguiente;
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(
          children: [
            Expanded(
              child: Text(
                l.levelTitle(perfil.nivelNumero, perfil.nivelNombre),
                style: theme.textTheme.headlineSmall,
              ),
            ),
            Chip(
              avatar: const Icon(Icons.local_fire_department, size: 18),
              label: Text(l.streakDays(perfil.rachaActual)),
            ),
          ],
        ),
        const SizedBox(height: 8),
        LabeledProgress(
          label: l.pointsTotal(perfil.puntos),
          value: siguiente == null ? l.maxLevel : l.pointsToNext(siguiente - perfil.puntos),
          progress: perfil.progresoNivel,
        ),
        Row(
          children: [
            _Metric(label: l.metricSavings, value: _pct(perfil.ratioAhorro), tooltip: l.metricSavingsHint),
            _Metric(label: l.metricConsistency, value: _pct(perfil.consistencia), tooltip: l.metricConsistencyHint),
            _Metric(
              label: l.metricImprovement,
              value: perfil.mejoraMensual == null
                  ? '—'
                  : '${perfil.mejoraMensual! >= 0 ? '+' : ''}${(perfil.mejoraMensual! * 100).round()} pts',
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
    return Expanded(
      child: Tooltip(
        message: tooltip,
        triggerMode: TooltipTriggerMode.tap,
        showDuration: const Duration(seconds: 5),
        child: Padding(
          padding: const EdgeInsets.only(bottom: 8),
          child: Column(
            children: [
              Text(value, style: theme.textTheme.titleLarge?.copyWith(fontWeight: FontWeight.w600)),
              Text(label, style: theme.textTheme.labelSmall, textAlign: TextAlign.center),
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
        padding: const EdgeInsets.all(16),
        children: [
          if (metas.isEmpty) EmptyView(icon: Icons.flag_outlined, text: l.noGoals),
          for (final meta in metas) _GoalCard(meta: meta),
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

class _GoalCard extends ConsumerWidget {
  const _GoalCard({required this.meta});

  final Goal meta;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final l = context.l;
    final api = ref.read(apiProvider);
    return SectionCard(
      title: meta.nombre,
      trailing: meta.cumplida ? Chip(avatar: const Icon(Icons.verified, size: 18), label: Text(l.goalReached)) : null,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          LabeledProgress(
            label: l.goalVerified,
            value: '${money(meta.aportado)} / ${money(meta.montoObjetivo)}',
            progress: meta.progreso,
          ),
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
  }
}

class _Challenges extends ConsumerWidget {
  const _Challenges();

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final l = context.l;
    final theme = Theme.of(context);
    final sugerencias = ref.watch(suggestionsProvider).value ?? const <ChallengeSuggestion>[];
    return AsyncView(
      value: ref.watch(challengesProvider),
      onRetry: () => ref.invalidate(challengesProvider),
      builder: (retos) {
        final activos = retos.where((r) => r.activo).toList();
        final pasados = retos.where((r) => !r.activo).toList();
        return ListView(
          padding: const EdgeInsets.all(16),
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
                  trailing: Text(l.pointsShort(s.puntos), style: theme.textTheme.labelLarge),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(s.motivo),
                      Align(
                        alignment: Alignment.centerRight,
                        child: FilledButton.tonal(
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
                  leading: Icon(reto.estado == 'cumplido' ? Icons.verified : Icons.hourglass_disabled_outlined),
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
    return SectionCard(
      title: reto.descripcion,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          LabeledProgress(
            label: reto.esTope ? l.challengeSpentSoFar : l.challengeProgress,
            value: _valor(l),
            progress: reto.progreso,
          ),
          Row(
            children: [
              Expanded(
                child: Text(
                  '${l.endsOn(shortDate(context, reto.fechaFin))} · ${l.pointsShort(reto.puntos)}',
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

class _Badges extends ConsumerWidget {
  const _Badges();

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final theme = Theme.of(context);
    final insignias = ref.watch(gamificationProvider).value?.insignias ?? const <BadgeInfo>[];
    return ListView(
      padding: const EdgeInsets.symmetric(vertical: 8),
      children: [
        for (final insignia in insignias)
          ListTile(
            leading: Icon(
              insignia.desbloqueada ? Icons.military_tech : Icons.lock_outline,
              size: 32,
              color: insignia.desbloqueada ? theme.colorScheme.primary : theme.colorScheme.outline,
            ),
            title: Text(insignia.nombre),
            subtitle: Text(insignia.descripcion),
            enabled: insignia.desbloqueada,
          ),
      ],
    );
  }
}
