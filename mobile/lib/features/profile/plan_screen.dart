import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/format.dart';
import '../../core/widgets.dart';
import '../../data/api.dart';
import '../../data/models.dart';
import '../../data/providers.dart';
import '../../l10n/gen/app_localizations.dart';

String planLabel(AppLocalizations l, String codigo) => switch (codigo) {
      'institucional' => l.planInstitutional,
      'premium' => l.planPremium,
      'familiar' => l.planFamily,
      _ => l.planFree,
    };

/// Mi plan (PS-97): el plan actual, cuánto queda del cupo de IA del mes, los
/// otros planes (Premium y Familiar se cambian sin cobro: es una simulación) y
/// el canje de un código de convenio o familiar.
/// Nombre para mostrar de una función de plan (`services/planes.py`). Null si la app no la conoce aún.
String? nombreFuncion(AppLocalizations l, String codigo) => switch (codigo) {
      'registro' => l.featRegistro,
      'numero_diario' => l.featNumeroDiario,
      'simulador' => l.featSimulador,
      'metas_retos' => l.featMetasRetos,
      'coach' => l.featCoach,
      'reportes' => l.featReportes,
      'captura_automatica' => l.featCapturaAutomatica,
      'ia_ampliada' => l.featIaAmpliada,
      'progreso_familiar' => l.featProgresoFamiliar,
      'apoyos_universidad' => l.featApoyos,
      _ => null,
    };

class PlanScreen extends ConsumerWidget {
  const PlanScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final l = context.l;
    final suscripcion = ref.watch(subscriptionProvider);
    final planes = ref.watch(plansProvider);
    return Scaffold(
      appBar: AppBar(title: Text(l.myPlan)),
      body: AsyncView<Subscription>(
        value: suscripcion,
        onRetry: () => ref.invalidate(subscriptionProvider),
        builder: (s) => RefreshIndicator(
          onRefresh: () async {
            ref
              ..invalidate(subscriptionProvider)
              ..invalidate(plansProvider);
            await ref.read(subscriptionProvider.future);
          },
          child: ListView(
            padding: const EdgeInsets.all(16),
            children: [
              _PlanActual(s),
              if (s.familia case final f?) _Familia(familia: f),
              const _Canje(),
              if (planes.value case final lista?) ...[
                Padding(
                  padding: const EdgeInsets.fromLTRB(4, 8, 4, 12),
                  child: Text(l.planOtherPlans, style: Theme.of(context).textTheme.titleMedium),
                ),
                for (final p in lista.where((p) => p.codigo != s.plan))
                  _OtroPlan(p, base: p.codigo == 'gratis' ? const [] : _funcionesGratis(lista)),
              ],
            ],
          ),
        ),
      ),
    );
  }
}

class _PlanActual extends StatelessWidget {
  const _PlanActual(this.s);

  final Subscription s;

  @override
  Widget build(BuildContext context) {
    final l = context.l;
    final theme = Theme.of(context);
    final fecha = longDate(context, s.reiniciaEl);
    final agotado = s.restantes <= 0;
    return SectionCard(
      title: l.planCurrent,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(planLabel(l, s.plan), key: const ValueKey('plan-actual'), style: theme.textTheme.headlineSmall),
          if (s.organizacion case final org?) Text(l.planOrganization(org), style: theme.textTheme.bodyMedium),
          const SizedBox(height: 16),
          LabeledProgress(
            label: l.aiUsageTitle,
            value: l.aiUsageCount(s.usadas, s.cupoIa),
            progress: s.cupoIa == 0 ? 1 : s.usadas / s.cupoIa,
            color: agotado ? theme.colorScheme.error : null,
          ),
          Text(
            [if (s.compartido) l.aiUsageShared, l.aiUsageResets(fecha)].join(' · '),
            style: theme.textTheme.bodySmall,
          ),
          if (agotado) ...[
            const SizedBox(height: 8),
            Text(l.aiUsageExhausted, style: theme.textTheme.bodyMedium?.copyWith(color: theme.colorScheme.error)),
          ],
          if (s.familia case final f?) ...[
            const SizedBox(height: 12),
            Row(
              children: [
                Expanded(child: SelectableText(l.familyCode(f.codigo), style: theme.textTheme.titleSmall)),
                IconButton(
                  tooltip: MaterialLocalizations.of(context).copyButtonLabel,
                  icon: const Icon(Icons.copy),
                  onPressed: () => Clipboard.setData(ClipboardData(text: f.codigo)),
                ),
              ],
            ),
            Text(l.familyMembers(f.integrantes, f.maxIntegrantes), style: theme.textTheme.bodySmall),
          ],
          if (s.aviso != null) ...[
            const SizedBox(height: 8),
            Text(l.planSimulated, style: theme.textTheme.bodySmall),
          ],
        ],
      ),
    );
  }
}

