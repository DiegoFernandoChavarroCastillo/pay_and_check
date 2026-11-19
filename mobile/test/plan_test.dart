import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:pay_and_check/core/format.dart';
import 'package:pay_and_check/features/profile/plan_screen.dart';
import 'package:pay_and_check/features/transactions/add_sheet.dart';

import 'fakes.dart';

void main() {
  testWidgets('Mi plan muestra el plan, el cupo usado y los otros planes', (tester) async {
    await tester.pumpWidget(await pantallaDePrueba(FakeApi(), const PlanScreen()));
    await tester.pumpAndSettle();

    expect(find.byKey(const ValueKey('plan-actual')), findsOneWidget);
    expect(tester.widget<Text>(find.byKey(const ValueKey('plan-actual'))).data, 'Gratis');
    expect(find.text('12 de 50 usadas'), findsOneWidget);
    await tester.dragUntilVisible(find.text('Familiar'), find.byType(ListView), const Offset(0, -200));
    expect(find.text('Premium'), findsOneWidget);
    expect(find.text('Se activa con el código de convenio de tu universidad.'), findsOneWidget);
  });

  testWidgets('cambiar a Premium avisa que es simulado y actualiza el plan', (tester) async {
    final api = FakeApi();
    await tester.pumpWidget(await pantallaDePrueba(api, const PlanScreen()));
    await tester.pumpAndSettle();

    final boton = find.widgetWithText(OutlinedButton, 'Cambiar a este plan');
    await tester.dragUntilVisible(boton.first, find.byType(ListView), const Offset(0, -200));
    await tester.ensureVisible(boton.first);
    await tester.pumpAndSettle();
    await tester.tap(boton.first);
    await tester.pumpAndSettle();
    expect(find.text('Es una simulación: no se te cobrará nada. Tu cupo de IA cambia de inmediato.'), findsOneWidget);
    await tester.tap(find.text('Confirmar'));
    await tester.pumpAndSettle();

    expect(api.planesElegidos, ['premium']);
    await tester.dragUntilVisible(find.text('12 de 300 usadas'), find.byType(ListView), const Offset(0, 200));
    expect(find.text('12 de 300 usadas'), findsOneWidget);
  });

  testWidgets('canjear un código de convenio activa Institucional', (tester) async {
    final api = FakeApi();
    await tester.pumpWidget(await pantallaDePrueba(api, const PlanScreen()));
    await tester.pumpAndSettle();

    await tester.enterText(find.byKey(const ValueKey('redeem-field')), 'eci-2026');
    await tester.tap(find.text('Canjear'));
    await tester.pumpAndSettle();

    expect(api.codigosCanjeados, ['eci-2026']);
    expect(tester.widget<Text>(find.byKey(const ValueKey('plan-actual'))).data, 'Institucional');
    expect(find.text('Convenio: ECI'), findsOneWidget);
  });

  for (final codigo in [402, 503]) {
    testWidgets('con $codigo el registro por texto abre el formulario manual con el monto', (tester) async {
      final api = FakeApi()..parseoFallaCon = codigo;
      await tester.pumpWidget(await pantallaDePrueba(api, const QuickAddScreen(initialText: 'almuerzo 12.500')));
      await tester.pumpAndSettle();
      await tester.tap(find.text('Continuar'));
      await tester.pumpAndSettle();

      expect(find.text('Nuevo gasto'), findsOneWidget);
      expect(find.text('12500'), findsOneWidget);
      expect(find.text('almuerzo 12.500'), findsOneWidget);
    });
  }

  test('montoDelTexto toma el primer monto con separadores de miles', () {
    expect(montoDelTexto(r'Bancolombia: compra por $45.900 en EXITO 10:32'), 45900);
    expect(montoDelTexto('pagué 1,200,000 de arriendo'), 1200000);
    expect(montoDelTexto('almuerzo 12500'), 12500);
    expect(montoDelTexto('sin monto'), isNull);
  });
}
