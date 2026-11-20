import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:intl/intl.dart';

import '../../core/format.dart';
import '../../core/motion.dart';
import '../../core/theme.dart';
import '../../core/widgets.dart';
import '../../data/api.dart';
import '../../data/models.dart';
import '../transactions/expense_form_screen.dart';

/// "¿Me alcanza?": antes de comprar, cómo quedaría el número del día (y la meta) si se gastara ese monto.
/// La cuenta la hace el backend (`POST /budgets/active/simulate`); no guarda nada ni usa IA.
void showAffordSheet(BuildContext context) {
  showModalBottomSheet<void>(
    context: context,
    showDragHandle: true,
    isScrollControlled: true,
    builder: (_) => const _AffordSheet(),
  );
}

class _AffordSheet extends ConsumerStatefulWidget {
  const _AffordSheet();

  @override
  ConsumerState<_AffordSheet> createState() => _AffordSheetState();
}

class _AffordSheetState extends ConsumerState<_AffordSheet> {
  final _monto = TextEditingController();
  // "A cuotas": cuántas y la tasa efectiva anual que dice la entidad.
  final _cuotas = TextEditingController(text: '12');
  final _tasa = TextEditingController();
  bool _aCuotas = false;
  AffordCheck? _resultado;
  CreditCheck? _credito;
  bool _busy = false;

  @override
  void dispose() {
    _monto.dispose();
    _cuotas.dispose();
    _tasa.dispose();
    super.dispose();
  }

  Future<void> _simular() async {
    final monto = parseMoney(_monto.text);
    if (monto == null || monto <= 0) return;
    final cuotas = int.tryParse(_cuotas.text.trim());
    final tasa = double.tryParse(_tasa.text.trim().replaceAll(',', '.'));
    if (_aCuotas && (cuotas == null || cuotas < 1 || tasa == null)) return;
    FocusScope.of(context).unfocus();
    setState(() => _busy = true);
    final api = ref.read(apiProvider);
    AffordCheck? resultado;
    CreditCheck? credito;
    await guarded(context, () async {
      if (_aCuotas) {
        credito = await api.simulateCredit(monto, cuotas!, tasa!);
      } else {
        resultado = await api.simulate(monto);
      }
    });
    if (!mounted) return;
    setState(() {
      _busy = false;
      _resultado = _aCuotas ? null : resultado ?? _resultado;
      _credito = _aCuotas ? credito ?? _credito : null;
    });
  }

  void _registrar(AffordCheck r) {
    Navigator.pop(context);
    Navigator.push(
      context,
      MaterialPageRoute<void>(builder: (_) => ExpenseFormScreen(draft: ExpenseDraft(monto: r.monto))),
    );
  }

  @override
  Widget build(BuildContext context) {
    final l = context.l;
    final theme = Theme.of(context);
    final r = _resultado;
    return SafeArea(
      child: Padding(
        padding: EdgeInsets.fromLTRB(16, 0, 16, 16 + MediaQuery.viewInsetsOf(context).bottom),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Text(l.affordTitle, style: theme.textTheme.titleLarge),
            const SizedBox(height: 4),
            Text(l.affordHint, style: theme.textTheme.bodyMedium?.copyWith(color: theme.colorScheme.onSurfaceVariant)),
            const SizedBox(height: 16),
            // De contado o a cuotas: el crédito también se decide antes.
            SegmentedButton<bool>(
              segments: [
                ButtonSegment(value: false, label: Text(l.affordCash), icon: const Icon(Icons.payments_outlined)),
                ButtonSegment(value: true, label: Text(l.affordCredit), icon: const Icon(Icons.credit_card)),
              ],
              selected: {_aCuotas},
              onSelectionChanged: (s) => setState(() {
                _aCuotas = s.first;
                _resultado = null;
                _credito = null;
              }),
            ),
            const SizedBox(height: 12),
            MoneyField(controller: _monto, label: l.amount, autofocus: true, hero: true),
            if (_aCuotas) ...[
              const SizedBox(height: 12),
              Row(
                children: [
                  Expanded(
                    child: TextField(
                      controller: _cuotas,
                      keyboardType: TextInputType.number,
                      decoration: InputDecoration(labelText: l.creditInstallments),
                    ),
                  ),
                  const SizedBox(width: 12),
                  Expanded(
                    child: TextField(
                      controller: _tasa,
                      keyboardType: const TextInputType.numberWithOptions(decimal: true),
                      decoration: InputDecoration(labelText: l.creditRate, hintText: '26,5', suffixText: '% E.A.'),
                    ),
                  ),
                ],
              ),
            ],
            const SizedBox(height: 12),
            FilledButton.icon(
              onPressed: _busy ? null : _simular,
              icon: _busy
                  ? const SizedBox(width: 18, height: 18, child: CircularProgressIndicator(strokeWidth: 2))
                  : const Icon(Icons.calculate_outlined),
              label: Text(l.affordCheck),
            ),
            AnimatedSize(
              duration: motion(context),
              curve: kMotionCurve,
              child: _credito != null
                  ? _ResultadoCredito(c: _credito!)
                  : r == null
                      ? const SizedBox(width: double.infinity)
                      : _Resultado(r: r, onRegistrar: _registrar),
            ),
          ],
        ),
      ),
    );
  }
}

