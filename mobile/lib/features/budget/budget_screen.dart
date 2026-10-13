import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/format.dart';
import '../../core/widgets.dart';
import '../../data/api.dart';
import '../../data/models.dart';
import '../../data/providers.dart';
import '../../data/session.dart';
import '../../l10n/gen/app_localizations.dart';

const coachTones = ['motivador', 'directo', 'humoristico', 'minimalista'];

String toneLabel(AppLocalizations l, String tono) => switch (tono) {
      'directo' => l.toneDirect,
      'humoristico' => l.toneHumorous,
      'minimalista' => l.toneMinimal,
      _ => l.toneMotivating,
    };

/// Crea el presupuesto del periodo o edita el activo. En el primer uso
/// (`onboarding`) también pregunta el estilo del coach.
class BudgetScreen extends ConsumerStatefulWidget {
  const BudgetScreen({super.key, this.current, this.onboarding = false});

  final Budget? current;
  final bool onboarding;

  @override
  ConsumerState<BudgetScreen> createState() => _BudgetScreenState();
}

class _BudgetScreenState extends ConsumerState<BudgetScreen> {
  final _form = GlobalKey<FormState>();
  late final _monto = TextEditingController(text: widget.current?.montoTotal.round().toString() ?? '');
  late DateTime _inicio = widget.current?.fechaInicio ?? today();
  late DateTime _fin = widget.current?.fechaFin ?? today().add(const Duration(days: 120));
  late String _tono = ref.read(sessionProvider).value?.coachTone ?? coachTones.first;
  bool _saving = false;

  @override
  void dispose() {
    _monto.dispose();
    super.dispose();
  }

  Future<void> _save() async {
    final l = context.l;
    if (!_form.currentState!.validate()) return;
    if (!_fin.isAfter(_inicio)) {
      showSnack(l.budgetDatesError);
      return;
    }

    setState(() => _saving = true);
    final api = ref.read(apiProvider);
    final monto = parseMoney(_monto.text)!;
    final ok = await guarded(context, () async {
      final actual = widget.current;
      if (actual == null) {
        await api.createBudget(monto, _inicio, _fin);
      } else {
        await api.updateBudget(actual.id, monto, _inicio, _fin);
      }
      if (widget.onboarding) await ref.read(sessionProvider.notifier).updateProfile({'coach_tone': _tono});
    });
    if (!mounted) return;
    setState(() => _saving = false);
    if (ok) {
      refreshData(ref);
      Navigator.pop(context);
    }
  }

  @override
  Widget build(BuildContext context) {
    final l = context.l;
    return Scaffold(
      appBar: AppBar(title: Text(widget.current == null ? l.createBudget : l.editBudget)),
      body: Form(
        key: _form,
        child: ListView(
          padding: const EdgeInsets.all(16),
          children: [
            Text(l.budgetExplain, style: Theme.of(context).textTheme.bodyLarge),
            const SizedBox(height: 20),
            MoneyField(controller: _monto, label: l.budgetAmount, autofocus: widget.current == null),
            const SizedBox(height: 12),
            DateField(label: l.startDate, value: _inicio, onChanged: (d) => setState(() => _inicio = d)),
            const SizedBox(height: 12),
            DateField(label: l.endDate, value: _fin, onChanged: (d) => setState(() => _fin = d)),
            if (widget.onboarding) ...[
              const SizedBox(height: 24),
              Text(l.coachToneQuestion, style: Theme.of(context).textTheme.titleMedium),
              const SizedBox(height: 8),
              Wrap(
                spacing: 8,
                children: [
                  for (final tono in coachTones)
                    ChoiceChip(
                      label: Text(toneLabel(l, tono)),
                      selected: _tono == tono,
                      onSelected: (_) => setState(() => _tono = tono),
                    ),
                ],
              ),
            ],
            const SizedBox(height: 24),
            SaveButton(saving: _saving, onPressed: _save),
          ],
        ),
      ),
    );
  }
}
