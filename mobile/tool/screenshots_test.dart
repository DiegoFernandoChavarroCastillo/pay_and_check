// Capturas de las pantallas con datos de mentira, para revisar el diseño sin
// teléfono. No es una prueba: no corre con `flutter test` a secas.
//
//   flutter test tool/screenshots_test.dart
//
// Deja los PNG en build/screenshots/ (claro y oscuro). Los emojis salen como
// recuadros porque el entorno de pruebas no trae fuente de emojis.
import 'dart:io';
import 'dart:ui' as ui;

import 'package:flutter/material.dart';
import 'package:flutter/rendering.dart';
import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:pay_and_check/core/motion.dart';

import 'package:pay_and_check/data/models.dart';
import 'package:pay_and_check/features/auth/auth_screens.dart';
import 'package:pay_and_check/features/budget/budget_screen.dart';
import 'package:pay_and_check/features/reports/analytics_screen.dart';
import 'package:pay_and_check/features/reports/report_screens.dart';
import 'package:pay_and_check/features/sms/sms_inbox_screen.dart';
import 'package:pay_and_check/features/transactions/add_sheet.dart';
import 'package:pay_and_check/features/transactions/expense_form_screen.dart';
import 'package:pay_and_check/features/transactions/manage_screens.dart';

import '../test/fakes.dart';

final _marco = GlobalKey();
final _salida = Directory('build/screenshots');

Future<void> _fuente(String familia, String ruta) async {
  final bytes = await File(ruta).readAsBytes();
  await (FontLoader(familia)..addFont(Future.value(ByteData.sublistView(bytes)))).load();
}

Future<void> _capturar(WidgetTester tester, String nombre) async {
  await tester.pumpAndSettle();
  final borde = _marco.currentContext!.findRenderObject()! as RenderRepaintBoundary;
  await tester.runAsync(() async {
    final imagen = await borde.toImage(pixelRatio: 1.5);
    final png = await imagen.toByteData(format: ui.ImageByteFormat.png);
    await File('${_salida.path}/$nombre.png').writeAsBytes(png!.buffer.asUint8List());
  });
}

String _dia(int atras) => DateTime.now().subtract(Duration(days: atras)).toIso8601String().substring(0, 10);

/// Backend de mentira con más datos que el de las pruebas, para ver las listas llenas.
class _ApiLlena extends FakeApi {
  @override
  Future<List<Expense>> expenses({int? categoryId}) async => [
        for (final (i, (dias, cat, monto, texto, origen, comercio)) in [
          (0, 1, 18500, 'Almuerzo con el equipo', 'voz', 'Crepes'),
          (0, 3, 24000, 'Cine con una amiga', 'texto', null),
          (1, 1, 7200, 'Café y pan', 'ocr', 'Tostao'),
          (1, 3, 15900, 'Suscripción de música', 'recurrente', null),
          (3, 1, 62300, 'Mercado de la semana', 'sms', 'Éxito'),
        ].indexed)
          Expense.fromJson({
            'id': i + 1,
            'category_id': cat,
            'monto': '$monto',
            'descripcion': texto,
            'source': origen,
            'comercio': comercio,
            'fecha': _dia(dias),
          }),
      ];

  @override
  Future<List<PendingPayment>> pendingPayments() async => [
        PendingPayment.fromJson({
          'recurring_id': 1, 'category_id': 1, 'descripcion': 'Recibo de la luz', 'monto': '85000', 'fecha': _dia(0),
        }),
        PendingPayment.fromJson({
          'recurring_id': 2, 'category_id': 1, 'descripcion': 'Arriendo', 'monto': '850000', 'fecha': _dia(2),
        }),
      ];

  @override
  Future<List<RecurringExpense>> recurring() async => [
        RecurringExpense.fromJson({
          'id': 1, 'category_id': 1, 'monto': '85000', 'descripcion': 'Recibo de la luz', 'frecuencia': 'mensual',
          'dia_semana': 0, 'dia_mes': 12, 'activo': true, 'proximo_vencimiento': _dia(0), 'pendiente_desde': _dia(0),
        }),
        RecurringExpense.fromJson({
          'id': 3, 'category_id': 1, 'monto': '25000', 'descripcion': 'Recarga de transporte', 'frecuencia': 'semanal',
          'dia_semana': 0, 'dia_mes': null, 'activo': true, 'proximo_vencimiento': _dia(-5), 'pendiente_desde': null,
        }),
      ];

