import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../l10n/gen/app_localizations.dart';
import 'format.dart';
import 'motion.dart';
import 'theme.dart';

/// Para mostrar avisos (ej. el mensaje del coach) aunque la pantalla que los
/// originó ya se haya cerrado.
final messengerKey = GlobalKey<ScaffoldMessengerState>();

extension L10nX on BuildContext {
  AppLocalizations get l => AppLocalizations.of(this)!;
}

/// Espacio que ocupa abajo la barra de navegación flotante. El contenido de
/// las pestañas pasa por detrás de ella, así que cada lista lo suma a su margen.
double bottomInset(BuildContext context) => MediaQuery.paddingOf(context).bottom;

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
      hijo = const _Skeleton(key: ValueKey('carga'));
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
          FadeSlideIn(
            child: Container(
              width: 88,
              height: 88,
              decoration: BoxDecoration(color: theme.colorScheme.primaryContainer, shape: BoxShape.circle),
              child: Icon(icon, size: 40, color: theme.colorScheme.onPrimaryContainer),
            ),
          ),
          const SizedBox(height: 16),
          Text(text, textAlign: TextAlign.center, style: theme.textTheme.bodyLarge),
          if (action != null) ...[const SizedBox(height: 16), action!],
        ],
      ),
    );
  }
}

/// Tarjeta del mosaico: esquinas amplias, título opcional y, si se puede tocar,
/// respuesta al tacto. Es la base de todas las tarjetas de la app.
class BentoTile extends StatelessWidget {
  const BentoTile({
    super.key,
    this.title,
    this.trailing,
    required this.child,
    this.color,
    this.foreground,
    this.gradient,
    this.onTap,
    this.padding = const EdgeInsets.all(16),
  });

  final String? title;
  final Widget? trailing;
  final Widget child;
  final Color? color;

  /// Color del título cuando la tarjeta tiene fondo de acento.
  final Color? foreground;
  final Gradient? gradient;
  final VoidCallback? onTap;
  final EdgeInsetsGeometry padding;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final radio = BorderRadius.circular(AppTokens.radius);
    final contenido = Padding(
      padding: padding,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          if (title != null)
            Padding(
              padding: const EdgeInsets.only(bottom: 12),
              child: Row(
                children: [
                  Expanded(
                    child: Text(title!, style: theme.textTheme.titleMedium?.copyWith(color: foreground)),
                  ),
                  ?trailing,
                ],
              ),
            ),
          child,
        ],
      ),
    );
    return Pressable(
      enabled: onTap != null,
      child: Material(
        color: gradient == null ? (color ?? theme.cardTheme.color) : Colors.transparent,
        borderRadius: radio,
        clipBehavior: Clip.antiAlias,
        child: Ink(
          decoration: gradient == null ? null : BoxDecoration(gradient: gradient, borderRadius: radio),
          child: onTap == null
              ? contenido
              : InkWell(
                  onTap: () {
                    tapFeedback();
                    onTap!();
                  },
                  child: contenido,
                ),
        ),
      ),
    );
  }
}

/// Fila del mosaico: tarjetas lado a lado, todas de la misma altura. En
/// pantallas angostas o con la letra muy grande pasan a apilarse.
class BentoRow extends StatelessWidget {
  const BentoRow({super.key, required this.children, this.flex});

  final List<Widget> children;

  /// Proporción de ancho de cada tarjeta; por defecto todas iguales.
  final List<int>? flex;

  static bool stacks(BuildContext context) =>
      MediaQuery.sizeOf(context).width < 340 || MediaQuery.textScalerOf(context).scale(10) > 13;

  @override
  Widget build(BuildContext context) {
    if (stacks(context)) {
      return Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          for (final (i, hijo) in children.indexed) ...[
            if (i > 0) const SizedBox(height: AppTokens.gap),
            hijo,
          ],
        ],
      );
    }
    return IntrinsicHeight(
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          for (final (i, hijo) in children.indexed) ...[
            if (i > 0) const SizedBox(width: AppTokens.gap),
            Expanded(flex: flex?[i] ?? 1, child: hijo),
          ],
        ],
      ),
    );
  }
}

/// Pestañas de una pantalla, con el margen del mosaico.
class PillTabs extends StatelessWidget {
  const PillTabs({super.key, required this.labels});

  final List<String> labels;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.fromLTRB(16, 12, 16, 4),
      // Las pestañas no crecen sin límite con la letra del teléfono: dejarían de caber.
      child: MediaQuery.withClampedTextScaling(
        maxScaleFactor: 1.3,
        child: TabBar(tabs: [for (final texto in labels) Tab(text: texto, height: 44)]),
      ),
    );
  }
}

