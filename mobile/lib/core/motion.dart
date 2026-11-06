import 'dart:math' as math;

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import 'format.dart';

const kMotion = Duration(milliseconds: 350);
const kMotionCurve = Curves.easeOutCubic;

/// Curva con un rebote leve, para lo que "aterriza": tarjetas, selección.
const kSpring = Curves.easeOutBack;

/// Las animaciones que no terminan nunca (el coach que respira, la racha que
/// late) se apagan en las pruebas: si no, `pumpAndSettle` no acabaría.
bool ambientMotionEnabled = true;

/// Si se pueden mostrar animaciones en bucle.
bool ambient(BuildContext context) => ambientMotionEnabled && !MediaQuery.disableAnimationsOf(context);

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

/// Número entero que cuenta hasta su valor (puntos, porcentajes, días).
class AnimatedCount extends StatelessWidget {
  const AnimatedCount({super.key, required this.value, this.style, this.format});

  final int value;
  final TextStyle? style;
  final String Function(int valor)? format;

  @override
  Widget build(BuildContext context) {
    return TweenAnimationBuilder<double>(
      tween: Tween(begin: 0, end: value.toDouble()),
      duration: motion(context, const Duration(milliseconds: 700)),
      curve: kMotionCurve,
      builder: (context, v, _) => Text(format?.call(v.round()) ?? '${v.round()}', style: style),
    );
  }
}

/// Respuesta al tacto: el contenido se encoge un poco al presionarlo y vuelve
/// con un rebote. No atrapa el toque; eso lo hace el `InkWell` de dentro.
class Pressable extends StatefulWidget {
  const Pressable({super.key, required this.child, this.enabled = true});

  final Widget child;
  final bool enabled;

  @override
  State<Pressable> createState() => _PressableState();
}

class _PressableState extends State<Pressable> {
  bool _abajo = false;

  void _set(bool abajo) {
    if (!widget.enabled || abajo == _abajo) return;
    setState(() => _abajo = abajo);
  }

  @override
  Widget build(BuildContext context) {
    return Listener(
      onPointerDown: (_) => _set(true),
      onPointerUp: (_) => _set(false),
      onPointerCancel: (_) => _set(false),
      child: AnimatedScale(
        scale: _abajo ? 0.97 : 1,
        duration: motion(context, Duration(milliseconds: _abajo ? 90 : 320)),
        curve: _abajo ? Curves.easeOut : kSpring,
        child: widget.child,
      ),
    );
  }
}

/// Vibración corta al tocar algo que responde.
void tapFeedback() => HapticFeedback.selectionClick();

/// Brillo que recorre los bloques de carga. Sin animaciones queda quieto.
class Shimmer extends StatefulWidget {
  const Shimmer({super.key, required this.child});

  final Widget child;

  @override
  State<Shimmer> createState() => _ShimmerState();
}

class _ShimmerState extends State<Shimmer> with SingleTickerProviderStateMixin {
  late final _c = AnimationController(vsync: this, duration: const Duration(milliseconds: 1300));

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    if (MediaQuery.disableAnimationsOf(context)) {
      _c.stop();
    } else if (!_c.isAnimating) {
      _c.repeat();
    }
  }

  @override
  void dispose() {
    _c.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    final base = scheme.surfaceContainerHighest;
    final luz = scheme.surfaceContainerLowest;
    return AnimatedBuilder(
      animation: _c,
      child: widget.child,
      builder: (context, child) => ShaderMask(
        blendMode: BlendMode.srcATop,
        shaderCallback: (rect) => LinearGradient(
          begin: Alignment(-1 + 3 * _c.value - 1, 0),
          end: Alignment(3 * _c.value - 1, 0),
          colors: [base, luz, base],
        ).createShader(rect),
        child: child,
      ),
    );
  }
}

/// Bloque gris redondeado que ocupa el lugar de un contenido que está cargando.
class SkeletonBox extends StatelessWidget {
  const SkeletonBox({super.key, this.height = 16, this.width, this.radius = 12});

  final double height;
  final double? width;
  final double radius;

