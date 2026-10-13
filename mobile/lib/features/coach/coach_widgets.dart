import 'dart:math' as math;

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/format.dart';
import '../../core/motion.dart';
import '../../core/theme.dart';
import '../../core/widgets.dart';
import '../../data/api.dart';
import '../../data/models.dart';
import '../../data/providers.dart';
import '../../l10n/gen/app_localizations.dart';
import '../progress/goal_dialogs.dart';

const moodEmojis = {
  'ansioso': '😰',
  'preocupado': '😟',
  'neutral': '😐',
  'tranquilo': '🙂',
  'confiado': '😄',
};

String moodLabel(AppLocalizations l, String animo) => switch (animo) {
      'ansioso' => l.moodAnxious,
      'preocupado' => l.moodWorried,
      'tranquilo' => l.moodCalm,
      'confiado' => l.moodConfident,
      _ => l.moodNeutral,
    };

/// Color del coach según el ánimo. Ninguno es rojo: un mal día no es una falta.
const moodColors = {
  'ansioso': Color(0xFF8A63D2),
  'preocupado': Color(0xFF3B7DD8),
  'neutral': Color(0xFF3BA7B8),
  'tranquilo': Color(0xFF2E9C82),
  'confiado': Color(0xFFE0A23B),
};

/// El coach: una forma orgánica que respira. No es una cara ni un personaje,
/// es una presencia. Sin animaciones queda quieta.
class CoachOrb extends StatefulWidget {
  const CoachOrb({super.key, this.size = 48, this.color});

  final double size;
  final Color? color;

  @override
  State<CoachOrb> createState() => _CoachOrbState();
}

class _CoachOrbState extends State<CoachOrb> with SingleTickerProviderStateMixin {
  late final _c = AnimationController(vsync: this, duration: const Duration(seconds: 7));

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    if (!ambient(context)) {
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
    final color = widget.color ?? moodColors['ansioso']!;
    return ExcludeSemantics(
      child: TweenAnimationBuilder<Color?>(
        tween: ColorTween(end: color),
        duration: motion(context, const Duration(milliseconds: 600)),
        builder: (context, c, _) => AnimatedBuilder(
          animation: _c,
          builder: (context, _) => CustomPaint(
            size: Size.square(widget.size),
            painter: _OrbPainter(_c.value * 2 * math.pi, c ?? color),
          ),
        ),
      ),
    );
  }
}

class _OrbPainter extends CustomPainter {
  _OrbPainter(this.fase, this.color);

  final double fase;
  final Color color;

  Path _forma(Offset centro, double radio, double fase) {
    final path = Path();
    const pasos = 48;
    for (var i = 0; i <= pasos; i++) {
      final a = 2 * math.pi * i / pasos;
      final r = radio * (1 + 0.07 * math.sin(3 * a + fase) + 0.05 * math.sin(2 * a - fase * 2));
      final p = centro + Offset(math.cos(a), math.sin(a)) * r;
      i == 0 ? path.moveTo(p.dx, p.dy) : path.lineTo(p.dx, p.dy);
    }
    return path..close();
  }

  @override
  void paint(Canvas canvas, Size size) {
    final centro = size.center(Offset.zero);
    final radio = size.shortestSide / 2 * 0.8 * (1 + 0.03 * math.sin(fase));
    final area = Rect.fromCircle(center: centro, radius: radio);

    // Halo: la misma forma, más grande y difusa.
    canvas.drawPath(
      _forma(centro, radio * 1.08, -fase),
      Paint()
        ..color = color.withValues(alpha: 0.28)
        ..maskFilter = MaskFilter.blur(BlurStyle.normal, size.shortestSide * 0.08),
    );
    canvas.drawPath(
      _forma(centro, radio, fase),
      Paint()
        ..shader = RadialGradient(
          center: Alignment(-0.4 + 0.2 * math.cos(fase), -0.5 + 0.2 * math.sin(fase)),
          radius: 1.1,
          colors: [Color.lerp(color, Colors.white, 0.65)!, color, Color.lerp(color, Colors.black, 0.18)!],
          stops: const [0, 0.6, 1],
        ).createShader(area),
    );
  }

  @override
  bool shouldRepaint(_OrbPainter old) => old.fase != fase || old.color != color;
}

/// El coach con el color del ánimo de hoy, y un saltito cada vez que se
/// registra un gasto.
class CoachAvatar extends ConsumerStatefulWidget {
  const CoachAvatar({super.key, this.size = 48});

  final double size;

  @override
  ConsumerState<CoachAvatar> createState() => _CoachAvatarState();
}

class _CoachAvatarState extends ConsumerState<CoachAvatar> {
  int _saltos = 0;

  @override
  Widget build(BuildContext context) {
    ref.listen(summaryProvider, (antes, ahora) {
      final a = antes?.value?.gastadoTotal, b = ahora.value?.gastadoTotal;
      if (a != null && b != null && b > a) setState(() => _saltos++);
    });
    final checkins = ref.watch(checkinsProvider).value ?? const <Checkin>[];
    final hoy = today();
    final animo = checkins.where((c) => c.fecha == hoy).firstOrNull?.animo;
    final orbe = CoachOrb(size: widget.size, color: moodColors[animo]);
    if (_saltos == 0) return orbe;
    return TweenAnimationBuilder<double>(
      key: ValueKey(_saltos),
      tween: Tween(begin: 1.25, end: 1),
      duration: motion(context, const Duration(milliseconds: 600)),
      curve: kSpring,
      builder: (context, escala, child) => Transform.scale(scale: escala, child: child),
      child: orbe,
    );
  }
}

