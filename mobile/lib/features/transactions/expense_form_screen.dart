import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/charts.dart';
import '../../core/format.dart';
import '../../core/motion.dart';
import '../../core/theme.dart';
import '../../core/widgets.dart';
import '../../data/api.dart';
import '../coach/coach_widgets.dart';
import '../../data/models.dart';
import '../../data/providers.dart';

/// Alta, edición y confirmación de un gasto. Todo gasto que propone la IA
/// (texto, voz, recibo, SMS) pasa por aquí como `draft` antes de guardarse:
/// la persona siempre ve y corrige lo que se va a registrar.
class ExpenseFormScreen extends ConsumerStatefulWidget {
  const ExpenseFormScreen({super.key, this.draft, this.existing});

  final ExpenseDraft? draft;
  final Expense? existing;

  @override
  ConsumerState<ExpenseFormScreen> createState() => _ExpenseFormScreenState();
}

class _ExpenseFormScreenState extends ConsumerState<ExpenseFormScreen> {
  final _form = GlobalKey<FormState>();
  late final TextEditingController _monto;
  late final TextEditingController _descripcion;
  late final TextEditingController _comercio;
  late DateTime _fecha;
  int? _categoryId;
  bool _saving = false;

  @override
  void initState() {
    super.initState();
    final draft = widget.draft;
    final existing = widget.existing;
    final monto = existing?.monto ?? draft?.monto;
    _monto = TextEditingController(text: monto == null ? '' : monto.round().toString());
    _descripcion = TextEditingController(text: existing?.descripcion ?? draft?.descripcion ?? '');
    _comercio = TextEditingController(text: existing?.comercio ?? draft?.comercio ?? '');
    _fecha = existing?.fecha ?? draft?.fecha ?? today();
    _categoryId = existing?.categoryId;
  }

  @override
  void dispose() {
    _monto.dispose();
    _descripcion.dispose();
    _comercio.dispose();
    super.dispose();
  }

  /// La categoría elegida; si aún no hay, la que propuso la IA por nombre o la primera.
  int? _categoriaInicial(List<Category> categorias) {
    if (_categoryId != null && categorias.any((c) => c.id == _categoryId)) return _categoryId;
    final propuesta = categorias.where((c) => c.nombre == widget.draft?.categoria).firstOrNull;
    return (propuesta ?? categorias.firstOrNull)?.id;
  }

  Future<void> _save(int categoryId) async {
    if (!_form.currentState!.validate()) return;
    setState(() => _saving = true);

    final api = ref.read(apiProvider);
    final comercio = _comercio.text.trim();
    final datos = {
      'monto': parseMoney(_monto.text),
      'category_id': categoryId,
      'descripcion': _descripcion.text.trim(),
      'fecha': isoDate(_fecha),
      'comercio': comercio.isEmpty ? null : comercio,
    };

    Expense? creado;
    final ok = await guarded(context, () async {
      final existing = widget.existing;
      if (existing != null) {
        await api.updateExpense(existing.id, datos);
      } else {
        creado = await api.createExpense({
          ...datos,
          'source': widget.draft?.source ?? 'manual',
          'texto_original': widget.draft?.textoOriginal,
        });
      }
    });
    if (!mounted) return;
    setState(() => _saving = false);
    if (!ok) return;

    unawaited(HapticFeedback.lightImpact());
    refreshData(ref);
    Navigator.pop(context);
    // El mensaje del coach llega después y sin bloquear: registrar nunca espera a la IA.
    final nuevo = creado;
    if (nuevo != null) unawaited(api.reaction(nuevo.id).then(showSnack, onError: (_) {}));
  }

  Future<void> _delete() async {
    final l = context.l;
    if (!await confirm(context, title: l.deleteExpenseTitle, body: l.deleteExpenseBody, action: l.delete)) return;
    if (!mounted) return;
    final ok = await guarded(context, () => ref.read(apiProvider).deleteExpense(widget.existing!.id));
    if (ok && mounted) {
      refreshData(ref);
      Navigator.pop(context);
    }
  }

  @override
  Widget build(BuildContext context) {
    final l = context.l;
    final esConfirmacion = widget.draft != null && widget.draft!.source != 'manual';
    return Scaffold(
      appBar: AppBar(
        title: Text(widget.existing != null ? l.editExpense : (esConfirmacion ? l.confirmExpense : l.newExpense)),
        actions: [
          if (widget.existing != null)
            IconButton(tooltip: l.delete, icon: const Icon(Icons.delete_outline), onPressed: _delete),
        ],
      ),
      body: AsyncView(
        value: ref.watch(categoriesProvider),
        onRetry: () => ref.invalidate(categoriesProvider),
        builder: (categorias) {
          final seleccion = _categoriaInicial(categorias);
          return Form(
            key: _form,
            child: ListView(
              padding: const EdgeInsets.all(16),
              children: [
                // Lo que propone la IA llega como una tarjeta del coach: se revisa antes de guardar.
                if (esConfirmacion)
                  TweenAnimationBuilder<double>(
                    tween: Tween(begin: 0.9, end: 1),
                    duration: motion(context, const Duration(milliseconds: 450)),
                    curve: kSpring,
                    builder: (context, escala, child) => Transform.scale(scale: escala, child: child),
                    child: SectionCard(
                      color: context.tokens.coach.container,
                      child: Row(
                        children: [
                          const CoachAvatar(size: 40),
                          const SizedBox(width: 12),
                          Expanded(
                            child: Text(
                              l.confirmExpenseHint,
                              style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                                    color: context.tokens.coach.onContainer,
                                  ),
                            ),
                          ),
                        ],
                      ),
                    ),
                  ),
                MoneyField(
                  controller: _monto,
                  label: l.amount,
                  autofocus: widget.existing == null && !esConfirmacion,
                  hero: true,
                ),
                const SizedBox(height: 12),
                TextFormField(
                  controller: _descripcion,
                  textCapitalization: TextCapitalization.sentences,
                  decoration: InputDecoration(labelText: l.description),
                  validator: (v) => (v ?? '').trim().isEmpty ? l.requiredField : null,
                ),
                const SizedBox(height: 12),
                Padding(
                  padding: const EdgeInsets.only(left: 4, bottom: 6, top: 4),
                  child: Text(l.category, style: Theme.of(context).textTheme.labelLarge),
                ),
                // La categoría se elige de un toque, cada una con su color de las gráficas.
                Builder(
                  builder: (context) {
                    final colores = categoryColors(categorias.map((c) => c.nombre), Theme.of(context).brightness);
                    return Wrap(
                      spacing: 8,
                      runSpacing: 4,
                      children: [
                        for (final c in categorias)
                          ChoiceChip(
                            avatar: CircleAvatar(backgroundColor: colores[c.nombre], radius: 6),
                            showCheckmark: false,
                            label: Text(c.nombre),
                            selected: c.id == seleccion,
                            onSelected: (_) {
                              tapFeedback();
                              setState(() => _categoryId = c.id);
                            },
                          ),
                      ],
                    );
                  },
                ),
                const SizedBox(height: 12),
                DateField(label: l.date, value: _fecha, onChanged: (d) => setState(() => _fecha = d)),
                const SizedBox(height: 12),
                TextFormField(
                  controller: _comercio,
                  textCapitalization: TextCapitalization.words,
                  decoration: InputDecoration(labelText: l.merchantOptional),
                ),
                const SizedBox(height: 24),
                SaveButton(
                  saving: _saving,
                  onPressed: () {
                    final id = _categoryId ?? seleccion;
                    if (id != null) _save(id);
                  },
                ),
              ],
            ),
          );
        },
      ),
    );
  }
}
