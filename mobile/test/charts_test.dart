import 'package:fl_chart/fl_chart.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:pay_and_check/core/charts.dart';
import 'package:pay_and_check/core/motion.dart';
import 'package:pay_and_check/features/home/home_screen.dart';
import 'package:pay_and_check/features/reports/analytics_screen.dart';

import 'fakes.dart';

void main() {
  test('groupSlices deja las más grandes y junta el resto en una sola', () {
    final porciones = [
      for (final (i, valor) in [10.0, 70.0, 0.0, 30.0, 20.0, 5.0, 50.0, 40.0].indexed) (label: 'c$i', value: valor),
    ];

    final grupos = groupSlices(porciones, otherLabel: 'Otras');

    expect(grupos.map((g) => g.label), ['c1', 'c6', 'c7', 'c3', 'c4', 'Otras']);
    expect(grupos.last.value, 15);
    // Con una sola de más no vale la pena agrupar: "Otras" sería una categoría con otro nombre.
    expect(groupSlices(porciones.take(7), otherLabel: 'Otras').map((g) => g.label), isNot(contains('Otras')));
  });

  test('categoryColors es estable y no repite color dentro de una gráfica', () {
    final nombres = ['comida', 'transporte', 'entretenimiento', 'salud', 'ropa', 'hogar'];
    final colores = categoryColors(nombres, Brightness.light);

    expect(colores.values.toSet().length, nombres.length);
    expect(categoryColors(['comida'], Brightness.light)['comida'], colores['comida']);
  });

  test('compactMoney abrevia los montos de los ejes', () {
    expect(compactMoney(800), '800');
    expect(compactMoney(120000), '120k');
    expect(compactMoney(1200000), '1,2M');
    expect(compactMoney(3000000), '3M');
  });

  testWidgets('el inicio muestra la dona de la semana y abre el análisis', (tester) async {
    await tester.pumpWidget(await appDePrueba(FakeApi()));
    await tester.pumpAndSettle();

    expect(find.text('Esta semana'), findsOneWidget);
    expect(find.byType(PieChart), findsOneWidget);
    expect(find.text('50% más que la semana anterior'), findsOneWidget);

    await tester.ensureVisible(find.text('Ver análisis'));
    await tester.tap(find.text('Ver análisis'));
    await tester.pumpAndSettle();

    expect(find.byType(AnalyticsScreen), findsOneWidget);
  });

  testWidgets('el análisis reparte la semana por categorías y deja comparar semanas', (tester) async {
    await tester.pumpWidget(await pantallaDePrueba(FakeApi(), const AnalyticsScreen()));
    await tester.pumpAndSettle();

    // Semana actual: 7 categorías se muestran como 5 + "Otras".
    expect(find.text('16 mar – 22 mar'), findsOneWidget);
    expect(find.text(r'40% · $ 24.000'), findsOneWidget);
    expect(find.text('Otras'), findsOneWidget);
    expect(find.text('regalos'), findsNothing);
    expect(find.text('50% más que la semana anterior'), findsOneWidget);
    expect(find.text(r'Promedio semanal: $ 33.333'), findsOneWidget);

    await tester.tap(find.byTooltip('Semana anterior'));
    await tester.pumpAndSettle();
    expect(find.text('9 mar – 15 mar'), findsOneWidget);
    expect(find.text(r'100% · $ 40.000'), findsOneWidget);

    // La más antigua no tiene gastos: se dice, en vez de dibujar una dona vacía.
    await tester.tap(find.byTooltip('Semana anterior'));
    await tester.pumpAndSettle();
    expect(find.text('Sin gastos registrados en esta semana.'), findsOneWidget);
    expect(find.byType(PieChart), findsNothing);
  });

  testWidgets('la tendencia cambia entre semanas y días', (tester) async {
    await tester.pumpWidget(await pantallaDePrueba(FakeApi(), const AnalyticsScreen()));
    await tester.pumpAndSettle();

    await tester.ensureVisible(find.text('Días'));
    await tester.pumpAndSettle();
    LineChart linea() => tester.widget<LineChart>(find.byType(LineChart));
    expect(linea().data.lineBarsData.single.spots.map((s) => s.y), [0, 40000, 60000]);

    await tester.tap(find.text('Días'));
    await tester.pumpAndSettle();
    // Dos líneas: esta semana y la anterior, de lunes a domingo.
    expect(linea().data.lineBarsData.length, 2);
    expect(linea().data.lineBarsData.last.spots.length, 7);
  });

  testWidgets('sin gastos el análisis muestra un estado vacío', (tester) async {
    await tester.pumpWidget(await pantallaDePrueba(FakeApi(conGastos: false), const AnalyticsScreen()));
    await tester.pumpAndSettle();

    expect(find.textContaining('Cuando registres gastos'), findsOneWidget);
    expect(find.byType(PieChart), findsNothing);
    expect(find.byType(LineChart), findsNothing);
  });

  testWidgets('con las animaciones desactivadas el valor final sale de inmediato', (tester) async {
    await tester.pumpWidget(
      await pantallaDePrueba(
        FakeApi(),
        const Scaffold(body: AnimatedMoney(value: 14258)),
        sinAnimaciones: true,
      ),
    );
    // Un solo cuadro, sin dejar correr el tiempo.
    await tester.pump();
    expect(find.text(r'$ 14.258'), findsOneWidget);
  });

  testWidgets('con animaciones, el monto cuenta hasta su valor', (tester) async {
    await tester.pumpWidget(await pantallaDePrueba(FakeApi(), const Scaffold(body: AnimatedMoney(value: 14258))));
    await tester.pump();
    expect(find.text(r'$ 14.258'), findsNothing);

    await tester.pumpAndSettle();
    expect(find.text(r'$ 14.258'), findsOneWidget);
  });

  testWidgets('el inicio sin gastos esta semana lo dice en vez de dibujar la dona', (tester) async {
    await tester.pumpWidget(await pantallaDePrueba(FakeApi(conGastos: false), Scaffold(body: HomeScreen(onOpenCoach: () {}))));
    await tester.pumpAndSettle();

    expect(find.text('Sin gastos registrados en esta semana.'), findsOneWidget);
    expect(find.byType(PieChart), findsNothing);
  });
}
