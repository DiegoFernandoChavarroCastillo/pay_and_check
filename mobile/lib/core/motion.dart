import 'package:flutter/material.dart';

import 'format.dart';

const kMotion = Duration(milliseconds: 350);
const kMotionCurve = Curves.easeOutCubic;

/// Duración de una animación, o cero si la persona pidió al teléfono quitar
/// las animaciones (accesibilidad): el resultado final se muestra de inmediato.
Duration motion(BuildContext context, [Duration duracion = kMotion]) =>
    MediaQuery.disableAnimationsOf(context) ? Duration.zero : duracion;

/// Monto que "cuenta" hasta su valor al aparecer y se desliza cuando cambia.
class AnimatedMoney extends StatelessWidget {
  const AnimatedMoney({super.key, required this.value, this.style});

  final double value;
  final TextStyle? style;

  @override
  Widget build(BuildContext context) {
    return TweenAnimationBuilder<double>(
      tween: Tween(begin: 0, end: value),
      duration: motion(context, const Duration(milliseconds: 700)),
      curve: kMotionCurve,
      builder: (context, v, _) => Text(money(v), style: style),
    );
  }
}

/// Entrada suave: el contenido aparece y sube unos píxeles. Con [index] las
/// tarjetas de una lista entran una tras otra en vez de todas a la vez.
class FadeSlideIn extends StatelessWidget {
  const FadeSlideIn({super.key, this.index = 0, required this.child});

  final int index;
  final Widget child;

  @override
  Widget build(BuildContext context) {
    final espera = 60 * index.clamp(0, 8);
    final total = 320 + espera;
    return TweenAnimationBuilder<double>(
      tween: Tween(begin: 0, end: 1),
      duration: motion(context, Duration(milliseconds: total)),
      curve: Interval(espera / total, 1, curve: kMotionCurve),
      child: child,
      builder: (context, t, child) => Opacity(
        opacity: t,
        child: Transform.translate(offset: Offset(0, 12 * (1 - t)), child: child),
      ),
    );
  }
}

/// Envuelve cada elemento de una lista en una entrada escalonada.
List<Widget> staggered(List<Widget> hijos) => [
      for (final (i, hijo) in hijos.indexed) FadeSlideIn(index: i, child: hijo),
    ];
