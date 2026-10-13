import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:pay_and_check/core/motion.dart';
import 'package:pay_and_check/core/theme.dart';
import 'package:pay_and_check/core/widgets.dart';
import 'package:pay_and_check/data/models.dart';
import 'package:pay_and_check/features/coach/coach_widgets.dart';
import 'package:pay_and_check/features/progress/progress_screen.dart';
import 'package:pay_and_check/l10n/gen/app_localizations.dart';

/// Un widget suelto con el tema de la app y, si se pide, letra grande o sin animaciones.
Widget _app(Widget hijo, {double escala = 1, bool sinAnimaciones = false, double ancho = 360}) {
  return MaterialApp(
    theme: buildTheme(Brightness.light),
    locale: const Locale('es'),
    localizationsDelegates: AppLocalizations.localizationsDelegates,
    supportedLocales: AppLocalizations.supportedLocales,
    home: MediaQuery(
      data: MediaQueryData(
        size: Size(ancho, 800),
        textScaler: TextScaler.linear(escala),
        disableAnimations: sinAnimaciones,
      ),
      child: Scaffold(body: hijo),
    ),
  );
}

void main() {
  const fila = BentoRow(
    children: [
      BentoTile(key: ValueKey('a'), child: Text('uno')),
      BentoTile(key: ValueKey('b'), child: Text('dos')),
    ],
  );
  Offset pos(WidgetTester tester, String key) => tester.getTopLeft(find.byKey(ValueKey(key)));

  testWidgets('las tarjetas van lado a lado y con la misma altura', (tester) async {
    await tester.pumpWidget(_app(fila));

    expect(pos(tester, 'a').dy, pos(tester, 'b').dy);
    expect(pos(tester, 'b').dx, greaterThan(pos(tester, 'a').dx));
    expect(tester.getSize(find.byKey(const ValueKey('a'))), tester.getSize(find.byKey(const ValueKey('b'))));
  });

  testWidgets('con la letra muy grande las tarjetas se apilan', (tester) async {
    await tester.pumpWidget(_app(fila, escala: 1.6));

    expect(pos(tester, 'a').dx, pos(tester, 'b').dx);
    expect(pos(tester, 'b').dy, greaterThan(pos(tester, 'a').dy));
  });

  testWidgets('en una pantalla angosta las tarjetas se apilan', (tester) async {
    await tester.pumpWidget(_app(fila, ancho: 320));

    expect(pos(tester, 'b').dy, greaterThan(pos(tester, 'a').dy));
  });

  testWidgets('sin animaciones, anillo y contador muestran su valor final de inmediato', (tester) async {
    await tester.pumpWidget(
      _app(
        const Column(
          children: [
            ProgressRing(progress: 0.68),
            AnimatedCount(value: 140),
          ],
        ),
        sinAnimaciones: true,
      ),
    );
    await tester.pump();

    expect(tester.widget<CircularProgressIndicator>(find.byType(CircularProgressIndicator)).value, 0.68);
    expect(find.text('140'), findsOneWidget);
  });

  testWidgets('con animaciones, el contador llega a su valor', (tester) async {
    await tester.pumpWidget(_app(const AnimatedCount(value: 140)));
    expect(find.text('140'), findsNothing);

    await tester.pumpAndSettle();
    expect(find.text('140'), findsOneWidget);
  });

  testWidgets('sin animaciones el coach queda quieto y el confeti no se lanza', (tester) async {
    ambientMotionEnabled = true;
    addTearDown(() => ambientMotionEnabled = false);
    await tester.pumpWidget(
      _app(
        const Stack(
          children: [
            CoachOrb(size: 80),
            Positioned.fill(child: ConfettiBurst(colors: [Colors.teal])),
          ],
        ),
        sinAnimaciones: true,
      ),
    );

    // Nada queda animándose: si el coach respirara, esto no terminaría.
    await tester.pumpAndSettle();
    expect(tester.hasRunningAnimations, isFalse);
    expect(find.byType(CoachOrb), findsOneWidget);
  });

  testWidgets('una insignia pendiente se distingue de una obtenida', (tester) async {
    BadgeInfo insignia(String nombre, bool lista) => BadgeInfo.fromJson({
          'codigo': nombre,
          'nombre': nombre,
          'descripcion': 'Cómo se consigue',
          'desbloqueada': lista,
        });
    await tester.pumpWidget(
      _app(
        ListView(
          children: [
            BadgeTile(insignia: insignia('Primer paso', true)),
            BadgeTile(insignia: insignia('Semana completa', false)),
          ],
        ),
      ),
    );

    expect(find.byIcon(Icons.military_tech), findsOneWidget);
    expect(find.byIcon(Icons.lock_outline), findsOneWidget);
    expect(find.bySemanticsLabel(RegExp('Por desbloquear')), findsOneWidget);
  });
}