  @override
  Future<List<Goal>> goals() async => [
        Goal.fromJson({
          'id': 1,
          'nombre': 'Viaje a la costa',
          'monto_objetivo': '1200000',
          'fecha_limite': null,
          'estado': 'activa',
          'aportado': '816000',
          'progreso': '0.68',
          'aportes': [
            {'id': 1, 'monto': '200000', 'fecha': _dia(4)},
          ],
        }),
      ];

  @override
  Future<List<Challenge>> challenges() async => [
        Challenge.fromJson({
          'id': 1,
          'tipo': 'checkins',
          'descripcion': 'Haz 5 check-ins esta semana',
          'objetivo': '5',
          'valor_actual': '3',
          'fecha_fin': _dia(-3),
          'estado': 'activo',
          'puntos': 30,
        }),
        Challenge.fromJson({
          'id': 2,
          'tipo': 'reducir_categoria',
          'descripcion': 'Gasta 20% menos en entretenimiento',
          'objetivo': '80000',
          'valor_actual': '39900',
          'fecha_fin': _dia(-5),
          'estado': 'activo',
          'puntos': 50,
        }),
      ];

  @override
  Future<GamificationProfile> gamification() async => GamificationProfile.fromJson({
        ...gamificationJson,
        'insignias': [
          ...gamificationJson['insignias']! as List,
          {'codigo': 'racha_7', 'nombre': 'Semana completa', 'descripcion': 'Registra 7 días seguidos.', 'desbloqueada': false},
          {'codigo': 'meta_1', 'nombre': 'Primera meta', 'descripcion': 'Cumple una meta de ahorro.', 'desbloqueada': false},
        ],
      });

  @override
  Future<List<ChatMessage>> chatHistory() async => [
        ChatMessage.local('¿Cómo voy esta semana?'),
        ChatMessage.fromJson({
          'id': 1,
          'rol': 'coach',
          'contenido': 'Vas bien: llevas 60.000 de los 99.800 de tu ritmo semanal. Si mantienes el almuerzo en casa dos días, cierras por debajo.',
        }),
      ];

  @override
  Future<WeeklyReport?> weeklyReport() async => WeeklyReport.fromJson({
        'semana_inicio': _dia(5),
        'semana_fin': _dia(-1),
        'gasto_total_semana': '60000',
        'gasto_por_categoria': [
          {'categoria': 'comida', 'monto': '36000'},
          {'categoria': 'entretenimiento', 'monto': '24000'},
        ],
        'ritmo_esperado_semanal': '99800',
        'diferencia_vs_ritmo': '-39800',
        'recomendaciones': 'Vas por debajo de tu ritmo. Comida es lo que más pesa: dos almuerzos en casa te dejan margen para el fin de semana.',
      });

  @override
  Future<Wrapped> wrapped(int anio, int mes) async => Wrapped.fromJson({
        'anio': anio,
        'mes': mes,
        'gasto_total': '412000',
        'num_gastos': 37,
        'dias_con_registro': 22,
        'categoria_top': {'categoria': 'comida', 'porcentaje': 41},
        'gasto_mayor': {'descripcion': 'Mercado', 'monto': '62300'},
        'variacion_vs_mes_anterior_pct': -8,
        'aportado_a_metas': '200000',
        'puntos_ganados': 140,
        'insignias': ['Primer paso'],
        'animo_frecuente': 'tranquilo',
        'frase_coach': 'Un mes constante: registraste casi todos los días.',
      });
}