/// Tarjeta con título de sección, separada de la siguiente.
class SectionCard extends StatelessWidget {
  const SectionCard({super.key, this.title, this.trailing, required this.child, this.color, this.foreground, this.onTap});

  final String? title;
  final Widget? trailing;
  final Widget child;
  final Color? color;
  final Color? foreground;
  final VoidCallback? onTap;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(bottom: AppTokens.gap),
      child: BentoTile(title: title, trailing: trailing, color: color, foreground: foreground, onTap: onTap, child: child),
    );
  }
}

/// Anillo de avance que crece desde cero, con contenido en el centro.
class ProgressRing extends StatelessWidget {
  const ProgressRing({super.key, required this.progress, this.size = 64, this.stroke = 7, this.color, this.track, this.child});

  final double progress;
  final double size;
  final double stroke;
  final Color? color;
  final Color? track;
  final Widget? child;

  @override
  Widget build(BuildContext context) {
    return SizedBox.square(
      dimension: size,
      child: Stack(
        alignment: Alignment.center,
        children: [
          TweenAnimationBuilder<double>(
            tween: Tween(begin: 0, end: progress.clamp(0, 1).toDouble()),
            duration: motion(context, const Duration(milliseconds: 800)),
            curve: kMotionCurve,
            builder: (context, v, _) => SizedBox.square(
              dimension: size - stroke,
              child: CircularProgressIndicator(
                value: v,
                strokeWidth: stroke,
                strokeCap: StrokeCap.round,
                color: color,
                backgroundColor: track,
              ),
            ),
          ),
          ?child,
        ],
      ),
    );
  }
}

/// Ícono dentro de un círculo de color suave, para encabezar tarjetas y filas.
class IconBadge extends StatelessWidget {
  const IconBadge({super.key, required this.icon, this.color, this.foreground, this.size = 40});

  final IconData icon;
  final Color? color;
  final Color? foreground;
  final double size;

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    return Container(
      width: size,
      height: size,
      decoration: BoxDecoration(color: color ?? scheme.primaryContainer, shape: BoxShape.circle),
      child: Icon(icon, size: size * 0.5, color: foreground ?? scheme.onPrimaryContainer),
    );
  }
}

/// Lo que se ve mientras llega un dato: bloques con brillo en vez de un spinner.
class _Skeleton extends StatelessWidget {
  const _Skeleton({super.key});

  @override
  Widget build(BuildContext context) {
    return const Padding(
      padding: EdgeInsets.symmetric(vertical: 8),
      child: Shimmer(
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            SkeletonBox(height: 120, radius: AppTokens.radius),
            SizedBox(height: AppTokens.gap),
            Row(
              children: [
                Expanded(child: SkeletonBox(height: 84, radius: AppTokens.radius)),
                SizedBox(width: AppTokens.gap),
                Expanded(child: SkeletonBox(height: 84, radius: AppTokens.radius)),
              ],
            ),
          ],
        ),
      ),
    );
  }
}

/// Campo de monto: solo dígitos y separadores, con validación. Con [hero] es
/// el protagonista del formulario: cifra grande y centrada.
class MoneyField extends StatelessWidget {
  const MoneyField({
    super.key,
    required this.controller,
    required this.label,
    this.autofocus = false,
    this.hero = false,
  });

  final TextEditingController controller;
  final String label;
  final bool autofocus;
  final bool hero;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final cifra = theme.textTheme.displaySmall?.copyWith(fontFeatures: kTabular);
    return TextFormField(
      controller: controller,
      autofocus: autofocus,
      keyboardType: const TextInputType.numberWithOptions(decimal: true),
      inputFormatters: [FilteringTextInputFormatter.allow(RegExp(r'[\d.,]'))],
      style: hero ? cifra : null,
      decoration: hero
          ? InputDecoration(
              labelText: label,
              floatingLabelBehavior: FloatingLabelBehavior.always,
              hintText: '0',
              hintStyle: cifra?.copyWith(color: theme.colorScheme.outlineVariant),
              prefixText: '\$ ',
              prefixStyle: cifra?.copyWith(color: theme.colorScheme.onSurfaceVariant),
              contentPadding: const EdgeInsets.fromLTRB(20, 28, 20, 20),
              border: OutlineInputBorder(
                borderRadius: BorderRadius.circular(AppTokens.radius),
                borderSide: BorderSide.none,
              ),
            )
          : InputDecoration(labelText: label, prefixText: '\$ '),
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
              minHeight: 10,
              borderRadius: BorderRadius.circular(5),
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