/// Check-in diario: un toque para decir cómo te sientes con tu dinero hoy.
class CheckinCard extends ConsumerWidget {
  const CheckinCard({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final l = context.l;
    final hoy = today();
    final checkins = ref.watch(checkinsProvider).value ?? const <Checkin>[];
    final deHoy = checkins.where((c) => c.fecha == hoy).firstOrNull;

    Future<void> registrar(String animo) async {
      final ok = await guarded(context, () => ref.read(apiProvider).checkin(animo));
      if (ok) refreshData(ref);
    }

    return SectionCard(
      title: deHoy == null ? l.checkinQuestion : l.checkinDone,
      child: Row(
        mainAxisAlignment: MainAxisAlignment.spaceBetween,
        children: [
          for (final animo in moodEmojis.keys)
            Semantics(
              button: true,
              selected: deHoy?.animo == animo,
              label: moodLabel(l, animo),
              child: InkWell(
                borderRadius: BorderRadius.circular(16),
                onTap: () => registrar(animo),
                child: AnimatedContainer(
                  duration: motion(context, const Duration(milliseconds: 250)),
                  width: 56,
                  padding: const EdgeInsets.symmetric(vertical: 8),
                  decoration: BoxDecoration(
                    borderRadius: BorderRadius.circular(16),
                    color: deHoy?.animo == animo
                        ? Theme.of(context).colorScheme.primaryContainer
                        : Theme.of(context).colorScheme.primaryContainer.withValues(alpha: 0),
                  ),
                  child: Column(
                    children: [
                      // El ánimo elegido crece con un rebote leve.
                      AnimatedScale(
                        scale: deHoy?.animo == animo ? 1.2 : 1,
                        duration: motion(context),
                        curve: Curves.easeOutBack,
                        child: ExcludeSemantics(child: Text(moodEmojis[animo]!, style: const TextStyle(fontSize: 28))),
                      ),
                      const SizedBox(height: 4),
                      // La etiqueta se encoge si no cabe ("Confianza"), en vez de cortarse.
                      ExcludeSemantics(
                        child: Padding(
                          padding: const EdgeInsets.symmetric(horizontal: 2),
                          child: FittedBox(
                            fit: BoxFit.scaleDown,
                            child: Text(moodLabel(l, animo), style: Theme.of(context).textTheme.labelSmall),
                          ),
                        ),
                      ),
                    ],
                  ),
                ),
              ),
            ),
        ],
      ),
    );
  }
}

/// Un consejo del coach con su acción de un tap. La acción solo se ejecuta
/// cuando el usuario la toca: el coach propone, la persona decide.
class InsightCard extends ConsumerStatefulWidget {
  const InsightCard({super.key, required this.insight});

  final Insight insight;

  @override
  ConsumerState<InsightCard> createState() => _InsightCardState();
}

class _InsightCardState extends ConsumerState<InsightCard> {
  bool _busy = false;
  bool _done = false;

  Future<void> _ejecutar(InsightAction accion) async {
    final api = ref.read(apiProvider);
    final l = context.l;

    if (accion.tipo == 'crear_meta') {
      await showGoalDialog(context, ref);
      return;
    }

    setState(() => _busy = true);
    final ok = await guarded(context, () async {
      switch (accion.tipo) {
        case 'crear_reto':
          await api.createChallenge(accion.payload);
        case 'poner_limite':
          await api.updateCategory(accion.payload['category_id'] as int, {'limite': accion.payload['limite']});
        case 'apartar_meta':
          await api.contribute(
            accion.payload['goal_id'] as int,
            double.parse(accion.payload['monto'].toString()),
          );
      }
    });
    if (!mounted) return;
    setState(() {
      _busy = false;
      _done = ok;
    });
    if (ok) {
      refreshData(ref);
      showSnack(l.actionDone);
    }
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final coach = context.tokens.coach;
    final insight = widget.insight;
    final accion = insight.accion;
    return SectionCard(
      color: coach.container,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              const CoachAvatar(size: 40),
              const SizedBox(width: 12),
              Expanded(
                child: Padding(
                  padding: const EdgeInsets.only(top: 4),
                  child: Text(
                    insight.mensaje,
                    style: theme.textTheme.bodyLarge?.copyWith(color: coach.onContainer, fontWeight: FontWeight.w500),
                  ),
                ),
              ),
            ],
          ),
          // Explicabilidad: el dato en que se basa el consejo, si la IA lo reescribió.
          if (insight.mensaje != insight.descripcion)
            Padding(
              padding: const EdgeInsets.only(top: 8, left: 52),
              child: Text(
                '${context.l.whyThis} ${insight.descripcion}',
                style: theme.textTheme.bodySmall?.copyWith(color: coach.onContainer.withValues(alpha: 0.75)),
              ),
            ),
          if (accion != null) ...[
            const SizedBox(height: 12),
            Align(
              alignment: Alignment.centerRight,
              child: FilledButton.icon(
                onPressed: _busy || _done ? null : () => _ejecutar(accion),
                style: FilledButton.styleFrom(backgroundColor: coach.color),
                icon: Icon(_done ? Icons.check : Icons.bolt),
                label: Text(_done ? context.l.actionDone : accion.etiqueta),
              ),
            ),
          ],
        ],
      ),
    );
  }
}
