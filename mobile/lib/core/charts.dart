import 'dart:math' as math;

import 'package:fl_chart/fl_chart.dart';
import 'package:flutter/material.dart';

import 'format.dart';
import 'motion.dart';

/// Tonos de las gráficas. A propósito no hay un rojo ni un verde "de semáforo":
/// una categoría no es buena ni mala (principio de cero culpa).
const _paleta = [
  Color(0xFF1F6F5C),
  Color(0xFF3B7DD8),
  Color(0xFFE0A23B),
  Color(0xFF8A63D2),
  Color(0xFFE07A5F),
  Color(0xFF3BA7B8),
  Color(0xFFC95C9A),
  Color(0xFF6B7A99),
];

int _hash(String texto) => texto.codeUnits.fold(7, (h, c) => (h * 31 + c) & 0x7fffffff);

/// Un color por categoría. Sale del nombre, así que la misma categoría conserva
/// su color de una semana a otra; si dos chocan, la segunda toma el siguiente libre.
Map<String, Color> categoryColors(Iterable<String> nombres, Brightness brillo) {
  final usados = <int>{};
  final colores = <String, Color>{};
  for (final nombre in nombres) {
    var i = _hash(nombre) % _paleta.length;
    if (usados.length < _paleta.length) {
      while (usados.contains(i)) {
        i = (i + 1) % _paleta.length;
      }
    }
    usados.add(i);
    colores[nombre] = brillo == Brightness.dark ? Color.lerp(_paleta[i], Colors.white, 0.3)! : _paleta[i];
  }
  return colores;
}

typedef Slice = ({String label, double value});

/// Deja las [max] porciones más grandes y junta el resto en una sola, para
/// que la torta siga siendo legible con muchas categorías.
List<Slice> groupSlices(Iterable<Slice> porciones, {required String otherLabel, int max = 5}) {
  final orden = porciones.where((p) => p.value > 0).toList()..sort((a, b) => b.value.compareTo(a.value));
  if (orden.length <= max + 1) return orden;
  final resto = orden.skip(max).fold(0.0, (suma, p) => suma + p.value);
  return [...orden.take(max), (label: otherLabel, value: resto)];
}

/// Monto abreviado para los ejes: `1,2M`, `120k`, `800`.
String compactMoney(double valor) {
  if (valor >= 1000000) return '${(valor / 1000000).toStringAsFixed(1).replaceAll('.0', '').replaceAll('.', ',')}M';
  if (valor >= 1000) return '${(valor / 1000).round()}k';
  return '${valor.round()}';
}

/// Torta tipo dona con el total en el centro y su leyenda. Tocar una porción
/// la resalta y muestra su porcentaje.
class CategoryDonut extends StatefulWidget {
  const CategoryDonut({super.key, required this.slices, required this.otherLabel, this.compact = false});

  final List<Slice> slices;
  final String otherLabel;

  /// Versión pequeña para el inicio: dona más chica y leyenda de 3 renglones.
  final bool compact;

  @override
  State<CategoryDonut> createState() => _CategoryDonutState();
}

class _CategoryDonutState extends State<CategoryDonut> {
  int? _tocada;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final scheme = theme.colorScheme;
    final porciones = groupSlices(widget.slices, otherLabel: widget.otherLabel, max: widget.compact ? 3 : 5);
    final total = porciones.fold(0.0, (suma, p) => suma + p.value);
    if (total <= 0) return const SizedBox.shrink();

    final colores = categoryColors(
      porciones.map((p) => p.label).where((n) => n != widget.otherLabel),
      theme.brightness,
    );
    Color color(Slice p) => colores[p.label] ?? scheme.outlineVariant;
    int pct(Slice p) => (p.value / total * 100).round();

    final lado = widget.compact ? 104.0 : 164.0;
    final grosor = widget.compact ? 16.0 : 22.0;
    final tocada = _tocada != null && _tocada! < porciones.length ? porciones[_tocada!] : null;