  @override
  Widget build(BuildContext context) {
    return Container(
      height: height,
      width: width,
      decoration: BoxDecoration(
        color: Theme.of(context).colorScheme.surfaceContainerHighest,
        borderRadius: BorderRadius.circular(radius),
      ),
    );
  }
}

/// Celebración: un estallido de papelitos que cae y se desvanece una sola vez.
/// Se pone encima de lo que se celebra; no recibe toques.
class ConfettiBurst extends StatefulWidget {
  const ConfettiBurst({super.key, required this.colors, this.count = 42});

  final List<Color> colors;
  final int count;

  @override
  State<ConfettiBurst> createState() => _ConfettiBurstState();
}

class _ConfettiBurstState extends State<ConfettiBurst> with SingleTickerProviderStateMixin {
  late final _c = AnimationController(vsync: this, duration: const Duration(milliseconds: 1600));
  late final _piezas = [
    for (var i = 0, r = math.Random(7); i < widget.count; i++)
      (
        angulo: -math.pi / 2 + (r.nextDouble() - 0.5) * 2.4,
        fuerza: 0.45 + r.nextDouble() * 0.55,
        giro: (r.nextDouble() - 0.5) * 10,
        lado: 5 + r.nextDouble() * 5,
        color: widget.colors[i % widget.colors.length],
      ),
  ];
  bool _lanzado = false;

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    if (!_lanzado && !MediaQuery.disableAnimationsOf(context)) _c.forward();
    _lanzado = true;
  }

  @override
  void dispose() {
    _c.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return IgnorePointer(
      child: AnimatedBuilder(
        animation: _c,
        builder: (context, _) => CustomPaint(
          size: Size.infinite,
          painter: _ConfettiPainter(_c.value, _piezas),
        ),
      ),
    );
  }
}

typedef _Pieza = ({double angulo, double fuerza, double giro, double lado, Color color});

class _ConfettiPainter extends CustomPainter {
  _ConfettiPainter(this.t, this.piezas);

  final double t;
  final List<_Pieza> piezas;

  @override
  void paint(Canvas canvas, Size size) {
    if (t <= 0 || t >= 1) return;
    final origen = Offset(size.width / 2, size.height * 0.35);
    final alcance = size.shortestSide * 0.9;
    final avance = Curves.easeOutCubic.transform(t);
    final pintura = Paint();
    for (final p in piezas) {
      final dx = math.cos(p.angulo) * p.fuerza * alcance * avance;
      // Sube con el impulso y cae con la gravedad.
      final dy = math.sin(p.angulo) * p.fuerza * alcance * avance + size.height * 0.55 * t * t;
      pintura.color = p.color.withValues(alpha: (1 - t * t).clamp(0, 1).toDouble());
      canvas
        ..save()
        ..translate(origen.dx + dx, origen.dy + dy)
        ..rotate(p.giro * t)
        ..drawRRect(
          RRect.fromRectAndRadius(
            Rect.fromCenter(center: Offset.zero, width: p.lado, height: p.lado * 1.6),
            const Radius.circular(1.5),
          ),
          pintura,
        )
        ..restore();
    }
  }

  @override
  bool shouldRepaint(_ConfettiPainter old) => old.t != t;
}

/// Latido suave y continuo, para llamar la atención sin distraer (la racha).
class Breathing extends StatefulWidget {
  const Breathing({super.key, required this.child, this.amount = 0.08});

  final Widget child;
  final double amount;

  @override
  State<Breathing> createState() => _BreathingState();
}

class _BreathingState extends State<Breathing> with SingleTickerProviderStateMixin {
  late final _c = AnimationController(vsync: this, duration: const Duration(milliseconds: 1400));

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    if (!ambient(context)) {
      _c.value = 0;
      _c.stop();
    } else if (!_c.isAnimating) {
      _c.repeat(reverse: true);
    }
  }

  @override
  void dispose() {
    _c.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return ScaleTransition(
      scale: Tween(begin: 1.0, end: 1 + widget.amount).animate(CurvedAnimation(parent: _c, curve: Curves.easeInOut)),
      child: widget.child,
    );
  }
}
