// Funciones añadidas tras el análisis de competidores (noviembre 2026): vacas, apoyos de la universidad,
// gastos previstos y lo que le deben a la persona.
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:pay_and_check/features/planning/planned_screen.dart';
import 'package:pay_and_check/features/transactions/expense_form_screen.dart';

import 'fakes.dart';

void main() {
  testWidgets('una vaca registra solo la parte propia y deja el resto por cobrar', (tester) async {
    final api = FakeApi();
    await tester.pumpWidget(await pantallaDePrueba(api, const ExpenseFormScreen()));
    await tester.pumpAndSettle();

    await tester.enterText(find.byType(TextFormField).first, '90000');
    await tester.enterText(find.widgetWithText(TextFormField, 'Descripción'), 'Pizza');
    await tester.ensureVisible(find.text('Lo pagué por varias personas'));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Lo pagué por varias personas'));
    await tester.pumpAndSettle();
    await tester.enterText(find.widgetWithText(TextFormField, '¿Con quiénes?'), 'Juan, Laura');
    await tester.ensureVisible(find.text('Guardar'));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Guardar'));
    await tester.pumpAndSettle();

    expect(api.gastosCreados, isEmpty);
    expect(api.vacas.single, {
      'monto_total': 90000.0,
      'category_id': 1,
      'descripcion': 'Pizza',
      'fecha': api.vacas.single['fecha'],
      'personas': ['Juan', 'Laura'],
    });
  });

  testWidgets('Inicio muestra lo que le deben y los apoyos cuando hay motivo', (tester) async {
    final api = FakeApi()
      ..cobros = {
        'total_pendiente': '42000',
        'pendientes': [
          {'id': 1, 'expense_id': 5, 'persona': 'Juan', 'descripcion': 'Pizza', 'monto': '21000',
           'fecha': '2026-03-10', 'pagado': false, 'pagado_en': null},
          {'id': 2, 'expense_id': 5, 'persona': 'Laura', 'descripcion': 'Pizza', 'monto': '21000',
           'fecha': '2026-03-10', 'pagado': false, 'pagado_en': null},
        ],
      }
      ..apoyos = {
        'organizacion': 'ECI',
        'motivo_sugerencia': 'estres',
        'apoyos': [
          {'id': 3, 'tipo': 'bienestar', 'titulo': 'Psicología', 'descripcion': 'Citas', 'contacto': 'Bienestar',
           'me_interesa': false},
        ],
      };
    await tester.pumpWidget(await appDePrueba(api));
    await tester.pumpAndSettle();

    expect(find.textContaining(r'Te deben $ 42.000 de 2 vacas'), findsOneWidget);
    expect(find.text('Ver apoyos de ECI'), findsOneWidget);

    await tester.ensureVisible(find.text('Ver apoyos de ECI'));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Ver apoyos de ECI'));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Me interesa'));
    await tester.pumpAndSettle();
    expect(api.interesados, [3]);
  });

  testWidgets('sin motivo no se sugieren los apoyos', (tester) async {
    final api = FakeApi()
      ..apoyos = {
        'organizacion': 'ECI',
        'motivo_sugerencia': null,
        'apoyos': [
          {'id': 3, 'tipo': 'beca', 'titulo': 'Beca', 'descripcion': 'x', 'contacto': 'y', 'me_interesa': false},
        ],
      };
    await tester.pumpWidget(await appDePrueba(api));
    await tester.pumpAndSettle();
    expect(find.text('Ver apoyos de ECI'), findsNothing);
  });

  testWidgets('un gasto previsto se crea desde una plantilla', (tester) async {
    final api = FakeApi();
    await tester.pumpWidget(await pantallaDePrueba(api, const PlannedScreen()));
    await tester.pumpAndSettle();

    await tester.tap(find.text('Nuevo gasto previsto'));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Matrícula'));
    await tester.pumpAndSettle();
    await tester.enterText(find.widgetWithText(TextFormField, 'Monto'), '850000');
    await tester.tap(find.text('Crear'));
    await tester.pumpAndSettle();

    expect(api.previstosCreados.single, {'descripcion': 'Matrícula', 'monto': 850000.0});
  });
}
