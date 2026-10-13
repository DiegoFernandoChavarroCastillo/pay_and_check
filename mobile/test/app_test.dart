import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:pay_and_check/core/api/api_client.dart';
import 'package:pay_and_check/core/settings.dart';
import 'package:pay_and_check/data/api.dart';
import 'package:pay_and_check/data/models.dart';
import 'package:pay_and_check/data/session.dart';
import 'package:pay_and_check/features/coach/coach_widgets.dart';
import 'package:pay_and_check/features/sms/sms_inbox_screen.dart';
import 'package:pay_and_check/features/transactions/add_sheet.dart';
import 'package:pay_and_check/features/transactions/expense_form_screen.dart';
import 'package:pay_and_check/features/transactions/manage_screens.dart';
import 'package:shared_preferences/shared_preferences.dart';

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

  testWidgets('un texto que habla de dinero recibido se confirma y se guarda como ingreso', (tester) async {
    final api = FakeApi()
      ..parseo = {
        'tipo': 'ingreso',
        'monto': '200000',
        'categoria': null,
        'descripcion': 'pago de mis papás',
        'fecha': '2026-03-10',
      };
    await tester.pumpWidget(
      await pantallaDePrueba(api, const QuickAddScreen(initialText: 'recibí un pago de 200,000 por mis papás')),
    );
    await tester.pumpAndSettle();
    await tester.tap(find.text('Continuar'));
    await tester.pumpAndSettle();

    // No es el formulario de gasto: no pide categoría.
    expect(find.text('Confirma el ingreso'), findsOneWidget);
    expect(find.text('Categoría'), findsNothing);
    expect(find.text('200000'), findsOneWidget);

    await tester.tap(find.text('Guardar'));
    await tester.pumpAndSettle();

    expect(api.ingresosCreados.single, {'monto': 200000.0, 'descripcion': 'pago de mis papás', 'fecha': '2026-03-10'});
    expect(api.gastosCreados, isEmpty);
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

  testWidgets('un SMS del banco aparece en notificaciones y se aprueba sin salir de la lista', (tester) async {
    final api = FakeApi()
      ..parseo = {
        'tipo': 'gasto',
        'monto': '45900',
        'categoria': 'comida',
        'descripcion': 'compra en Éxito',
        'fecha': '2026-03-10',
      };
    api.sms
      ..llega(1, 'Bancolombia', r'Bancolombia: compra por $45.900 en EXITO 10:32')
      ..llega(2, 'Nequi', 'Nequi: Pagaste 12.000 a Juan')
      ..llega(3, 'Claro', 'Tu código de verificación es 482913');
    await tester.pumpWidget(await appDePrueba(api));
    await tester.pumpAndSettle();

    // La campana cuenta solo los que parecen movimientos: el código de verificación no.
    expect(find.descendant(of: find.byType(Badge), matching: find.text('2')), findsOneWidget);
    await tester.tap(find.byTooltip('Notificaciones'));
    await tester.pumpAndSettle();
    expect(find.textContaining('482913'), findsNothing);

    // Descartar quita el mensaje sin registrar nada.
    await tester.tap(find.text('Descartar').last);
    await tester.pumpAndSettle();
    expect(find.textContaining('Pagaste 12.000'), findsNothing);

    // Aprobar muestra lo que entendió la IA; guardar lo registra con su origen.
    await tester.tap(find.text('Aprobar'));
    await tester.pumpAndSettle();
    expect(find.text(r'$ 45.900'), findsOneWidget);
    expect(find.text('comida · compra en Éxito'), findsOneWidget);
    expect(api.gastosCreados, isEmpty);

    await tester.tap(find.text('Guardar'));
    await tester.pumpAndSettle();
    expect(api.gastosCreados.single, {
      'monto': 45900.0,
      'category_id': 1,
      'descripcion': 'compra en Éxito',
      'fecha': '2026-03-10',
      'comercio': null,
      'source': 'sms',
      'texto_original': r'Bancolombia: compra por $45.900 en EXITO 10:32',
    });
    expect(find.textContaining('no hay movimientos por revisar'), findsOneWidget);
  });

  testWidgets('un SMS de dinero recibido se guarda como ingreso', (tester) async {
    final api = FakeApi()
      ..parseo = {
        'tipo': 'ingreso',
        'monto': '200000',
        'categoria': null,
        'descripcion': 'transferencia recibida',
        'fecha': '2026-03-10',
      };
    api.sms.llega(1, 'Bancolombia', r'Bancolombia: recibiste una transferencia por $200.000');
    await tester.pumpWidget(await pantallaDePrueba(api, const NotificationsScreen()));
    await tester.pumpAndSettle();

    await tester.tap(find.text('Aprobar'));
    await tester.pumpAndSettle();
    expect(find.text('Ingreso'), findsOneWidget);
    await tester.tap(find.text('Guardar'));
    await tester.pumpAndSettle();

    expect(api.ingresosCreados.single['monto'], 200000.0);
    expect(api.gastosCreados, isEmpty);
  });

  testWidgets('a una categoría por defecto solo se le puede poner un límite propio', (tester) async {
    final api = FakeApi();
    await tester.pumpWidget(await pantallaDePrueba(api, const CategoriesScreen()));
    await tester.pumpAndSettle();

    await tester.tap(find.text('comida'));
    await tester.pumpAndSettle();
    // Ni el nombre ni el tipo: son comunes a todas las personas.
    expect(find.text('Nombre'), findsNothing);
    await tester.enterText(find.byType(TextFormField), '200000');
    await tester.tap(find.text('Guardar'));
    await tester.pumpAndSettle();

    final (id, cambios) = api.categoriasEditadas.single;
    expect(id, 1);
    expect(cambios, {'limite': 200000.0});
  });

  testWidgets('lo revisado y el recordatorio son de cada cuenta, no del teléfono', (tester) async {
    SharedPreferences.setMockInitialValues({'reminder_enabled_7': true, 'sms_revisados_7': ['1']});
    final prefs = await SharedPreferences.getInstance();
    final api = FakeApi();
    api.sms.llega(1, 'Nequi', 'Nequi: Pagaste 12.000 a Juan');
    final contenedor = ProviderContainer(
      overrides: [
        apiProvider.overrideWithValue(api),
        tokenStorageProvider.overrideWithValue(MemoryTokenStorage((access: 'a', refresh: 'r'))),
        sharedPreferencesProvider.overrideWithValue(prefs),
        deviceTimezoneProvider.overrideWithValue(() async => null),
        smsSourceProvider.overrideWithValue(api.sms),
      ],
    );
    addTearDown(contenedor.dispose);

    // La cuenta de la prueba es la 1: no hereda lo que dejó la cuenta 7 en este teléfono.
    expect((await contenedor.read(sessionProvider.future))!.id, 1);
    expect(contenedor.read(settingsProvider).reminderEnabled, isFalse);
    await contenedor.read(smsInboxProvider.notifier).cargar();
    expect(contenedor.read(smsInboxProvider).mensajes, hasLength(1));
  });
}
