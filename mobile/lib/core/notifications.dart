import 'package:flutter/material.dart';
import 'package:flutter_local_notifications/flutter_local_notifications.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_timezone/flutter_timezone.dart';
import 'package:timezone/data/latest.dart' as tzdata;
import 'package:timezone/timezone.dart' as tz;

final notificationsProvider = Provider<ReminderService>((ref) => ReminderService());

/// Recordatorio diario del check-in. Es una notificación local programada en
/// el teléfono: no necesita servidor de push.
class ReminderService {
  static const _id = 1;
  final _plugin = FlutterLocalNotificationsPlugin();
  bool _listo = false;

  Future<void> _init() async {
    if (_listo) return;
    tzdata.initializeTimeZones();
    tz.setLocalLocation(tz.getLocation((await FlutterTimezone.getLocalTimezone()).identifier));
    await _plugin.initialize(
      settings: const InitializationSettings(android: AndroidInitializationSettings('@mipmap/ic_launcher')),
    );
    _listo = true;
  }

  /// Programa el recordatorio todos los días a `hora`. Devuelve false si el
  /// usuario no concedió el permiso de notificaciones.
  Future<bool> schedule(TimeOfDay hora, {required String title, required String body}) async {
    await _init();
    final android = _plugin.resolvePlatformSpecificImplementation<AndroidFlutterLocalNotificationsPlugin>();
    if (await android?.requestNotificationsPermission() == false) return false;

    final ahora = tz.TZDateTime.now(tz.local);
    var cuando = tz.TZDateTime(tz.local, ahora.year, ahora.month, ahora.day, hora.hour, hora.minute);
    if (!cuando.isAfter(ahora)) cuando = cuando.add(const Duration(days: 1));

    await _plugin.zonedSchedule(
      id: _id,
      title: title,
      body: body,
      scheduledDate: cuando,
      notificationDetails: const NotificationDetails(
        android: AndroidNotificationDetails('checkin', 'Check-in'),
      ),
      // Inexacta a propósito: no exige el permiso especial de alarmas exactas.
      androidScheduleMode: AndroidScheduleMode.inexactAllowWhileIdle,
      matchDateTimeComponents: DateTimeComponents.time,
    );
    return true;
  }

  Future<void> cancel() async {
    await _init();
    await _plugin.cancel(id: _id);
  }

  /// Deja programados exactamente estos avisos de gastos fijos (a las 9:00 del día que vencen) y quita
  /// los que ya no correspondan. Con [pedirPermiso] se solicita el permiso de notificaciones si falta;
  /// sin él, no se le pregunta nada a la persona.
  Future<void> syncFixed(List<FixedReminder> avisos, {bool pedirPermiso = false}) async {
    await _init();
    if (pedirPermiso && avisos.isNotEmpty) {
      await _plugin
          .resolvePlatformSpecificImplementation<AndroidFlutterLocalNotificationsPlugin>()
          ?.requestNotificationsPermission();
    }
    for (final pendiente in await _plugin.pendingNotificationRequests()) {
      if (pendiente.id >= _baseFijos) await _plugin.cancel(id: pendiente.id);
    }

    final ahora = tz.TZDateTime.now(tz.local);
    for (final aviso in avisos) {
      final cuando = tz.TZDateTime(tz.local, aviso.fecha.year, aviso.fecha.month, aviso.fecha.day, 9);
      // Si vence hoy y ya pasaron las 9, la app ya lo muestra como pendiente: no hace falta avisar.
      if (!cuando.isAfter(ahora)) continue;
      await _plugin.zonedSchedule(
        id: _baseFijos + aviso.id,
        title: aviso.title,
        body: aviso.body,
        scheduledDate: cuando,
        notificationDetails: const NotificationDetails(
          android: AndroidNotificationDetails('gastos_fijos', 'Gastos fijos'),
        ),
        androidScheduleMode: AndroidScheduleMode.inexactAllowWhileIdle,
      );
    }
  }

  static const _baseFijos = 1000;
}

/// Aviso de un gasto fijo que vence en [fecha]. [id] debe ser único entre los avisos vigentes.
class FixedReminder {
  const FixedReminder({required this.id, required this.fecha, required this.title, required this.body});

  final int id;
  final DateTime fecha;
  final String title;
  final String body;
}
