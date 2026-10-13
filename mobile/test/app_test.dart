import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:pay_and_check/data/models.dart';
import 'package:pay_and_check/features/coach/coach_widgets.dart';
import 'package:pay_and_check/features/transactions/expense_form_screen.dart';

import 'fakes.dart';

/// Sin sesión manda el idioma del teléfono, que en los tests es inglés por defecto.
void enEspanol(WidgetTester tester) {
  tester.platformDispatcher.localesTestValue = const [Locale('es')];
  addTearDown(tester.platformDispatcher.clearLocalesTestValue);
}

void main() {
  testWidgets('sin sesión muestra el login y entrar lleva al dashboard', (tester) async {
    enEspanol(tester);
    await tester.pumpWidget(await appDePrueba(FakeApi(), conSesion: false));
    await tester.pumpAndSettle();
    expect(find.text('Hola de nuevo'), findsOneWidget);

    await tester.enterText(find.byType(TextFormField).at(0), 'ana@test.com');
    await tester.enterText(find.byType(TextFormField).at(1), 'secret123');
    await tester.tap(find.text('Entrar'));
    await tester.pumpAndSettle();

    expect(find.text('Hola, Ana'), findsOneWidget);
    expect(find.text('Disponible por día'), findsOneWidget);
    expect(find.text(r'$ 14.258'), findsOneWidget);
    expect(find.text(r'$ 442.000 en total · quedan 31 días'), findsOneWidget);
  });

  testWidgets('una contraseña incorrecta muestra el mensaje del backend y no entra', (tester) async {
    enEspanol(tester);
    await tester.pumpWidget(await appDePrueba(FakeApi(), conSesion: false));
    await tester.pumpAndSettle();

    await tester.enterText(find.byType(TextFormField).at(0), 'ana@test.com');
    await tester.enterText(find.byType(TextFormField).at(1), 'otra');
    await tester.tap(find.text('Entrar'));
    await tester.pumpAndSettle();

    expect(find.text('Credenciales inválidas.'), findsOneWidget);
    expect(find.text('Hola de nuevo'), findsOneWidget);
  });

  testWidgets('con sesión guardada entra directo; sin presupuesto invita a crearlo', (tester) async {
    await tester.pumpWidget(await appDePrueba(FakeApi(conPresupuesto: false)));
    await tester.pumpAndSettle();

    expect(find.text('Crear presupuesto'), findsOneWidget);
    expect(find.text('Disponible por día'), findsNothing);
    // Sin presupuesto no hay dónde registrar gastos: no se ofrece el botón.
    expect(find.byType(FloatingActionButton), findsNothing);
  });

  testWidgets('el check-in se registra con un toque', (tester) async {
    final api = FakeApi();
    await tester.pumpWidget(await appDePrueba(api));
    await tester.pumpAndSettle();

    await tester.ensureVisible(find.text('Calma'));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Calma'));
    await tester.pumpAndSettle();

    expect(api.checkinsHechos, ['tranquilo']);
  });

  testWidgets('un gasto propuesto por la IA se confirma y se guarda con su origen', (tester) async {
    final api = FakeApi();
    final draft = ExpenseDraft(
      monto: 5000,
      categoria: 'entretenimiento',
      descripcion: 'helado',
      fecha: DateTime(2026, 3, 10),
      source: 'voz',
      textoOriginal: 'me compré un helado de 5000',
    );
    await tester.pumpWidget(await pantallaDePrueba(api, ExpenseFormScreen(draft: draft)));
    await tester.pumpAndSettle();

    expect(find.text('Confirma el gasto'), findsOneWidget);
    expect(find.text('5000'), findsOneWidget);
    expect(find.text('entretenimiento'), findsOneWidget);

    // La persona corrige el monto antes de guardar.
    await tester.enterText(find.byType(TextFormField).first, '6.500');
    await tester.tap(find.text('Guardar'));
    await tester.pump();

    expect(api.gastosCreados.single, {
      'monto': 6500.0,
      'category_id': 3,
      'descripcion': 'helado',
      'fecha': '2026-03-10',
      'comercio': null,
      'source': 'voz',
      'texto_original': 'me compré un helado de 5000',
    });
  });

  testWidgets('el formulario no guarda un gasto sin monto', (tester) async {
    final api = FakeApi();
    await tester.pumpWidget(await pantallaDePrueba(api, const ExpenseFormScreen()));
    await tester.pumpAndSettle();

    await tester.tap(find.text('Guardar'));
    await tester.pumpAndSettle();

    expect(find.text('Escribe un monto mayor que cero'), findsOneWidget);
    expect(api.gastosCreados, isEmpty);
  });

  testWidgets('la acción de un tap del coach se ejecuta solo al tocarla', (tester) async {
    final api = FakeApi();
    final insight = Insight.fromJson(insightJson);
    await tester.pumpWidget(
      await pantallaDePrueba(api, Scaffold(body: InsightCard(insight: insight))),
    );
    await tester.pumpAndSettle();

    // Explicabilidad: se muestra el dato en que se basa el consejo.
    expect(find.textContaining('Basado en:'), findsOneWidget);
    expect(api.retosCreados, isEmpty);

    await tester.tap(find.text('Aceptar reto: 20% menos en entretenimiento'));
    await tester.pumpAndSettle();

    expect(api.retosCreados.single, {'plantilla': 'reducir_categoria', 'category_id': 3, 'porcentaje': 20});
    expect(find.text('Hecho'), findsWidgets);
  });

  testWidgets('desplazar el inicio no mueve la cabecera de Progreso', (tester) async {
    await tester.pumpWidget(await appDePrueba(FakeApi()));
    await tester.pumpAndSettle();

    await tester.drag(find.byType(ListView).first, const Offset(0, -600));
    await tester.pumpAndSettle();
    await tester.tap(find.byIcon(Icons.emoji_events_outlined));
    await tester.pumpAndSettle();

    // El nivel se ve nada más entrar, sin tener que tirar hacia abajo.
    expect(tester.getTopLeft(find.text('Nivel 1 · Aprendiz')).dy, greaterThan(0));
  });
}
