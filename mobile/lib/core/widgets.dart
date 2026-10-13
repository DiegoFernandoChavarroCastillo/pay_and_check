import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../l10n/gen/app_localizations.dart';
import 'format.dart';
import 'motion.dart';

/// Para mostrar avisos (ej. el mensaje del coach) aunque la pantalla que los
/// originó ya se haya cerrado.
final messengerKey = GlobalKey<ScaffoldMessengerState>();

extension L10nX on BuildContext {
  AppLocalizations get l => AppLocalizations.of(this)!;
}

void showSnack(String texto) {
  messengerKey.currentState
    ?..hideCurrentSnackBar()
    ..showSnackBar(SnackBar(content: Text(texto), behavior: SnackBarBehavior.floating));
}

/// Ejecuta una acción contra el backend y muestra el error si falla.
/// Devuelve true si terminó bien.
Future<bool> guarded(BuildContext context, Future<void> Function() accion) async {
  final l = context.l;
  try {
    await accion();
    return true;
  } catch (e) {
    showSnack(errorMessage(e, l));
    return false;
  }
}

Future<bool> confirm(BuildContext context, {required String title, required String body, String? action}) async {
  final ok = await showDialog<bool>(
    context: context,
    builder: (context) => AlertDialog(
      title: Text(title),
      content: Text(body),
      actions: [
        TextButton(onPressed: () => Navigator.pop(context, false), child: Text(context.l.cancel)),
        FilledButton(onPressed: () => Navigator.pop(context, true), child: Text(action ?? context.l.confirm)),
      ],
    ),
  );
  return ok ?? false;
}

/// Estados de carga y error uniformes para cualquier dato remoto.
class AsyncView<T> extends StatelessWidget {
  const AsyncView({super.key, required this.value, required this.builder, this.onRetry});

  final AsyncValue<T> value;
  final Widget Function(T data) builder;
  final VoidCallback? onRetry;

  @override
  Widget build(BuildContext context) {
    // Al refrescar se mantiene el dato anterior a la vista en vez de parpadear.
    final Widget hijo;
    if (value.hasValue) {
      hijo = KeyedSubtree(key: const ValueKey('datos'), child: builder(value.requireValue));
    } else if (value.hasError) {
      hijo = ErrorView(key: const ValueKey('error'), error: value.error!, onRetry: onRetry);
    } else {
      hijo = const Padding(
        key: ValueKey('carga'),
        padding: EdgeInsets.all(32),
        child: Center(child: CircularProgressIndicator()),
      );
    }
    // El paso de "cargando" a los datos es un fundido, no un salto.
    return AnimatedSwitcher(
      duration: motion(context, const Duration(milliseconds: 250)),
      layoutBuilder: (actual, anteriores) => Stack(
        alignment: Alignment.topCenter,
        children: [...anteriores, ?actual],
      ),
      child: hijo,
    );
  }
}

class ErrorView extends StatelessWidget {
  const ErrorView({super.key, required this.error, this.onRetry});

  final Object error;
  final VoidCallback? onRetry;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.all(24),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(Icons.cloud_off, size: 40, color: Theme.of(context).colorScheme.outline),
          const SizedBox(height: 12),
          Text(errorMessage(error, context.l), textAlign: TextAlign.center),
          if (onRetry != null) ...[
            const SizedBox(height: 12),
            FilledButton.tonal(onPressed: onRetry, child: Text(context.l.retry)),
          ],
        ],
      ),
    );
  }
}

class EmptyView extends StatelessWidget {
  const EmptyView({super.key, required this.icon, required this.text, this.action});

  final IconData icon;
  final String text;
  final Widget? action;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Padding(
      padding: const EdgeInsets.all(32),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(icon, size: 48, color: theme.colorScheme.outline),
          const SizedBox(height: 12),
          Text(text, textAlign: TextAlign.center, style: theme.textTheme.bodyLarge),
          if (action != null) ...[const SizedBox(height: 16), action!],
        ],
      ),
    );
  }
}

