import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/theme.dart';
import '../../core/widgets.dart';
import '../../data/api.dart';
import '../../data/models.dart';
import '../../data/providers.dart';

/// Apoyos de la universidad del convenio: becas, alimentación, acompañamiento, monitorías pagas. "Me interesa"
/// solo suma uno al total anónimo que ve la universidad; el contacto lo hace la persona.
class SupportScreen extends ConsumerWidget {
  const SupportScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final l = context.l;
    return Scaffold(
      appBar: AppBar(title: Text(l.supportTitle)),
      body: AsyncView<SupportList>(
        value: ref.watch(supportProvider),
        onRetry: () => ref.invalidate(supportProvider),
        builder: (s) {
          if (s.apoyos.isEmpty) {
            return Center(child: EmptyView(icon: Icons.school_outlined, text: l.supportEmpty));
          }
          return ListView(
            padding: const EdgeInsets.all(16),
            children: [
              Text(l.supportIntro(s.organizacion ?? ''), style: Theme.of(context).textTheme.bodyMedium),
              const SizedBox(height: 16),
              for (final a in s.apoyos) _ApoyoCard(apoyo: a),
              const SizedBox(height: 8),
              Text(l.supportPrivacy, style: Theme.of(context).textTheme.bodySmall),
            ],
          );
        },
      ),
    );
  }
}

IconData iconoDeApoyo(String tipo) => switch (tipo) {
      'beca' => Icons.workspace_premium_outlined,
      'alimentacion' => Icons.restaurant_outlined,
      'bienestar' => Icons.favorite_outline,
      'ingresos' => Icons.work_outline,
      _ => Icons.volunteer_activism_outlined,
    };

class _ApoyoCard extends ConsumerStatefulWidget {
  const _ApoyoCard({required this.apoyo});

  final SupportResource apoyo;

  @override
  ConsumerState<_ApoyoCard> createState() => _ApoyoCardState();
}

class _ApoyoCardState extends ConsumerState<_ApoyoCard> {
  bool _busy = false;

  Future<void> _meInteresa() async {
    final l = context.l;
    setState(() => _busy = true);
    final ok = await guarded(context, () => ref.read(apiProvider).supportInterest(widget.apoyo.id));
    if (!mounted) return;
    setState(() => _busy = false);
    if (ok) {
      ref.invalidate(supportProvider);
      showSnack(l.supportNoted);
    }
  }

  @override
  Widget build(BuildContext context) {
    final l = context.l;
    final theme = Theme.of(context);
    final a = widget.apoyo;
    final acento = context.tokens.goals;
    return Padding(
      padding: const EdgeInsets.only(bottom: 12),
      child: SectionCard(
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                IconBadge(icon: iconoDeApoyo(a.tipo), color: acento.container, foreground: acento.onContainer),
                const SizedBox(width: 12),
                Expanded(child: Text(a.titulo, style: theme.textTheme.titleMedium)),
              ],
            ),
            const SizedBox(height: 8),
            Text(a.descripcion, style: theme.textTheme.bodyMedium),
            const SizedBox(height: 8),
            // El contacto se puede copiar para escribir o ir a la oficina.
            InkWell(
              onTap: () {
                Clipboard.setData(ClipboardData(text: a.contacto));
                showSnack(l.copied);
              },
              child: Row(
                children: [
                  Icon(Icons.contact_support_outlined, size: 18, color: theme.colorScheme.primary),
                  const SizedBox(width: 8),
                  Expanded(child: Text(a.contacto, style: theme.textTheme.bodySmall)),
                  Icon(Icons.copy, size: 16, color: theme.colorScheme.onSurfaceVariant),
                ],
              ),
            ),
            const SizedBox(height: 12),
            Align(
              alignment: Alignment.centerRight,
              child: a.meInteresa
                  ? Chip(avatar: const Icon(Icons.check, size: 18), label: Text(l.supportInterested))
                  : FilledButton.tonal(onPressed: _busy ? null : _meInteresa, child: Text(l.supportInterest)),
            ),
          ],
        ),
      ),
    );
  }
}

/// Tarjeta de Inicio que pone los apoyos a la vista cuando las cifras lo justifican (el presupuesto no
/// alcanza o hay varios días de ansiedad). Sin motivo no aparece: no es publicidad de la universidad.
class SupportSuggestionCard extends ConsumerWidget {
  const SupportSuggestionCard({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final s = ref.watch(supportProvider).value;
    if (s == null || s.motivo == null || s.apoyos.isEmpty) return const SizedBox.shrink();
    final l = context.l;
    final acento = context.tokens.coach;
    return Padding(
      padding: const EdgeInsets.only(bottom: AppTokens.gap),
      child: SectionCard(
        color: acento.container,
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Icon(Icons.volunteer_activism_outlined, color: acento.onContainer),
                const SizedBox(width: 12),
                Expanded(
                  child: Text(
                    s.motivo == 'estres' ? l.supportSuggestStress : l.supportSuggestRisk,
                    style: Theme.of(context).textTheme.bodyMedium?.copyWith(color: acento.onContainer),
                  ),
                ),
              ],
            ),
            const SizedBox(height: 12),
            FilledButton.tonal(
              onPressed: () => Navigator.push(context, MaterialPageRoute<void>(builder: (_) => const SupportScreen())),
              child: Text(l.supportSee(s.organizacion ?? '')),
            ),
          ],
        ),
      ),
    );
  }
}
