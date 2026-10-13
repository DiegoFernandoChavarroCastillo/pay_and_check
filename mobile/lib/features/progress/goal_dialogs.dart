import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/format.dart';
import '../../core/widgets.dart';
import '../../data/api.dart';
import '../../data/models.dart';
import '../../data/providers.dart';

/// Crea una meta de ahorro.
Future<void> showGoalDialog(BuildContext context, WidgetRef ref) async {
  final form = GlobalKey<FormState>();
  final nombre = TextEditingController();
  final objetivo = TextEditingController();

  final crear = await showDialog<bool>(
    context: context,
    builder: (context) => AlertDialog(
      title: Text(context.l.newGoal),
      content: Form(
        key: form,
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            TextFormField(
              controller: nombre,
              autofocus: true,
              textCapitalization: TextCapitalization.sentences,
              decoration: InputDecoration(labelText: context.l.goalName, hintText: context.l.goalNameHint),
              validator: (v) => (v ?? '').trim().isEmpty ? context.l.requiredField : null,
            ),
            const SizedBox(height: 12),
            MoneyField(controller: objetivo, label: context.l.goalTarget),
          ],
        ),
      ),
      actions: [
        TextButton(onPressed: () => Navigator.pop(context, false), child: Text(context.l.cancel)),
        FilledButton(
          onPressed: () {
            if (form.currentState!.validate()) Navigator.pop(context, true);
          },
          child: Text(context.l.create),
        ),
      ],
    ),
  );

  if (crear == true && context.mounted) {
    final ok = await guarded(
      context,
      () => ref.read(apiProvider).createGoal(nombre.text.trim(), parseMoney(objetivo.text)!, null),
    );
    if (ok) refreshData(ref);
  }
}

/// Aparta dinero del disponible hacia una meta.
Future<void> showContributeDialog(BuildContext context, WidgetRef ref, Goal goal) async {
  final form = GlobalKey<FormState>();
  final monto = TextEditingController();
  final disponible = ref.read(summaryProvider).value?.disponibleTotal;

  final apartar = await showDialog<bool>(
    context: context,
    builder: (context) => AlertDialog(
      title: Text(context.l.setAsideFor(goal.nombre)),
      content: Form(
        key: form,
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            MoneyField(controller: monto, label: context.l.amount, autofocus: true),
            const SizedBox(height: 12),
            Text(
              disponible == null ? context.l.setAsideHint : context.l.setAsideAvailable(money(disponible)),
              style: Theme.of(context).textTheme.bodySmall,
            ),
          ],
        ),
      ),
      actions: [
        TextButton(onPressed: () => Navigator.pop(context, false), child: Text(context.l.cancel)),
        FilledButton(
          onPressed: () {
            if (form.currentState!.validate()) Navigator.pop(context, true);
          },
          child: Text(context.l.setAside),
        ),
      ],
    ),
  );

  if (apartar == true && context.mounted) {
    final ok = await guarded(context, () => ref.read(apiProvider).contribute(goal.id, parseMoney(monto.text)!));
    if (ok) refreshData(ref);
  }
}
