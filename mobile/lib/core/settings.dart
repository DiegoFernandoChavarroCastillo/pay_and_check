import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:shared_preferences/shared_preferences.dart';

import '../data/session.dart';

/// Preferencias que viven solo en el teléfono (el tono del coach y el idioma
/// viven en el backend, con la cuenta). La apariencia es del teléfono; el
/// recordatorio es de cada cuenta, para que no lo herede quien entre después.
class AppSettings {
  const AppSettings({
    this.themeMode = ThemeMode.system,
    this.reminderEnabled = false,
    this.reminderTime = const TimeOfDay(hour: 20, minute: 0),
  });

  final ThemeMode themeMode;
  final bool reminderEnabled;
  final TimeOfDay reminderTime;

  AppSettings copyWith({ThemeMode? themeMode, bool? reminderEnabled, TimeOfDay? reminderTime}) => AppSettings(
        themeMode: themeMode ?? this.themeMode,
        reminderEnabled: reminderEnabled ?? this.reminderEnabled,
        reminderTime: reminderTime ?? this.reminderTime,
      );
}

/// Se sobreescribe en `main()` con la instancia ya cargada.
final sharedPreferencesProvider = Provider<SharedPreferences>((ref) => throw UnimplementedError());

final settingsProvider = NotifierProvider<SettingsController, AppSettings>(SettingsController.new);

class SettingsController extends Notifier<AppSettings> {
  static const _theme = 'theme_mode';
  static const _reminder = 'reminder_enabled';
  static const _hour = 'reminder_hour';
  static const _minute = 'reminder_minute';

  SharedPreferences get _prefs => ref.read(sharedPreferencesProvider);

  /// Sufijo de las preferencias que son de la cuenta y no del teléfono.
  String get _cuenta => '_${ref.read(sessionProvider).value?.id ?? 0}';

  @override
  AppSettings build() {
    final prefs = ref.watch(sharedPreferencesProvider);
    ref.watch(sessionProvider.select((s) => s.value?.id));
    return AppSettings(
      themeMode: ThemeMode.values[prefs.getInt(_theme) ?? ThemeMode.system.index],
      reminderEnabled: prefs.getBool('$_reminder$_cuenta') ?? false,
      reminderTime: TimeOfDay(
        hour: prefs.getInt('$_hour$_cuenta') ?? 20,
        minute: prefs.getInt('$_minute$_cuenta') ?? 0,
      ),
    );
  }

  void setThemeMode(ThemeMode mode) {
    _prefs.setInt(_theme, mode.index);
    state = state.copyWith(themeMode: mode);
  }

  void setReminder({required bool enabled, TimeOfDay? time}) {
    final hora = time ?? state.reminderTime;
    _prefs
      ..setBool('$_reminder$_cuenta', enabled)
      ..setInt('$_hour$_cuenta', hora.hour)
      ..setInt('$_minute$_cuenta', hora.minute);
    state = state.copyWith(reminderEnabled: enabled, reminderTime: hora);
  }
}
