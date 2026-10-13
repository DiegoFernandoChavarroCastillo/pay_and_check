import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/format.dart';
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
                          label: Text(l.allCategories),
                          selected: _categoryId == null,
                          onSelected: (_) => setState(() => _categoryId = null),
                        ),
                      ),
                      for (final c in categorias)
                        Padding(
                          padding: const EdgeInsets.only(right: 8),
                          child: FilterChip(
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
        return ListView.builder(
          padding: const EdgeInsets.only(bottom: 96),
          itemCount: gastos.length,
          itemBuilder: (context, i) {
            final g = gastos[i];
            return ListTile(
              leading: CircleAvatar(
                child: Icon(sourceIcon(g.source), semanticLabel: sourceLabel(l, g.source)),
              ),
              title: Text(g.descripcion, maxLines: 1, overflow: TextOverflow.ellipsis),
              subtitle: Text(
                [nombres[g.categoryId] ?? '', shortDate(context, g.fecha), ?g.comercio].join(' · '),
                maxLines: 1,
                overflow: TextOverflow.ellipsis,
              ),
              trailing: Text(money(g.monto), style: Theme.of(context).textTheme.titleMedium),
              onTap: () => Navigator.push(
                context,
                MaterialPageRoute<void>(builder: (_) => ExpenseFormScreen(existing: g)),
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
        return ListView.builder(
          padding: const EdgeInsets.only(bottom: 96),
          itemCount: ingresos.length,
          itemBuilder: (context, i) {
            final ingreso = ingresos[i];
            return ListTile(
              leading: const CircleAvatar(child: Icon(Icons.south_west)),
              title: Text(ingreso.descripcion, maxLines: 1, overflow: TextOverflow.ellipsis),
              subtitle: Text(shortDate(context, ingreso.fecha)),
              trailing: Row(
                mainAxisSize: MainAxisSize.min,
                children: [
                  Text(money(ingreso.monto), style: Theme.of(context).textTheme.titleMedium),
                  IconButton(
                    tooltip: l.delete,
                    icon: const Icon(Icons.delete_outline),
                    onPressed: () async {
                      if (!await confirm(context, title: l.deleteIncomeTitle, body: l.deleteIncomeBody, action: l.delete)) {
                        return;
                      }
                      if (!context.mounted) return;
                      final ok = await guarded(context, () => ref.read(apiProvider).deleteIncome(ingreso.id));
                      if (ok) refreshData(ref);
                    },
                  ),
                ],
              ),
            );
          },
        );
      },
    );
  }
}
