import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/format.dart';
import '../../core/widgets.dart';
import '../../data/api.dart';
import '../../data/models.dart';
import '../../data/providers.dart';

/// Categorías: las por defecto se muestran pero no se editan (son compartidas
/// por todos los usuarios); las propias admiten tipo y límite de gasto.
class CategoriesScreen extends ConsumerWidget {
  const CategoriesScreen({super.key});

  Future<void> _editar(BuildContext context, WidgetRef ref, [Category? actual]) async {
    final l = context.l;
    final form = GlobalKey<FormState>();
    final nombre = TextEditingController(text: actual?.nombre ?? '');
    final limite = TextEditingController(text: actual?.limite?.round().toString() ?? '');
    var fijo = actual?.tipo == 'fijo';

    final guardar = await showDialog<bool>(
      context: context,
      builder: (context) => StatefulBuilder(
        builder: (context, setState) => AlertDialog(
          title: Text(actual == null ? l.newCategory : l.editCategory),
          content: Form(
            key: form,
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                TextFormField(
                  controller: nombre,
                  autofocus: actual == null,
                  decoration: InputDecoration(labelText: l.name),
                  validator: (v) => (v ?? '').trim().isEmpty ? l.requiredField : null,
                ),
                const SizedBox(height: 12),
                TextFormField(
                  controller: limite,
                  keyboardType: TextInputType.number,
                  decoration: InputDecoration(labelText: l.limitOptional, prefixText: '\$ '),
                  validator: (v) =>
                      (v ?? '').trim().isEmpty || parseMoney(v!) != null ? null : l.invalidAmount,
                ),
                SwitchListTile(
                  contentPadding: EdgeInsets.zero,
                  title: Text(l.fixedExpense),
                  subtitle: Text(l.fixedExpenseHint),
                  value: fijo,
                  onChanged: (v) => setState(() => fijo = v),
                ),
              ],
            ),
          ),
          actions: [
            TextButton(onPressed: () => Navigator.pop(context, false), child: Text(l.cancel)),
            FilledButton(
              onPressed: () {
                if (form.currentState!.validate()) Navigator.pop(context, true);
              },
              child: Text(l.save),
            ),
          ],
        ),
      ),
    );
    if (guardar != true || !context.mounted) return;

    final api = ref.read(apiProvider);
    final tipo = fijo ? 'fijo' : 'opcional';
    final tope = limite.text.trim().isEmpty ? null : parseMoney(limite.text);
    final ok = await guarded(
      context,
      () => actual == null
          ? api.createCategory(nombre.text.trim(), tipo, tope)
          : api.updateCategory(actual.id, {'nombre': nombre.text.trim(), 'tipo': tipo, 'limite': tope}),
    );
    if (ok) refreshData(ref);
  }

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final l = context.l;
    return Scaffold(
      appBar: AppBar(title: Text(l.categories)),
      floatingActionButton: FloatingActionButton.extended(
        onPressed: () => _editar(context, ref),
        icon: const Icon(Icons.add),
        label: Text(l.newCategory),
      ),
      body: AsyncView(
        value: ref.watch(categoriesProvider),
        onRetry: () => ref.invalidate(categoriesProvider),
        builder: (categorias) => ListView(
          padding: const EdgeInsets.only(bottom: 96),
          children: [
            for (final c in categorias)
              ListTile(
                title: Text(c.nombre),
                subtitle: Text(
                  [
                    c.tipo == 'fijo' ? l.fixedExpense : l.optionalExpense,
                    if (c.limite != null) l.limitOf(money(c.limite!)),
                    if (!c.esPropia) l.defaultCategory,
                  ].join(' · '),
                ),
                trailing: c.esPropia ? const Icon(Icons.edit_outlined) : null,
                onTap: c.esPropia ? () => _editar(context, ref, c) : null,
              ),
          ],
        ),
      ),
    );
  }
}

/// Gastos fijos semanales: el backend los genera solo cada semana.
class RecurringScreen extends ConsumerWidget {
  const RecurringScreen({super.key});