class SectionCard extends StatelessWidget {
  const SectionCard({super.key, this.title, this.trailing, required this.child, this.color});

  final String? title;
  final Widget? trailing;
  final Widget child;
  final Color? color;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Card(
      color: color,
      margin: const EdgeInsets.only(bottom: 12),
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            if (title != null)
              Padding(
                padding: const EdgeInsets.only(bottom: 12),
                child: Row(
                  children: [
                    Expanded(child: Text(title!, style: theme.textTheme.titleMedium)),
                    ?trailing,
                  ],
                ),
              ),
            child,
          ],
        ),
      ),
    );
  }
}

/// Campo de monto: solo dígitos y separadores, con validación.
class MoneyField extends StatelessWidget {
  const MoneyField({super.key, required this.controller, required this.label, this.autofocus = false});

  final TextEditingController controller;
  final String label;
  final bool autofocus;

  @override
  Widget build(BuildContext context) {
    return TextFormField(
      controller: controller,
      autofocus: autofocus,
      keyboardType: const TextInputType.numberWithOptions(decimal: true),
      inputFormatters: [FilteringTextInputFormatter.allow(RegExp(r'[\d.,]'))],
      decoration: InputDecoration(labelText: label, prefixText: '\$ '),
      validator: (v) => parseMoney(v ?? '') == null ? context.l.invalidAmount : null,
    );
  }
}

/// Fecha elegible con el selector del sistema.
class DateField extends StatelessWidget {
  const DateField({super.key, required this.label, required this.value, required this.onChanged});

  final String label;
  final DateTime value;
  final ValueChanged<DateTime> onChanged;

  @override
  Widget build(BuildContext context) {
    return InkWell(
      onTap: () async {
        final elegida = await showDatePicker(
          context: context,
          initialDate: value,
          firstDate: DateTime(value.year - 2),
          lastDate: DateTime(value.year + 3),
        );
        if (elegida != null) onChanged(elegida);
      },
      child: InputDecorator(
        decoration: InputDecoration(labelText: label, suffixIcon: const Icon(Icons.calendar_today)),
        child: Text(longDate(context, value)),
      ),
    );
  }
}

/// Barra de progreso con etiqueta y valor, usada en desgloses, metas y retos.
class LabeledProgress extends StatelessWidget {
  const LabeledProgress({super.key, required this.label, required this.value, required this.progress, this.color});

  final String label;
  final String value;
  final double progress;
  final Color? color;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Padding(
      padding: const EdgeInsets.only(bottom: 12),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Expanded(child: Text(label, style: theme.textTheme.bodyMedium)),
              Text(value, style: theme.textTheme.bodyMedium?.copyWith(fontWeight: FontWeight.w600)),
            ],
          ),
          const SizedBox(height: 6),
          // La barra crece desde cero al aparecer y se desliza cuando el dato cambia.
          TweenAnimationBuilder<double>(
            tween: Tween(begin: 0, end: progress.clamp(0, 1).toDouble()),
            duration: motion(context, const Duration(milliseconds: 600)),
            curve: kMotionCurve,
            builder: (context, v, _) => LinearProgressIndicator(
              value: v,
              minHeight: 8,
              borderRadius: BorderRadius.circular(4),
              color: color,
            ),
          ),
        ],
      ),
    );
  }
}

/// Envoltura estándar de formularios: botón de guardar con estado de carga.
class SaveButton extends StatelessWidget {
  const SaveButton({super.key, required this.saving, required this.onPressed, this.label});

  final bool saving;
  final VoidCallback onPressed;
  final String? label;

  @override
  Widget build(BuildContext context) {
    return FilledButton(
      onPressed: saving ? null : onPressed,
      style: FilledButton.styleFrom(minimumSize: const Size.fromHeight(52)),
      child: saving
          ? const SizedBox.square(dimension: 20, child: CircularProgressIndicator(strokeWidth: 2))
          : Text(label ?? context.l.save),
    );
  }
}