/// Lo que trae el plan Gratis: los demás planes lo resumen en una línea.
List<String> _funcionesGratis(List<Plan> planes) =>
    planes.where((p) => p.codigo == 'gratis').firstOrNull?.funciones ?? const [];

class _OtroPlan extends ConsumerStatefulWidget {
  const _OtroPlan(this.plan, {this.base = const []});

  final Plan plan;
  final List<String> base;

  @override
  ConsumerState<_OtroPlan> createState() => _OtroPlanState();
}

class _OtroPlanState extends ConsumerState<_OtroPlan> {
  bool _busy = false;

  Future<void> _cambiar() async {
    final l = context.l;
    final nombre = planLabel(l, widget.plan.codigo);
    if (!await confirm(context, title: l.planChooseTitle(nombre), body: l.planChooseBody)) return;
    if (!mounted) return;
    setState(() => _busy = true);
    final ok = await guarded(context, () => ref.read(apiProvider).changePlan(widget.plan.codigo));
    if (!mounted) return;
    setState(() => _busy = false);
    if (ok) {
      ref.invalidate(subscriptionProvider);
      showSnack(l.planChanged(nombre));
    }
  }

  @override
  Widget build(BuildContext context) {
    final l = context.l;
    final theme = Theme.of(context);
    final p = widget.plan;
    final precio = p.codigo == 'institucional'
        ? l.planPaidByUniversity
        : p.precio == 0
            ? l.planFree
            : l.planPricePerMonth(money(p.precio));
    final cupo = p.compartido && p.maxIntegrantes != null
        ? l.planAiQuotaShared(p.cupoIa, p.maxIntegrantes!)
        : l.planAiQuota(p.cupoIa);
    return SectionCard(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Expanded(child: Text(planLabel(l, p.codigo), style: theme.textTheme.titleMedium)),
              Text(precio, style: theme.textTheme.titleSmall),
            ],
          ),
          const SizedBox(height: 8),
          // Lo que se puede hacer, primero; el cupo de IA es un detalle.
          if (widget.base.isNotEmpty)
            Padding(
              padding: const EdgeInsets.only(bottom: 4),
              child: Text(l.planEverythingInFree, style: theme.textTheme.bodyMedium),
            ),
          for (final f in p.funciones.where((f) => !widget.base.contains(f)))
            if (nombreFuncion(l, f) case final nombre?)
              Padding(
                padding: const EdgeInsets.only(bottom: 4),
                child: Row(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Icon(Icons.check_circle_outline, size: 18, color: theme.colorScheme.primary),
                    const SizedBox(width: 8),
                    Expanded(child: Text(nombre, style: theme.textTheme.bodyMedium)),
                  ],
                ),
              ),
          const SizedBox(height: 4),
          Text(cupo, style: theme.textTheme.bodySmall),
          if (p.estadoDemo == 'simulado') Text(l.planSimulated, style: theme.textTheme.bodySmall),
          const SizedBox(height: 8),
          // Institucional solo se activa con el código de convenio: no se puede elegir aquí.
          if (p.codigo == 'institucional')
            Text(l.planInstitutionalHow, style: theme.textTheme.bodySmall)
          else
            Align(
              alignment: Alignment.centerRight,
              child: OutlinedButton(
                onPressed: _busy ? null : _cambiar,
                child: _busy
                    ? const SizedBox.square(dimension: 16, child: CircularProgressIndicator(strokeWidth: 2))
                    : Text(l.planChoose),
              ),
            ),
        ],
      ),
    );
  }
}

