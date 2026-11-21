import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/format.dart';
import '../../core/theme.dart';
import '../../core/widgets.dart';
import '../../data/api.dart';
import '../../data/models.dart';
import '../../data/providers.dart';
import '../../l10n/gen/app_localizations.dart';
import '../transactions/expense_form_screen.dart';

/// Gastos grandes que vienen (matrícula, libros, regalos…): "¿me alcanza?" llevado al semestre. Por cada uno,
/// cuánto apartar por semana y si el ritmo de hoy lo permite.
class PlannedScreen extends ConsumerWidget {
  const PlannedScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final l = context.l;
    return Scaffold(
      appBar: AppBar(title: Text(l.plannedTitle)),
      floatingActionButton: FloatingActionButton.extended(
        onPressed: () => showPlannedDialog(context, ref),
        icon: const Icon(Icons.add),
        label: Text(l.plannedAdd),
      ),
      body: AsyncView<List<PlannedExpense>>(
        value: ref.watch(plannedProvider),
        onRetry: () => ref.invalidate(plannedProvider),
        builder: (lista) => lista.isEmpty
            ? Center(child: EmptyView(icon: Icons.event_note_outlined, text: l.plannedEmpty))
            : ListView(
                padding: const EdgeInsets.fromLTRB(16, 16, 16, 96),
                children: [for (final p in lista) _PrevistoCard(p: p)],
              ),
      ),
    );
  }
}

class _PrevistoCard extends ConsumerWidget {
  const _PrevistoCard({required this.p});

  final PlannedExpense p;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final l = context.l;
    final theme = Theme.of(context);
    final ajustado = (p.margenSemanal ?? 0) < 0;
    final acento = ajustado ? context.tokens.goals : context.tokens.income;
    return Padding(
      padding: const EdgeInsets.only(bottom: 12),
      child: SectionCard(
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Expanded(child: Text(p.descripcion, style: theme.textTheme.titleMedium)),
                Text(money(p.monto), style: theme.textTheme.titleMedium),
              ],
            ),
            Text(
              '${longDate(context, p.fecha)} · ${l.plannedInDays(p.dias ?? 0)}',
              style: theme.textTheme.bodySmall,
            ),
            if (p.porSemana != null) ...[
              const SizedBox(height: 10),
              Container(
                width: double.infinity,
                padding: const EdgeInsets.all(12),
                decoration: BoxDecoration(color: acento.container, borderRadius: BorderRadius.circular(12)),
                child: Text(
                  ajustado ? l.plannedTight(money(p.porSemana!)) : l.plannedOk(money(p.porSemana!)),
                  style: theme.textTheme.bodyMedium?.copyWith(color: acento.onContainer),
                ),
              ),
            ],
            const SizedBox(height: 8),
            Row(
              mainAxisAlignment: MainAxisAlignment.end,
              children: [
                TextButton(
                  onPressed: () async {
                    if (await guarded(context, () => ref.read(apiProvider).deletePlanned(p.id))) {
                      ref.invalidate(plannedProvider);
                    }
                  },
                  child: Text(l.delete),
                ),
                const SizedBox(width: 8),
                FilledButton.tonal(
                  onPressed: () => _yaLoPague(context, ref, p),
                  child: Text(l.plannedDone),
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }
}

/// Plantillas típicas de un estudiante: un toque llena la descripción.
List<String> plantillasPrevistas(AppLocalizations l) =>
    [l.plannedTuition, l.plannedBooks, l.plannedTrip, l.plannedGifts, l.plannedRent];

Future<void> showPlannedDialog(BuildContext context, WidgetRef ref) async {
  final form = GlobalKey<FormState>();
  final descripcion = TextEditingController();
  final monto = TextEditingController();
  var fecha = today().add(const Duration(days: 30));

  final crear = await showDialog<bool>(
    context: context,
    builder: (context) => StatefulBuilder(
      builder: (context, setState) {
        final l = context.l;
        return AlertDialog(
          title: Text(l.plannedAdd),
          content: Form(
            key: form,
            child: SingleChildScrollView(
              child: Column(
                mainAxisSize: MainAxisSize.min,
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  Wrap(
                    spacing: 6,
                    runSpacing: 4,
                    children: [
                      for (final p in plantillasPrevistas(l))
                        ActionChip(label: Text(p), onPressed: () => setState(() => descripcion.text = p)),
                    ],
                  ),
                  const SizedBox(height: 8),
                  TextFormField(
                    controller: descripcion,
                    textCapitalization: TextCapitalization.sentences,
                    decoration: InputDecoration(labelText: l.description),
                    validator: (v) => (v ?? '').trim().isEmpty ? l.requiredField : null,
                  ),
                  const SizedBox(height: 12),
                  MoneyField(controller: monto, label: l.amount),
                  const SizedBox(height: 12),
                  DateField(label: l.date, value: fecha, onChanged: (d) => setState(() => fecha = d)),
                ],
              ),
            ),
          ),
          actions: [
            TextButton(onPressed: () => Navigator.pop(context, false), child: Text(l.cancel)),
            FilledButton(
              onPressed: () {
                if (form.currentState!.validate()) Navigator.pop(context, true);
              },
              child: Text(l.create),
            ),
          ],
        );
      },
    ),
  );
  if (crear == true && context.mounted) {
    final valor = parseMoney(monto.text);
    if (valor == null) return;
    final ok = await guarded(
      context,
      () => ref.read(apiProvider).createPlanned(descripcion.text.trim(), valor, fecha),
    );
    if (ok) {
      ref
        ..invalidate(plannedProvider)
        ..invalidate(insightsProvider);
    }
  }
}


/// "Ya lo pagué": nada se registra sin que la persona lo confirme (la misma regla del registro por texto y de los
/// SMS). Antes el backend creaba el gasto solo y, si la persona ya lo había registrado a mano, quedaba dos veces.
Future<void> _yaLoPague(BuildContext context, WidgetRef ref, PlannedExpense p) async {
  final l = context.l;
  final eleccion = await showDialog<String>(
    context: context,
    builder: (ctx) => AlertDialog(
      title: Text(l.plannedDoneTitle),
      content: Text(l.plannedDoneBody(money(p.monto))),
      actions: [
        TextButton(onPressed: () => Navigator.pop(ctx), child: Text(l.cancel)),
        TextButton(onPressed: () => Navigator.pop(ctx, 'ya'), child: Text(l.plannedDoneAlready)),
        FilledButton(onPressed: () => Navigator.pop(ctx, 'registrar'), child: Text(l.plannedDoneRegister)),
      ],
    ),
  );
  if (eleccion == null || !context.mounted) return;

  if (eleccion == 'registrar') {
    final guardado = await Navigator.push<bool>(
      context,
      MaterialPageRoute(
        builder: (_) => ExpenseFormScreen(
          draft: ExpenseDraft(monto: p.monto, descripcion: p.descripcion, fecha: today()),
        ),
      ),
    );
    if (guardado != true || !context.mounted) return;
  }

  if (await guarded(context, () => ref.read(apiProvider).plannedDone(p.id))) {
    ref.invalidate(plannedProvider);
    refreshData(ref);
    showSnack(l.plannedDoneSnack);
  }
}
