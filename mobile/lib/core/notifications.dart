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
}