void main() {
  setUpAll(() async {
    ambientMotionEnabled = false;
    _salida.createSync(recursive: true);
    final flutter = Platform.environment['FLUTTER_ROOT']!;
    await _fuente('PlusJakartaSans', 'assets/fonts/PlusJakartaSans.ttf');
    await _fuente('MaterialIcons', '$flutter/bin/cache/artifacts/material_fonts/MaterialIcons-Regular.otf');
  });

  // Con la letra del teléfono al máximo nada debe desbordarse: un desborde hace fallar esta captura.
  testWidgets('letra grande', (tester) async {
    tester.view
      ..physicalSize = const Size(1080, 2160)
      ..devicePixelRatio = 3;
    tester.platformDispatcher.textScaleFactorTestValue = 1.6;
    addTearDown(tester.view.reset);
    addTearDown(tester.platformDispatcher.clearTextScaleFactorTestValue);

    await tester.pumpWidget(RepaintBoundary(key: _marco, child: await appDePrueba(_ApiLlena())));
    await _capturar(tester, 'letra_grande_inicio');
    await tester.drag(find.byType(ListView).first, const Offset(0, -900));
    await _capturar(tester, 'letra_grande_inicio_abajo');
    await tester.tap(find.byIcon(Icons.emoji_events_outlined));
    await _capturar(tester, 'letra_grande_progreso');
    await tester.tap(find.byIcon(Icons.receipt_long_outlined));
    await _capturar(tester, 'letra_grande_movimientos');
  });

  for (final brillo in Brightness.values) {
    final modo = brillo.name;

    testWidgets('pestañas ($modo)', (tester) async {
      tester.view
        ..physicalSize = const Size(1080, 2160)
        ..devicePixelRatio = 3;
      tester.platformDispatcher.platformBrightnessTestValue = brillo;
      addTearDown(tester.view.reset);
      addTearDown(tester.platformDispatcher.clearPlatformBrightnessTestValue);

      await tester.pumpWidget(RepaintBoundary(key: _marco, child: await appDePrueba(_ApiLlena())));
      await _capturar(tester, 'inicio_$modo');

      await tester.drag(find.byType(ListView).first, const Offset(0, -520));
      await _capturar(tester, 'inicio_abajo_$modo');
      await tester.drag(find.byType(ListView).first, const Offset(0, -900));
      await _capturar(tester, 'inicio_final_$modo');

      await tester.tap(find.byType(FloatingActionButton));
      await _capturar(tester, 'registrar_$modo');
      await tester.tapAt(const Offset(180, 40));
      await tester.pumpAndSettle();

      for (final pestana in ['Movimientos', 'Coach', 'Progreso', 'Perfil']) {
        await tester.tap(find.descendant(of: find.byType(NavigationBar), matching: find.text(pestana)));
        await _capturar(tester, '${pestana.toLowerCase()}_$modo');
        if (pestana == 'Coach') {
          await tester.tap(find.text('Chat'));
          await _capturar(tester, 'chat_$modo');
        }
        if (pestana == 'Progreso') {
          for (final sub in ['Retos', 'Insignias']) {
            await tester.tap(find.text(sub));
            await _capturar(tester, '${sub.toLowerCase()}_$modo');
          }
        }
      }
    });

    testWidgets('pantallas sueltas ($modo)', (tester) async {
      tester.view
        ..physicalSize = const Size(1080, 2160)
        ..devicePixelRatio = 3;
      tester.platformDispatcher.platformBrightnessTestValue = brillo;
      addTearDown(tester.view.reset);
      addTearDown(tester.platformDispatcher.clearPlatformBrightnessTestValue);

      final borrador = ExpenseDraft(
        monto: 5000,
        categoria: 'entretenimiento',
        descripcion: 'helado',
        fecha: DateTime(2026, 3, 10),
        source: 'voz',
        textoOriginal: 'me compré un helado de 5000',
      );
      final pantallas = <String, Widget>{
        'login': const LoginScreen(),
        'gasto': ExpenseFormScreen(draft: borrador),
        'dictar': const QuickAddScreen(initialText: 'me compré un helado de 5000'),
        'analisis': const AnalyticsScreen(),
        'semanal': const WeeklyReportScreen(),
        'mensual': const WrappedScreen(),
        'presupuesto': const BudgetScreen(onboarding: true),
        'categorias': const CategoriesScreen(),
        'fijos': const RecurringScreen(),
        'notificaciones': const NotificationsScreen(),
      };
      for (final MapEntry(key: nombre, value: pantalla) in pantallas.entries) {
        await tester.pumpWidget(
          RepaintBoundary(key: _marco, child: await pantallaDePrueba(_ApiLlena(), KeyedSubtree(key: ValueKey(nombre), child: pantalla))),
        );
        await _capturar(tester, '${nombre}_$modo');
        if (nombre == 'mensual') {
          await tester.drag(find.byType(PageView), const Offset(-300, 0));
          await _capturar(tester, 'mensual2_$modo');
        }
      }
    });
  }
}