  Future<void> _crear(BuildContext context, WidgetRef ref, List<Category> categorias) async {
    final l = context.l;
    final dias = weekdayNames(context);
    final form = GlobalKey<FormState>();
    final monto = TextEditingController();
    final descripcion = TextEditingController();
    var categoryId = categorias.first.id;
    var dia = DateTime.now().weekday - 1;

    final guardar = await showDialog<bool>(
      context: context,
      builder: (context) => StatefulBuilder(
        builder: (context, setState) => AlertDialog(
          title: Text(l.newRecurring),
          content: Form(
            key: form,
            child: SingleChildScrollView(
              child: Column(
                mainAxisSize: MainAxisSize.min,
                children: [
                  MoneyField(controller: monto, label: l.amount, autofocus: true),
                  const SizedBox(height: 12),
                  TextFormField(
                    controller: descripcion,
                    decoration: InputDecoration(labelText: l.description),
                    validator: (v) => (v ?? '').trim().isEmpty ? l.requiredField : null,
                  ),
                  const SizedBox(height: 12),
                  DropdownButtonFormField<int>(
                    initialValue: categoryId,
                    decoration: InputDecoration(labelText: l.category),
                    items: [for (final c in categorias) DropdownMenuItem(value: c.id, child: Text(c.nombre))],
                    onChanged: (v) => setState(() => categoryId = v!),
                  ),
                  const SizedBox(height: 12),
                  DropdownButtonFormField<int>(
                    initialValue: dia,
                    decoration: InputDecoration(labelText: l.weekday),
                    items: [for (var i = 0; i < 7; i++) DropdownMenuItem(value: i, child: Text(dias[i]))],
                    onChanged: (v) => setState(() => dia = v!),
                  ),
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
              child: Text(l.save),
            ),
          ],
        ),
      ),
    );
    if (guardar != true || !context.mounted) return;

    final ok = await guarded(
      context,
      () => ref
          .read(apiProvider)
          .createRecurring(parseMoney(monto.text)!, descripcion.text.trim(), categoryId, dia),
    );
    if (ok) refreshData(ref);
  }

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final l = context.l;
    final dias = weekdayNames(context);
    final categorias = ref.watch(categoriesProvider).value ?? const <Category>[];
    final nombres = {for (final c in categorias) c.id: c.nombre};

    return Scaffold(
      appBar: AppBar(title: Text(l.recurringExpenses)),
      floatingActionButton: categorias.isEmpty
          ? null
          : FloatingActionButton.extended(
              onPressed: () => _crear(context, ref, categorias),
              icon: const Icon(Icons.add),
              label: Text(l.newRecurring),
            ),
      body: AsyncView(
        value: ref.watch(recurringProvider),
        onRetry: () => ref.invalidate(recurringProvider),
        builder: (fijos) {
          if (fijos.isEmpty) return Center(child: EmptyView(icon: Icons.autorenew, text: l.noRecurring));
          return ListView(
            padding: const EdgeInsets.only(bottom: 96),
            children: [
              for (final f in fijos)
                Dismissible(
                  key: ValueKey(f.id),
                  direction: DismissDirection.endToStart,
                  background: Container(
                    alignment: Alignment.centerRight,
                    padding: const EdgeInsets.only(right: 24),
                    color: Theme.of(context).colorScheme.errorContainer,
                    child: const Icon(Icons.delete_outline),
                  ),
                  confirmDismiss: (_) => confirm(
                    context,
                    title: l.deleteRecurringTitle,
                    body: l.deleteRecurringBody,
                    action: l.delete,
                  ),
                  onDismissed: (_) async {
                    await guarded(context, () => ref.read(apiProvider).deleteRecurring(f.id));
                    refreshData(ref);
                  },
                  child: SwitchListTile(
                    title: Text('${f.descripcion} · ${money(f.monto)}'),
                    subtitle: Text('${nombres[f.categoryId] ?? ''} · ${l.everyWeekday(dias[f.diaSemana])}'),
                    value: f.activo,
                    onChanged: (v) async {
                      final ok = await guarded(context, () => ref.read(apiProvider).setRecurringActive(f.id, v));
                      if (ok) refreshData(ref);
                    },
                  ),
                ),
            ],
          );
        },
      ),
    );
  }
}