class _Resultado extends StatelessWidget {
  const _Resultado({required this.r, required this.onRegistrar});

  final AffordCheck r;
  final ValueChanged<AffordCheck> onRegistrar;

  @override
  Widget build(BuildContext context) {
    final l = context.l;
    final theme = Theme.of(context);
    final tokens = context.tokens;
    // Sin semáforo de culpa: si no alcanza, el tono es de aviso (color de metas), no de error.
    final acento = r.alcanza && !r.enRiesgo ? tokens.income : tokens.goals;
    final lineas = <String>[
      if (!r.alcanza)
        l.affordOver(money(-r.totalDespues))
      else
        l.affordDaily(money(r.porDiaAntes), money(r.porDiaDespues), r.diasRestantes),
      if (r.alcanza && r.enRiesgo && r.fechaAgotamiento != null) l.affordRisk(shortDate(context, r.fechaAgotamiento!)),
      if (r.metaNombre != null && r.metaDias != null) l.affordGoal(r.metaDias!, r.metaNombre!),
    ];
    return Padding(
      padding: const EdgeInsets.only(top: 16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          SectionCard(
            color: acento.container,
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  r.alcanza ? l.affordYes : l.affordNo,
                  style: theme.textTheme.titleMedium?.copyWith(color: acento.onContainer, fontWeight: FontWeight.w700),
                ),
                const SizedBox(height: 8),
                for (final linea in lineas)
                  Padding(
                    padding: const EdgeInsets.only(bottom: 4),
                    child: Text(linea, style: theme.textTheme.bodyMedium?.copyWith(color: acento.onContainer)),
                  ),
              ],
            ),
          ),
          const SizedBox(height: 12),
          Row(
            children: [
              Expanded(
                child: OutlinedButton(onPressed: () => Navigator.pop(context), child: Text(l.affordSkip)),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: FilledButton(onPressed: () => onRegistrar(r), child: Text(l.affordLog)),
              ),
            ],
          ),
        ],
      ),
    );
  }
}


/// El resultado del crédito: cuota, costo total e intereses, y cómo queda el número del día pagándola.
class _ResultadoCredito extends StatelessWidget {
  const _ResultadoCredito({required this.c});

  final CreditCheck c;

  @override
  Widget build(BuildContext context) {
    final l = context.l;
    final theme = Theme.of(context);
    final acento = context.tokens.goals;
    final estilo = theme.textTheme.bodyMedium?.copyWith(color: acento.onContainer);
    return Padding(
      padding: const EdgeInsets.only(top: 16),
      child: SectionCard(
        color: acento.container,
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              l.creditInstallment(money(c.cuota), c.cuotas),
              style: theme.textTheme.titleMedium?.copyWith(color: acento.onContainer, fontWeight: FontWeight.w700),
            ),
            const SizedBox(height: 8),
            Text(l.creditTotal(money(c.totalPagado), money(c.intereses)), style: estilo),
            Text(l.creditMonthlyRate(NumberFormat('0.00', Localizations.localeOf(context).toLanguageTag()).format(c.tasaMensual)), style: estilo),
            if (c.porDiaHoy != null && c.porDiaConCuota != null) ...[
              const SizedBox(height: 8),
              Text(l.creditDaily(money(c.porDiaHoy!), money(c.porDiaConCuota!), c.cuotas), style: estilo),
            ],
            const SizedBox(height: 8),
            Text(l.creditDisclaimer, style: theme.textTheme.bodySmall?.copyWith(color: acento.onContainer)),
          ],
        ),
      ),
    );
  }
}