class _Canje extends ConsumerStatefulWidget {
  const _Canje();

  @override
  ConsumerState<_Canje> createState() => _CanjeState();
}

class _CanjeState extends ConsumerState<_Canje> {
  final _codigo = TextEditingController();
  bool _busy = false;

  @override
  void dispose() {
    _codigo.dispose();
    super.dispose();
  }

  Future<void> _canjear() async {
    final codigo = _codigo.text.trim();
    if (codigo.isEmpty) return;
    final l = context.l;
    setState(() => _busy = true);
    Subscription? nueva;
    await guarded(context, () async => nueva = await ref.read(apiProvider).redeemCode(codigo));
    if (!mounted) return;
    setState(() => _busy = false);
    final s = nueva;
    if (s != null) {
      _codigo.clear();
      ref.invalidate(subscriptionProvider);
      showSnack(l.planChanged(planLabel(l, s.plan)));
    }
  }

  @override
  Widget build(BuildContext context) {
    final l = context.l;
    return SectionCard(
      title: l.redeemTitle,
      child: Row(
        children: [
          Expanded(
            child: TextField(
              key: const ValueKey('redeem-field'),
              controller: _codigo,
              textCapitalization: TextCapitalization.characters,
              decoration: InputDecoration(hintText: l.redeemHint),
              onSubmitted: (_) => _canjear(),
            ),
          ),
          const SizedBox(width: 12),
          FilledButton(onPressed: _busy ? null : _canjear, child: Text(l.redeemAction)),
        ],
      ),
    );
  }
}


/// Plan Familiar con sentido para quien paga: el titular ve el progreso agregado de quien lo comparte; cada
/// integrante decide si lo comparte. Nunca se ven gastos, montos ni check-ins.
class _Familia extends ConsumerWidget {
  const _Familia({required this.familia});

  final Family familia;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final l = context.l;
    final theme = Theme.of(context);
    if (!familia.esTitular) {
      return Padding(
        padding: const EdgeInsets.only(top: 12),
        child: SectionCard(
          child: SwitchListTile(
            contentPadding: EdgeInsets.zero,
            value: familia.comparteProgreso,
            title: Text(l.familyShareToggle),
            subtitle: Text(l.familyShareHint),
            onChanged: (v) async {
              if (await guarded(context, () => ref.read(apiProvider).shareProgress(v))) {
                ref.invalidate(subscriptionProvider);
              }
            },
          ),
        ),
      );
    }
    final progreso = ref.watch(familyProgressProvider);
    return Padding(
      padding: const EdgeInsets.only(top: 12),
      child: SectionCard(
        title: l.familyProgressTitle,
        child: AsyncView<List<FamilyMemberProgress>>(
          value: progreso,
          onRetry: () => ref.invalidate(familyProgressProvider),
          builder: (lista) {
            if (lista.isEmpty) return Text(l.familyProgressEmpty, style: theme.textTheme.bodyMedium);
            return Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                for (final m in lista)
                  Padding(
                    padding: const EdgeInsets.only(bottom: 12),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(m.nombre, style: theme.textTheme.titleMedium),
                        if (!m.comparte)
                          Text(l.familyNotShared, style: theme.textTheme.bodySmall)
                        else ...[
                          Text(
                            [
                              l.familyStreak(m.racha ?? 0),
                              l.familyConsistency(((m.constancia ?? 0) * 100).round()),
                              if (m.presupuestoAlcanza != null)
                                m.presupuestoAlcanza! ? l.familyBudgetOk : l.familyBudgetTight,
                            ].join(' · '),
                            style: theme.textTheme.bodyMedium,
                          ),
                          if (m.progresoMetas != null) ...[
                            const SizedBox(height: 6),
                            LabeledProgress(
                              label: l.familyGoals(m.metasActivas ?? 0),
                              value: '${((m.progresoMetas ?? 0) * 100).round()} %',
                              progress: m.progresoMetas ?? 0,
                            ),
                          ],
                        ],
                      ],
                    ),
                  ),
                Text(l.familyPrivacy, style: theme.textTheme.bodySmall),
              ],
            );
          },
        ),
      ),
    );
  }
}
