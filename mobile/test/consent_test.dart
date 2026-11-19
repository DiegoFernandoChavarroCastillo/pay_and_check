import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:pay_and_check/features/profile/profile_screen.dart';

import 'fakes.dart';

/// Sin sesión manda el idioma del teléfono, que en los tests es inglés por defecto.
void enEspanol(WidgetTester tester) {
  tester.platformDispatcher.localesTestValue = const [Locale('es')];
  addTearDown(tester.platformDispatcher.clearLocalesTestValue);
}

void main() {
  testWidgets('el registro no se envía sin aceptar la política; con la casilla, entra', (tester) async {
    enEspanol(tester);
    final api = FakeApi();
    await tester.pumpWidget(await appDePrueba(api, conSesion: false));
    await tester.pumpAndSettle();
    await tester.tap(find.text('¿No tienes cuenta? Crea una'));
    await tester.pumpAndSettle();

    await tester.enterText(find.byType(TextFormField).at(0), 'Ana');
    await tester.enterText(find.byType(TextFormField).at(1), 'ana@test.com');
    await tester.enterText(find.byType(TextFormField).at(2), 'secret123');
    await tester.ensureVisible(find.text('Crear cuenta'));
    await tester.tap(find.text('Crear cuenta'));
    await tester.pumpAndSettle();

    expect(find.text('Para crear tu cuenta debes aceptar la política de privacidad.'), findsOneWidget);
    expect(api.registros, isEmpty);

    await tester.ensureVisible(find.byKey(const ValueKey('policy-checkbox')));
    await tester.tap(find.byKey(const ValueKey('policy-checkbox')));
    await tester.pump();
    await tester.ensureVisible(find.text('Crear cuenta'));
    await tester.tap(find.text('Crear cuenta'));
    await tester.pumpAndSettle();

    expect(api.registros.single['email'], 'ana@test.com');
    expect(find.text('Hola, Ana'), findsOneWidget);
  });

  testWidgets('el enlace de la casilla abre la política completa', (tester) async {
    enEspanol(tester);
    await tester.pumpWidget(await appDePrueba(FakeApi(), conSesion: false));
    await tester.pumpAndSettle();
    await tester.tap(find.text('¿No tienes cuenta? Crea una'));
    await tester.pumpAndSettle();

    await tester.tapOnText(find.textRange.ofSubstring('política de privacidad y el tratamiento de mis datos'));
    await tester.pumpAndSettle();

    expect(find.text('Política de privacidad'), findsOneWidget);
    expect(find.text('Quién es responsable'), findsOneWidget);
  });

  testWidgets('una cuenta sin la política vigente solo ve el consentimiento hasta aceptarla', (tester) async {
    final api = FakeApi()..usuario = {...userJson, 'politica_version': null, 'politica_vigente': false};
    await tester.pumpWidget(await appDePrueba(api));
    await tester.pumpAndSettle();

    expect(find.text('Antes de seguir'), findsOneWidget);
    expect(find.text('Hola, Ana'), findsNothing);

    await tester.tap(find.text('Acepto'));
    await tester.pumpAndSettle();

    expect(api.usuario['politica_vigente'], isTrue);
    expect(find.text('Hola, Ana'), findsOneWidget);
  });

  testWidgets('quien no acepta la política sale de la sesión', (tester) async {
    enEspanol(tester);
    final api = FakeApi()..usuario = {...userJson, 'politica_version': '2025-01', 'politica_vigente': false};
    await tester.pumpWidget(await appDePrueba(api));
    await tester.pumpAndSettle();

    expect(find.textContaining('Actualizamos la política de privacidad'), findsOneWidget);
    await tester.tap(find.text('No acepto, cerrar sesión'));
    await tester.pumpAndSettle();

    expect(find.text('Hola de nuevo'), findsOneWidget);
  });

  testWidgets('borrar la cuenta pide escribir BORRAR', (tester) async {
    final api = FakeApi();
    await tester.pumpWidget(await pantallaDePrueba(api, const ProfileScreen()));
    await tester.pumpAndSettle();

    await tester.dragUntilVisible(find.text('Eliminar mi cuenta'), find.byType(ListView).first, const Offset(0, -300));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Eliminar mi cuenta'));
    await tester.pumpAndSettle();
    await tester.tap(find.widgetWithText(FilledButton, 'Eliminar'));
    await tester.pumpAndSettle();

    final borrar = find.widgetWithText(FilledButton, 'Eliminar');
    expect(tester.widget<FilledButton>(borrar).onPressed, isNull);

    await tester.enterText(find.byKey(const ValueKey('delete-confirm-field')), 'borra');
    await tester.pump();
    expect(tester.widget<FilledButton>(borrar).onPressed, isNull);
    expect(api.borrada, isFalse);

    await tester.enterText(find.byKey(const ValueKey('delete-confirm-field')), 'borrar');
    await tester.pump();
    await tester.tap(borrar);
    await tester.pumpAndSettle();

    expect(api.borrada, isTrue);
  });

  testWidgets('el permiso de SMS pasa primero por el consentimiento de la app', (tester) async {
    final api = FakeApi()..usuario = {...userJson, 'sms_consent_at': null};
    api.sms.llega(1, 'Bancolombia', r'Bancolombia: compra por $45.900 en EXITO 10:32');
    await tester.pumpWidget(await appDePrueba(api));
    await tester.pumpAndSettle();

    // Android ya dio el permiso, pero sin el consentimiento de la app no se lee nada.
    expect(find.descendant(of: find.byType(Badge), matching: find.text('1')), findsNothing);
    await tester.tap(find.byTooltip('Notificaciones'));
    await tester.pumpAndSettle();

    await tester.tap(find.text('Permitir lectura de SMS'));
    await tester.pumpAndSettle();
    expect(find.text('Leer los SMS de tu banco'), findsOneWidget);
    await tester.tap(find.text('Ahora no'));
    await tester.pumpAndSettle();
    expect(api.usuario['sms_consent_at'], isNull);
    expect(find.textContaining(r'$45.900'), findsNothing);

    await tester.tap(find.text('Permitir lectura de SMS'));
    await tester.pumpAndSettle();
    await tester.tap(find.byKey(const ValueKey('sms-consent-accept')));
    await tester.pumpAndSettle();

    expect(api.usuario['sms_consent_at'], isNotNull);
    expect(find.textContaining(r'$45.900'), findsOneWidget);
  });
}
