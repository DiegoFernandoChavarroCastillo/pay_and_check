import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/format.dart';
import '../../core/motion.dart';
import '../../core/widgets.dart';
import '../../data/api.dart';
import '../../data/models.dart';
import '../../data/providers.dart';
import '../../l10n/gen/app_localizations.dart';
import '../progress/goal_dialogs.dart';

const moodEmojis = {
  'ansioso': '😰',
  'preocupado': '😟',
  'neutral': '😐',
  'tranquilo': '🙂',
  'confiado': '😄',
};

String moodLabel(AppLocalizations l, String animo) => switch (animo) {
      'ansioso' => l.moodAnxious,
      'preocupado' => l.moodWorried,
      'tranquilo' => l.moodCalm,
      'confiado' => l.moodConfident,
      _ => l.moodNeutral,
    };

/// Check-in diario: un toque para decir cómo te sientes con tu dinero hoy.
class CheckinCard extends ConsumerWidget {
  const CheckinCard({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final l = context.l;
    final hoy = today();
    final checkins = ref.watch(checkinsProvider).value ?? const <Checkin>[];
    final deHoy = checkins.where((c) => c.fecha == hoy).firstOrNull;

    Future<void> registrar(String animo) async {
      final ok = await guarded(context, () => ref.read(apiProvider).checkin(animo));
      if (ok) refreshData(ref);
    }

    return SectionCard(
      title: deHoy == null ? l.checkinQuestion : l.checkinDone,
      child: Row(
        mainAxisAlignment: MainAxisAlignment.spaceBetween,
        children: [
          for (final animo in moodEmojis.keys)
            Semantics(
              button: true,
              selected: deHoy?.animo == animo,
              label: moodLabel(l, animo),
              child: InkWell(
                borderRadius: BorderRadius.circular(16),
                onTap: () => registrar(animo),
                child: AnimatedContainer(
                  duration: motion(context, const Duration(milliseconds: 250)),
                  width: 56,
                  padding: const EdgeInsets.symmetric(vertical: 8),
                  decoration: BoxDecoration(
                    borderRadius: BorderRadius.circular(16),
                    color: deHoy?.animo == animo
                        ? Theme.of(context).colorScheme.primaryContainer
                        : Theme.of(context).colorScheme.primaryContainer.withValues(alpha: 0),
                  ),
                  child: Column(
                    children: [
                      // El ánimo elegido crece con un rebote leve.
                      AnimatedScale(
                        scale: deHoy?.animo == animo ? 1.2 : 1,
                        duration: motion(context),
                        curve: Curves.easeOutBack,
                        child: ExcludeSemantics(child: Text(moodEmojis[animo]!, style: const TextStyle(fontSize: 28))),
                      ),
                      const SizedBox(height: 4),
                      ExcludeSemantics(
                        child: Text(
                          moodLabel(l, animo),
                          style: Theme.of(context).textTheme.labelSmall,
                          overflow: TextOverflow.ellipsis,
                        ),
                      ),
                    ],
                  ),
                ),
              ),
            ),
        ],
      ),
    );
  }
}

/// Un consejo del coach con su acción de un tap. La acción solo se ejecuta
/// cuando el usuario la toca: el coach propone, la persona decide.
class InsightCard extends ConsumerStatefulWidget {
  const InsightCard({super.key, required this.insight});

  final Insight insight;

  @override
  ConsumerState<InsightCard> createState() => _InsightCardState();
}

class _InsightCardState extends ConsumerState<InsightCard> {
  bool _busy = false;
  bool _done = false;

  Future<void> _ejecutar(InsightAction accion) async {
    final api = ref.read(apiProvider);
    final l = context.l;

    if (accion.tipo == 'crear_meta') {
      await showGoalDialog(context, ref);
      return;
    }

    setState(() => _busy = true);
    final ok = await guarded(context, () async {
      switch (accion.tipo) {
        case 'crear_reto':
          await api.createChallenge(accion.payload);
        case 'poner_limite':
          await api.updateCategory(accion.payload['category_id'] as int, {'limite': accion.payload['limite']});
        case 'apartar_meta':
          await api.contribute(
            accion.payload['goal_id'] as int,
            double.parse(accion.payload['monto'].toString()),
          );
      }
    });
    if (!mounted) return;
    setState(() {
      _busy = false;
      _done = ok;
    });
    if (ok) {
      refreshData(ref);
      showSnack(l.actionDone);
    }
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final insight = widget.insight;
    final accion = insight.accion;
    return SectionCard(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Icon(Icons.auto_awesome, color: theme.colorScheme.primary),
              const SizedBox(width: 12),
              Expanded(child: Text(insight.mensaje, style: theme.textTheme.bodyLarge)),
            ],
          ),
          // Explicabilidad: el dato en que se basa el consejo, si la IA lo reescribió.
          if (insight.mensaje != insight.descripcion)
            Padding(
              padding: const EdgeInsets.only(top: 8, left: 36),
              child: Text(
                '${context.l.whyThis} ${insight.descripcion}',
                style: theme.textTheme.bodySmall?.copyWith(color: theme.colorScheme.onSurfaceVariant),
              ),
            ),
          if (accion != null) ...[
            const SizedBox(height: 12),
            Align(
              alignment: Alignment.centerRight,
              child: FilledButton.tonalIcon(
                onPressed: _busy || _done ? null : () => _ejecutar(accion),
                icon: Icon(_done ? Icons.check : Icons.bolt),
                label: Text(_done ? context.l.actionDone : accion.etiqueta),
              ),
            ),
          ],
        ],
      ),
    );
  }
}