    final dona = SizedBox.square(
      dimension: lado,
      child: Stack(
        alignment: Alignment.center,
        children: [
          // Al aparecer, la dona se dibuja en abanico: una porción invisible
          // ocupa lo que aún falta por mostrar.
          TweenAnimationBuilder<double>(
            tween: Tween(begin: 0, end: 1),
            duration: motion(context, const Duration(milliseconds: 800)),
            curve: kMotionCurve,
            builder: (context, t, _) => PieChart(
              PieChartData(
                startDegreeOffset: -90,
                sectionsSpace: 2,
                centerSpaceRadius: lado / 2 - grosor - 4,
                pieTouchData: PieTouchData(
                  touchCallback: (evento, respuesta) {
                    if (!evento.isInterestedForInteractions) return;
                    final i = respuesta?.touchedSection?.touchedSectionIndex;
                    final nueva = i == null || i < 0 || i >= porciones.length ? null : i;
                    if (nueva != _tocada) setState(() => _tocada = nueva);
                  },
                ),
                sections: [
                  for (final (i, p) in porciones.indexed)
                    PieChartSectionData(
                      value: p.value * t,
                      color: color(p),
                      radius: i == _tocada ? grosor + 4 : grosor,
                      showTitle: false,
                    ),
                  if (t < 1)
                    PieChartSectionData(
                      value: total * (1 - t),
                      color: Colors.transparent,
                      radius: grosor,
                      showTitle: false,
                    ),
                ],
              ),
              // Mientras se dibuja manda la animación de entrada; después, la
              // propia de la gráfica suaviza el resaltado al tocar.
              duration: t < 1 ? Duration.zero : motion(context, const Duration(milliseconds: 250)),
              curve: kMotionCurve,
            ),
          ),
          IgnorePointer(
            child: SizedBox(
              width: lado - 2 * grosor - 20,
              child: Column(
                mainAxisSize: MainAxisSize.min,
                children: [
                  FittedBox(
                    fit: BoxFit.scaleDown,
                    child: Text(
                      tocada == null ? money(total) : '${pct(tocada)}%',
                      style: (widget.compact ? theme.textTheme.titleSmall : theme.textTheme.titleMedium)
                          ?.copyWith(fontWeight: FontWeight.w700),
                    ),
                  ),
                  if (tocada != null)
                    Text(
                      tocada.label,
                      style: theme.textTheme.labelSmall,
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                    ),
                ],
              ),
            ),
          ),
        ],
      ),
    );

    final leyenda = Column(
      mainAxisSize: MainAxisSize.min,
      children: [
        for (final (i, p) in porciones.indexed)
          Padding(
            padding: const EdgeInsets.symmetric(vertical: 4),
            child: Row(
              children: [
                AnimatedContainer(
                  duration: motion(context, const Duration(milliseconds: 200)),
                  width: i == _tocada ? 14 : 10,
                  height: i == _tocada ? 14 : 10,
                  decoration: BoxDecoration(color: color(p), shape: BoxShape.circle),
                ),
                const SizedBox(width: 8),
                Expanded(
                  child: Text(p.label, style: theme.textTheme.bodyMedium, maxLines: 1, overflow: TextOverflow.ellipsis),
                ),
                const SizedBox(width: 8),
                Text(
                  widget.compact ? '${pct(p)}%' : '${pct(p)}% · ${money(p.value)}',
                  style: theme.textTheme.bodyMedium?.copyWith(fontWeight: FontWeight.w600),
                ),
              ],
            ),
          ),
      ],
    );

    // La leyenda ya dice lo mismo en texto: el dibujo no se lee dos veces.
    final dibujo = Semantics(label: money(total), excludeSemantics: true, child: dona);
    // La versión completa lleva montos en la leyenda: necesita todo el ancho.
    if (!widget.compact) {
      return Column(children: [dibujo, const SizedBox(height: 16), leyenda]);
    }
    return Row(children: [dibujo, const SizedBox(width: 16), Expanded(child: leyenda)]);
  }
}

/// Una línea de la gráfica de tendencia.
class TrendSeries {
  const TrendSeries({required this.name, required this.values, this.secondary = false});

  final String name;
  final List<double> values;

  /// Serie de comparación: se dibuja tenue y punteada, sin relleno.
  final bool secondary;
}

/// Línea(s) de gasto en el tiempo, con una referencia punteada opcional.
class TrendLine extends StatelessWidget {
  const TrendLine({
    super.key,
    required this.series,
    required this.labels,
    this.reference,
    this.referenceLabel,
    this.height = 190,
  });

  final List<TrendSeries> series;

  /// Etiquetas del eje X, una por punto.
  final List<String> labels;
  final double? reference;
  final String? referenceLabel;
  final double height;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final scheme = theme.colorScheme;
    final puntos = labels.length;
    final maximo = [
      for (final s in series) ...s.values,
      reference ?? 0,
    ].fold(0.0, math.max);
    final techo = maximo <= 0 ? 1.0 : maximo * 1.2;
    final cada = math.max(1, (puntos / 5).ceil());
    final etiqueta = theme.textTheme.labelSmall?.copyWith(color: scheme.onSurfaceVariant);

    LineChartBarData linea(TrendSeries s) {
      final color = s.secondary ? scheme.outline : scheme.primary;
      return LineChartBarData(
        spots: [for (final (i, v) in s.values.indexed) FlSpot(i.toDouble(), v)],
        isCurved: true,
        preventCurveOverShooting: true,
        color: color,
        barWidth: s.secondary ? 2 : 3,
        isStrokeCapRound: true,
        dashArray: s.secondary ? [6, 5] : null,
        dotData: FlDotData(show: !s.secondary && puntos <= 14),
        belowBarData: BarAreaData(
          show: !s.secondary,
          gradient: LinearGradient(
            begin: Alignment.topCenter,
            end: Alignment.bottomCenter,
            colors: [color.withValues(alpha: 0.28), color.withValues(alpha: 0)],
          ),
        ),
      );
    }

