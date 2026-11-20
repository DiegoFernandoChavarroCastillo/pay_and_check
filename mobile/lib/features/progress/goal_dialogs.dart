import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/format.dart';
import '../../core/native.dart';
import '../../core/theme.dart';
import '../../core/widgets.dart';
import '../../data/api.dart';
import '../../data/models.dart';
import '../../data/providers.dart';

/// Cuánto apartar por semana para juntar [objetivo] antes de [limite] (redondeado hacia arriba: mejor sobrar
/// que faltar). Es la misma cuenta que `plan_de_meta` del backend. Null sin fecha o con una fecha pasada.
double? aportePorSemana(double? objetivo, DateTime? limite, {DateTime? hoy}) {
  final desde = hoy ?? today();
  if (objetivo == null || objetivo <= 0 || limite == null || !limite.isAfter(desde)) return null;
  final dias = limite.difference(desde).inDays;
  final semanas = dias / 7 < 1 ? 1.0 : dias / 7;
  return (objetivo / semanas).ceilToDouble();
}

/// Crea una meta de ahorro. Con fecha límite muestra en vivo cuánto apartar por semana. El chat del coach la
/// abre ya llena ("Crear meta: Viaje") con [nombreInicial], [objetivoInicial] y [limiteInicial].
Future<void> showGoalDialog(
  BuildContext context,
  WidgetRef ref, {
  String? nombreInicial,
  double? objetivoInicial,
  DateTime? limiteInicial,
}) async {
  final form = GlobalKey<FormState>();
  final nombre = TextEditingController(text: nombreInicial ?? '');
  final objetivo = TextEditingController(text: objetivoInicial == null ? '' : objetivoInicial.round().toString());
  DateTime? limite = limiteInicial;
  final porSemanaDisponible = ref.read(summaryProvider).value?.disponiblePorSemana;

  final crear = await showDialog<bool>(
    context: context,
    builder: (context) => StatefulBuilder(
      builder: (context, setState) {
        final l = context.l;
        final porSemana = aportePorSemana(parseMoney(objetivo.text), limite);
        return AlertDialog(
          title: Text(l.newGoal),
          content: Form(
            key: form,
            child: SingleChildScrollView(
              child: Column(
                mainAxisSize: MainAxisSize.min,
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  TextFormField(
                    controller: nombre,
                    autofocus: nombreInicial == null,
                    textCapitalization: TextCapitalization.sentences,
                    decoration: InputDecoration(labelText: l.goalName, hintText: l.goalNameHint),
                    validator: (v) => (v ?? '').trim().isEmpty ? l.requiredField : null,
                  ),
                  const SizedBox(height: 12),
                  MoneyField(controller: objetivo, label: l.goalTarget, onChanged: (_) => setState(() {})),
                  const SizedBox(height: 12),
                  InkWell(
                    onTap: () async {
                      final hoy = today();
                      final elegida = await showDatePicker(
                        context: context,
                        initialDate: limite ?? hoy.add(const Duration(days: 90)),
                        firstDate: hoy.add(const Duration(days: 1)),
                        lastDate: DateTime(hoy.year + 5),
                      );
                      if (elegida != null) setState(() => limite = elegida);
                    },
                    child: InputDecorator(
                      decoration: InputDecoration(
                        labelText: l.goalDeadline,
                        suffixIcon: limite == null
                            ? const Icon(Icons.event_outlined)
                            : IconButton(
                                tooltip: l.clear,
                                icon: const Icon(Icons.close),
                                onPressed: () => setState(() => limite = null),
                              ),
                      ),
                      child: Text(limite == null ? l.goalNoDeadline : longDate(context, limite!)),
                    ),
                  ),
                  if (porSemana != null) ...[
                    const SizedBox(height: 12),
                    SectionCard(
                      color: context.tokens.goals.container,
                      child: Text(
                        porSemanaDisponible != null && porSemana > porSemanaDisponible
                            ? l.goalPerWeekTight(money(porSemana), money(porSemanaDisponible))
                            : l.goalPerWeek(money(porSemana)),
                        style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                              color: context.tokens.goals.onContainer,
                            ),
                      ),
                    ),
                  ],
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
    final ok = await guarded(
      context,
      () => ref.read(apiProvider).createGoal(nombre.text.trim(), parseMoney(objetivo.text)!, limite),
    );
    if (ok) {
      refreshData(ref);
      if (context.mounted) showSnack(context.l.goalCreated);
    }
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
            // Apartar aquí no mueve dinero real: el atajo abre la app de pago para guardarlo de verdad en un
            // bolsillo o meta. Pay&Check suma a Nequi y Daviplata, no compite con ellos.
            FutureBuilder<List<(String, String)>>(
              future: NativeBridge.paymentApps(),
              builder: (context, apps) {
                final lista = apps.data ?? const [];
                if (lista.isEmpty) return const SizedBox.shrink();
                return Padding(
                  padding: const EdgeInsets.only(top: 12),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(context.l.setAsideRealHint, style: Theme.of(context).textTheme.bodySmall),
                      const SizedBox(height: 8),
                      Wrap(
                        spacing: 8,
                        runSpacing: 4,
                        children: [
                          for (final (paquete, nombre) in lista)
                            OutlinedButton.icon(
                              onPressed: () => NativeBridge.openApp(paquete),
                              icon: const Icon(Icons.open_in_new, size: 18),
                              label: Text(context.l.openApp(nombre)),
                            ),
                        ],
                      ),
                    ],
                  ),
                );
              },
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
