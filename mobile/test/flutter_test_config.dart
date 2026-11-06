import 'dart:async';

import 'package:pay_and_check/core/motion.dart';

/// Las animaciones en bucle se apagan en todas las pruebas: con ellas
/// `pumpAndSettle` nunca terminaría.
Future<void> testExecutable(FutureOr<void> Function() testMain) async {
  ambientMotionEnabled = false;
  await testMain();
}
