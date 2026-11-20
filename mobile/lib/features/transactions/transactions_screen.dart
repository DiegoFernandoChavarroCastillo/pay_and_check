import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/charts.dart';
import '../../core/format.dart';
import '../../core/motion.dart';
import '../../core/theme.dart';
import '../../core/widgets.dart';
import '../../data/api.dart';
import '../../data/models.dart';
import '../../data/providers.dart';
import '../../l10n/gen/app_localizations.dart';
import 'expense_form_screen.dart';

IconData sourceIcon(String source) => switch (source) {
      'voz' => Icons.mic_none,
      'texto' => Icons.chat_bubble_outline,
      'ocr' => Icons.photo_camera_outlined,
      'sms' => Icons.sms_outlined,
      'recurrente' => Icons.autorenew,
      _ => Icons.edit_outlined,
    };

String sourceLabel(AppLocalizations l, String source) => switch (source) {
      'voz' => l.sourceVoice,
      'texto' => l.sourceText,
      'ocr' => l.sourceReceipt,
      'sms' => l.sourceSms,
      'recurrente' => l.sourceRecurring,
      _ => l.sourceManual,
    };

/// Lista de movimientos: gastos (filtrables por categoría) e ingresos.
class TransactionsScreen extends ConsumerStatefulWidget {
  const TransactionsScreen({super.key});

  @override
  ConsumerState<TransactionsScreen> createState() => _TransactionsScreenState();
}

class _TransactionsScreenState extends ConsumerState<TransactionsScreen> {
  bool _ingresos = false;
  int? _categoryId;
  String _busqueda = '';

  @override
  Widget build(BuildContext context) {
    final l = context.l;
    final categorias = ref.watch(categoriesProvider).value ?? const <Category>[];
    final nombres = {for (final c in categorias) c.id: c.nombre};

    return Column(
      children: [
        Padding(
          padding: const EdgeInsets.fromLTRB(16, 16, 16, 8),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              Text(l.tabTransactions, style: Theme.of(context).textTheme.headlineSmall),
              const SizedBox(height: 12),
              SegmentedButton<bool>(
                segments: [
                  ButtonSegment(value: false, label: Text(l.expenses)),
                  ButtonSegment(value: true, label: Text(l.incomes)),
                ],
                selected: {_ingresos},
                onSelectionChanged: (s) => setState(() => _ingresos = s.first),
              ),
              if (!_ingresos) ...[
                const SizedBox(height: 12),
                TextField(
                  decoration: InputDecoration(
                    hintText: l.search,
                    prefixIcon: const Icon(Icons.search),
                    isDense: true,
                  ),
                  onChanged: (v) => setState(() => _busqueda = v.trim().toLowerCase()),
                ),
                const SizedBox(height: 8),
                SizedBox(
                  height: 40,
                  child: ListView(
                    scrollDirection: Axis.horizontal,
                    children: [
                      Padding(
                        padding: const EdgeInsets.only(right: 8),
                        child: FilterChip(
                          showCheckmark: false,
                          label: Text(l.allCategories),
                          selected: _categoryId == null,
                          onSelected: (_) => setState(() => _categoryId = null),
                        ),
                      ),
                      for (final c in categorias)
                        Padding(
                          padding: const EdgeInsets.only(right: 8),
                          child: FilterChip(
                            showCheckmark: false,
                            label: Text(c.nombre),
                            selected: _categoryId == c.id,
                            onSelected: (v) => setState(() => _categoryId = v ? c.id : null),
                          ),
                        ),
                    ],
                  ),
                ),
              ],
            ],
          ),
        ),
        Expanded(
          child: RefreshIndicator(
            onRefresh: () async {
              refreshData(ref);
              await ref.read(expensesProvider.future);
            },
            child: _ingresos ? _incomeList() : _expenseList(nombres),
          ),
        ),
      ],
    );
  }

  Widget _expenseList(Map<int, String> nombres) {
    final l = context.l;
    return AsyncView(
      value: ref.watch(expensesProvider),
      onRetry: () => ref.invalidate(expensesProvider),
      builder: (todos) {
        final gastos = todos.where((g) {
          final coincide = _busqueda.isEmpty ||
              g.descripcion.toLowerCase().contains(_busqueda) ||
              (g.comercio ?? '').toLowerCase().contains(_busqueda);
          return coincide && (_categoryId == null || g.categoryId == _categoryId);
        }).toList();

        if (gastos.isEmpty) {
          return ListView(children: [EmptyView(icon: Icons.receipt_long_outlined, text: l.noExpenses)]);
        }
        // Un bloque por día, del más reciente al más antiguo, con lo gastado ese día.
        final porDia = <DateTime, List<Expense>>{};
        for (final g in [...gastos]..sort((a, b) => b.fecha.compareTo(a.fecha))) {
          porDia.putIfAbsent(DateTime(g.fecha.year, g.fecha.month, g.fecha.day), () => []).add(g);
        }
        final dias = porDia.keys.toList();
        final colores = categoryColors(nombres.values, Theme.of(context).brightness);
        return ListView.builder(
          padding: EdgeInsets.fromLTRB(16, 4, 16, 96 + bottomInset(context)),
          itemCount: dias.length,
          itemBuilder: (context, i) {
            final delDia = porDia[dias[i]]!;
            return FadeSlideIn(
              index: i,
              child: _DayGroup(
                titulo: _nombreDia(context, dias[i]),
                total: delDia.fold(0.0, (suma, g) => suma + g.monto),
                children: [
                  for (final g in delDia)
                    _Row(
                      icon: sourceIcon(g.source),
                      iconLabel: sourceLabel(l, g.source),
                      color: colores[nombres[g.categoryId]],
                      title: g.descripcion,
                      subtitle: [nombres[g.categoryId] ?? '', ?g.comercio].where((t) => t.isNotEmpty).join(' · '),
                      amount: g.monto,
                      onTap: () => Navigator.push(
                        context,
                        MaterialPageRoute<void>(builder: (_) => ExpenseFormScreen(existing: g)),
                      ),
                    ),
                ],
              ),
            );
          },
        );
      },
    );
  }

  Widget _incomeList() {
    final l = context.l;
    return AsyncView(
      value: ref.watch(incomesProvider),
      onRetry: () => ref.invalidate(incomesProvider),
      builder: (ingresos) {
        if (ingresos.isEmpty) {
          return ListView(children: [EmptyView(icon: Icons.south_west, text: l.noIncomes)]);
        }
        final acento = context.tokens.income;
        return ListView(
          padding: EdgeInsets.fromLTRB(16, 4, 16, 96 + bottomInset(context)),
          children: [
            BentoTile(
              padding: const EdgeInsets.symmetric(vertical: 8),
              child: Column(
                children: [
                  for (final ingreso in ingresos)
                    _Row(
                      icon: Icons.south_west,
                      color: acento.color,
                      title: ingreso.descripcion,
                      subtitle: shortDate(context, ingreso.fecha),
                      amount: ingreso.monto,
                      trailing: IconButton(
                        tooltip: l.delete,
                        icon: const Icon(Icons.delete_outline),
                        onPressed: () async {
                          if (!await confirm(
                            context,
                            title: l.deleteIncomeTitle,
                            body: l.deleteIncomeBody,
                            action: l.delete,
                          )) {
                            return;
                          }
                          if (!mounted) return;
                          final ok = await guarded(context, () => ref.read(apiProvider).deleteIncome(ingreso.id));
                          if (ok) refreshData(ref);
                        },
                      ),
                    ),
                ],
              ),
            ),
          ],
        );
      },
    );
  }
}