    final grafica = LineChart(
      LineChartData(
        minX: 0,
        maxX: math.max(1, puntos - 1).toDouble(),
        minY: 0,
        maxY: techo,
        lineBarsData: series.map(linea).toList(),
        borderData: FlBorderData(show: false),
        gridData: FlGridData(
          drawVerticalLine: false,
          horizontalInterval: techo / 4,
          getDrawingHorizontalLine: (_) => FlLine(color: scheme.outlineVariant.withValues(alpha: 0.5), strokeWidth: 1),
        ),
        extraLinesData: ExtraLinesData(
          horizontalLines: [
            if (reference != null && reference! > 0)
              HorizontalLine(
                y: reference!,
                color: scheme.tertiary,
                strokeWidth: 1.5,
                dashArray: [4, 4],
                label: HorizontalLineLabel(
                  show: referenceLabel != null,
                  alignment: Alignment.topRight,
                  style: etiqueta?.copyWith(color: scheme.tertiary),
                  labelResolver: (_) => referenceLabel ?? '',
                ),
              ),
          ],
        ),
        titlesData: FlTitlesData(
          topTitles: const AxisTitles(),
          rightTitles: const AxisTitles(),
          leftTitles: AxisTitles(
            sideTitles: SideTitles(
              showTitles: true,
              reservedSize: 40,
              interval: techo / 4,
              getTitlesWidget: (valor, meta) => valor >= techo
                  ? const SizedBox.shrink()
                  : SideTitleWidget(meta: meta, child: Text(compactMoney(valor), style: etiqueta)),
            ),
          ),
          bottomTitles: AxisTitles(
            sideTitles: SideTitles(
              showTitles: true,
              reservedSize: 28,
              interval: 1,
              getTitlesWidget: (valor, meta) {
                final i = valor.round();
                // De derecha a izquierda, para que el punto más reciente siempre tenga etiqueta.
                if (valor != i.toDouble() || i < 0 || i >= puntos || (puntos - 1 - i) % cada != 0) {
                  return const SizedBox.shrink();
                }
                return SideTitleWidget(meta: meta, child: Text(labels[i], style: etiqueta));
              },
            ),
          ),
        ),
        lineTouchData: LineTouchData(
          touchTooltipData: LineTouchTooltipData(
            fitInsideHorizontally: true,
            fitInsideVertically: true,
            getTooltipColor: (_) => scheme.inverseSurface,
            getTooltipItems: (tocados) => [
              for (final t in tocados)
                LineTooltipItem(
                  series.length > 1 ? '${series[t.barIndex].name}: ${money(t.y)}' : money(t.y),
                  theme.textTheme.labelMedium!.copyWith(color: scheme.onInverseSurface),
                ),
            ],
          ),
        ),
      ),
      duration: motion(context, const Duration(milliseconds: 300)),
      curve: kMotionCurve,
    );

    final resumen = [
      for (final s in series)
        '${s.name}: ${[for (final (i, v) in s.values.indexed) '${labels[i]} ${money(v)}'].join(', ')}',
    ].join('. ');

    return Semantics(
      label: resumen,
      excludeSemantics: true,
      child: SizedBox(
        height: height,
        child: LayoutBuilder(
          // Al aparecer, la línea se descubre de izquierda a derecha.
          builder: (context, limites) => TweenAnimationBuilder<double>(
            tween: Tween(begin: 0, end: 1),
            duration: motion(context, const Duration(milliseconds: 900)),
            curve: Curves.easeOutQuart,
            child: SizedBox(width: limites.maxWidth, height: height, child: grafica),
            builder: (context, t, child) => ClipRect(
              child: Align(alignment: Alignment.centerLeft, widthFactor: t, child: child),
            ),
          ),
        ),
      ),
    );
  }
}

/// Leyenda de una línea: muestra de color y nombre.
class TrendLegend extends StatelessWidget {
  const TrendLegend({super.key, required this.series});

  final List<TrendSeries> series;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final scheme = theme.colorScheme;
    return Wrap(
      spacing: 16,
      children: [
        for (final s in series)
          Row(
            mainAxisSize: MainAxisSize.min,
            children: [
              Container(
                width: 14,
                height: 3,
                decoration: BoxDecoration(
                  color: s.secondary ? scheme.outline : scheme.primary,
                  borderRadius: BorderRadius.circular(2),
                ),
              ),
              const SizedBox(width: 6),
              Text(s.name, style: theme.textTheme.labelMedium),
            ],
          ),
      ],
    );
  }
}
