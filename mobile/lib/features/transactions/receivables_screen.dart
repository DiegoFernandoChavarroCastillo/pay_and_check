import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:share_plus/share_plus.dart';

import '../../core/format.dart';
import '../../core/theme.dart';
import '../../core/widgets.dart';
import '../../data/api.dart';
import '../../data/models.dart';
import '../../data/providers.dart';
import '../../l10n/gen/app_localizations.dart';

/// Envía el cobro de una vaca por WhatsApp (o lo que elija la persona): "Juan, la pizza salió a $21.000 por
/// cabeza". Quien lo recibe conoce la app por ahí.
Future<void> compartirCobro(BuildContext context, {required String persona, required String descripcion,
    required double monto}) async {
  final l = context.l;
  await SharePlus.instance.share(ShareParams(text: l.receivableMessage(persona, descripcion, money(monto))));
}

/// El mensaje del grupo justo después de crear la vaca: "la pizza salió a $21.000 por persona".
Future<void> compartirCobroGrupal(AppLocalizations l, {required String descripcion, required double parte}) async {
  try {
    await SharePlus.instance.share(ShareParams(text: l.splitShareMessage(descripcion, money(parte))));
  } catch (_) {}
}

/// Lo que le deben a la persona por las vacas que pagó.
class ReceivablesScreen extends ConsumerWidget {
  const ReceivablesScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final l = context.l;
    final theme = Theme.of(context);
    return Scaffold(
      appBar: AppBar(title: Text(l.receivablesTitle)),
      body: AsyncView<ReceivableSummary>(
        value: ref.watch(receivablesProvider),
        onRetry: () => ref.invalidate(receivablesProvider),
        builder: (r) => r.pendientes.isEmpty
            ? Center(child: EmptyView(icon: Icons.handshake_outlined, text: l.receivablesEmpty))
            : ListView(
                padding: const EdgeInsets.all(16),
                children: [
                  Text(l.receivablesTotal(money(r.total)), style: theme.textTheme.titleLarge),
                  const SizedBox(height: 4),
                  Text(l.receivablesHint, style: theme.textTheme.bodySmall),
                  const SizedBox(height: 16),
                  for (final c in r.pendientes)
                    Padding(
                      padding: const EdgeInsets.only(bottom: 8),
                      child: SectionCard(
                        child: Row(
                          children: [
                            Expanded(
                              child: Column(
                                crossAxisAlignment: CrossAxisAlignment.start,
                                children: [
                                  Text(c.persona, style: theme.textTheme.titleMedium),
                                  Text('${c.descripcion} · ${shortDate(context, c.fecha)}',
                                      style: theme.textTheme.bodySmall),
                                ],
                              ),
                            ),
                            Text(money(c.monto), style: theme.textTheme.titleMedium),
                            IconButton(
                              tooltip: l.receivableRemind,
                              icon: const Icon(Icons.send_outlined),
                              onPressed: () =>
                                  compartirCobro(context, persona: c.persona, descripcion: c.descripcion, monto: c.monto),
                            ),
                            IconButton(
                              tooltip: l.receivablePaid,
                              icon: Icon(Icons.check_circle_outline, color: context.tokens.income.color),
                              onPressed: () async {
                                if (await guarded(context, () => ref.read(apiProvider).receivablePaid(c.id))) {
                                  ref.invalidate(receivablesProvider);
                                  showSnack(l.receivablePaidSnack(c.persona));
                                }
                              },
                            ),
                          ],
                        ),
                      ),
                    ),
                ],
              ),
      ),
    );
  }
}

/// Tarjeta de Inicio: "Te deben $63.000". Solo aparece si hay cobros pendientes.
class ReceivablesCard extends ConsumerWidget {
  const ReceivablesCard({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final r = ref.watch(receivablesProvider).value;
    if (r == null || r.pendientes.isEmpty) return const SizedBox.shrink();
    final l = context.l;
    final acento = context.tokens.income;
    return Padding(
      padding: const EdgeInsets.only(bottom: AppTokens.gap),
      child: Material(
        color: acento.container,
        borderRadius: BorderRadius.circular(AppTokens.radius),
        child: InkWell(
          borderRadius: BorderRadius.circular(AppTokens.radius),
          onTap: () => Navigator.push(context, MaterialPageRoute<void>(builder: (_) => const ReceivablesScreen())),
          child: Padding(
            padding: const EdgeInsets.all(16),
            child: Row(
              children: [
                Icon(Icons.handshake_outlined, color: acento.onContainer),
                const SizedBox(width: 12),
                Expanded(
                  child: Text(
                    l.receivablesCard(money(r.total), r.pendientes.length),
                    style: Theme.of(context).textTheme.bodyLarge?.copyWith(color: acento.onContainer),
                  ),
                ),
                Icon(Icons.chevron_right, color: acento.onContainer),
              ],
            ),
          ),
        ),
      ),
    );
  }
}