String _nombreDia(BuildContext context, DateTime dia) {
  final hoy = today();
  if (dia == hoy) return context.l.dayToday;
  if (dia == hoy.subtract(const Duration(days: 1))) return context.l.dayYesterday;
  final texto = longDate(context, dia);
  return texto[0].toUpperCase() + texto.substring(1);
}

/// Los movimientos de un día dentro de una tarjeta, con su total arriba.
class _DayGroup extends StatelessWidget {
  const _DayGroup({required this.titulo, required this.total, required this.children});

  final String titulo;
  final double total;
  final List<Widget> children;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Padding(
      padding: const EdgeInsets.only(bottom: AppTokens.gap),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Padding(
            padding: const EdgeInsets.fromLTRB(8, 8, 8, 8),
            child: Row(
              children: [
                Expanded(child: Text(titulo, style: theme.textTheme.titleSmall)),
                Text(
                  money(total),
                  style: theme.textTheme.labelLarge?.copyWith(
                    color: theme.colorScheme.onSurfaceVariant,
                    fontFeatures: kTabular,
                  ),
                ),
              ],
            ),
          ),
          BentoTile(padding: const EdgeInsets.symmetric(vertical: 8), child: Column(children: children)),
        ],
      ),
    );
  }
}

/// Un movimiento: ícono con el color de su categoría, descripción y monto.
class _Row extends StatelessWidget {
  const _Row({
    required this.icon,
    required this.title,
    required this.subtitle,
    required this.amount,
    this.iconLabel,
    this.color,
    this.onTap,
    this.trailing,
  });

  final IconData icon;
  final String? iconLabel;
  final Color? color;
  final String title;
  final String subtitle;
  final double amount;
  final VoidCallback? onTap;
  final Widget? trailing;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final tono = color ?? theme.colorScheme.primary;
    return ListTile(
      contentPadding: EdgeInsets.only(left: 16, right: trailing == null ? 16 : 4),
      leading: Container(
        width: 44,
        height: 44,
        decoration: BoxDecoration(color: tono.withValues(alpha: 0.16), borderRadius: BorderRadius.circular(14)),
        child: Icon(icon, size: 22, color: tono, semanticLabel: iconLabel),
      ),
      // Dos renglones: una descripción como "Mesada de mis papás" no debe quedar cortada por el monto.
      title: Text(title, maxLines: 2, overflow: TextOverflow.ellipsis, style: theme.textTheme.titleSmall),
      subtitle: subtitle.isEmpty ? null : Text(subtitle, maxLines: 1, overflow: TextOverflow.ellipsis),
      trailing: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Text(money(amount), style: theme.textTheme.titleSmall?.copyWith(fontFeatures: kTabular)),
          ?trailing,
        ],
      ),
      onTap: onTap,
    );
  }
}
