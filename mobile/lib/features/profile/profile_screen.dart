import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/notifications.dart';
import '../../core/settings.dart';
import '../../core/motion.dart';
import '../../core/widgets.dart';
import '../../data/providers.dart';
import '../../data/session.dart';
import '../../l10n/gen/app_localizations.dart';
import '../budget/budget_screen.dart';
import '../reports/analytics_screen.dart';
import '../reports/report_screens.dart';
import '../sms/sms_inbox_screen.dart';
import '../transactions/manage_screens.dart';

String _themeLabel(AppLocalizations l, ThemeMode mode) => switch (mode) {
      ThemeMode.light => l.themeLight,
      ThemeMode.dark => l.themeDark,
      ThemeMode.system => l.themeSystem,
    };

Future<T?> _choose<T>(BuildContext context, String title, Map<T, String> opciones, T actual) {
  return showDialog<T>(
    context: context,
    builder: (context) => SimpleDialog(
      title: Text(title),
      children: [
        for (final opcion in opciones.entries)
          ListTile(
            title: Text(opcion.value),
            trailing: opcion.key == actual ? const Icon(Icons.check) : null,
            onTap: () => Navigator.pop(context, opcion.key),
          ),
      ],
    ),
  );
}

/// Perfil: estilo del coach, idioma, recordatorio, gestión y privacidad.
class ProfileScreen extends ConsumerWidget {
  const ProfileScreen({super.key});

  void _abrir(BuildContext context, Widget pantalla) =>
      Navigator.push(context, MaterialPageRoute<void>(builder: (_) => pantalla));

  Future<void> _recordatorio(BuildContext context, WidgetRef ref, {required bool activar, TimeOfDay? hora}) async {
    final l = context.l;
    final ajustes = ref.read(settingsProvider.notifier);
    final servicio = ref.read(notificationsProvider);
    final cuando = hora ?? ref.read(settingsProvider).reminderTime;
    try {
      if (!activar) {
        await servicio.cancel();
        ajustes.setReminder(enabled: false);
        return;
      }
      final concedido = await servicio.schedule(cuando, title: l.reminderTitle, body: l.reminderBody);
      ajustes.setReminder(enabled: concedido, time: cuando);
      if (!concedido) showSnack(l.reminderDenied);
    } catch (_) {
      showSnack(l.errorGeneric);
    }
  }

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final l = context.l;
    final theme = Theme.of(context);
    final user = ref.watch(sessionProvider).value;
    final ajustes = ref.watch(settingsProvider);
    final session = ref.read(sessionProvider.notifier);
    final budget = ref.watch(summaryProvider).value?.budget;
    if (user == null) return const SizedBox.shrink();

    Widget titulo(String texto) => _SectionTitle(texto);
    final perfil = ref.watch(gamificationProvider).value;
    final scheme = theme.colorScheme;

    return ListView(
      padding: const EdgeInsets.fromLTRB(16, 16, 16, 24),
      children: _agrupar([
        BentoTile(
          padding: const EdgeInsets.all(20),
          gradient: LinearGradient(
            begin: Alignment.topLeft,
            end: Alignment.bottomRight,
            colors: [scheme.primaryContainer, Color.lerp(scheme.primaryContainer, scheme.tertiaryContainer, 0.7)!],
          ),
          child: Row(
            children: [
              CircleAvatar(
                radius: 30,
                backgroundColor: scheme.primary,
                child: Text(
                  user.nombre.isEmpty ? '?' : user.nombre.characters.first.toUpperCase(),
                  style: theme.textTheme.headlineSmall?.copyWith(color: scheme.onPrimary),
                ),
              ),
              const SizedBox(width: 16),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(user.nombre, style: theme.textTheme.titleLarge?.copyWith(color: scheme.onPrimaryContainer)),
                    // Un correo largo se encoge antes que partirse en dos renglones.
                    FittedBox(
                      fit: BoxFit.scaleDown,
                      alignment: Alignment.centerLeft,
                      child: Text(
                        user.email,
                        style: theme.textTheme.bodyMedium?.copyWith(color: scheme.onPrimaryContainer),
                      ),
                    ),
                    if (perfil != null)
                      Padding(
                        padding: const EdgeInsets.only(top: 4),
                        child: Text(
                          '${l.levelTitle(perfil.nivelNumero, perfil.nivelNombre)} · ${l.pointsTotal(perfil.puntos)}',
                          style: theme.textTheme.labelLarge?.copyWith(color: scheme.onPrimaryContainer),
                        ),
                      ),
                  ],
                ),
              ),
            ],
          ),
        ),
        titulo(l.sectionCoach),
        ListTile(
          leading: const Icon(Icons.record_voice_over_outlined),
          title: Text(l.coachTone),
          subtitle: Text(toneLabel(l, user.coachTone)),
          onTap: () async {
            final tono = await _choose(
              context,
              l.coachTone,
              {for (final t in coachTones) t: toneLabel(l, t)},
              user.coachTone,
            );
            if (tono != null && context.mounted) {
              final ok = await guarded(context, () => session.updateProfile({'coach_tone': tono}));
              // El tono cambia cómo se redactan los consejos: se piden de nuevo.
              if (ok) ref.invalidate(insightsProvider);
            }
          },
        ),
        SwitchListTile(
          secondary: const Icon(Icons.notifications_outlined),
          title: Text(l.reminder),
          subtitle: Text(ajustes.reminderEnabled ? ajustes.reminderTime.format(context) : l.reminderOff),
          value: ajustes.reminderEnabled,
          onChanged: (v) => _recordatorio(context, ref, activar: v),
        ),
        if (ajustes.reminderEnabled)
          ListTile(
            leading: const Icon(Icons.schedule),
            title: Text(l.reminderTime),
            subtitle: Text(ajustes.reminderTime.format(context)),
            onTap: () async {
              final hora = await showTimePicker(context: context, initialTime: ajustes.reminderTime);
              if (hora != null && context.mounted) await _recordatorio(context, ref, activar: true, hora: hora);
            },
          ),
        titulo(l.sectionMoney),
        if (budget != null)
          ListTile(
            leading: const Icon(Icons.account_balance_wallet_outlined),
            title: Text(l.editBudget),
            onTap: () => _abrir(context, BudgetScreen(current: budget)),
          ),
        ListTile(
          leading: const Icon(Icons.category_outlined),
          title: Text(l.categories),
          onTap: () => _abrir(context, const CategoriesScreen()),
        ),
        ListTile(
          leading: const Icon(Icons.autorenew),
          title: Text(l.recurringExpenses),
          onTap: () => _abrir(context, const RecurringScreen()),
        ),
        ListTile(
          leading: const Icon(Icons.sms_outlined),
          title: Text(l.smsTitle),
          subtitle: Text(l.smsSubtitle),
          onTap: () => _abrir(context, const SmsInboxScreen()),
        ),
        titulo(l.sectionReports),
        ListTile(
          leading: const Icon(Icons.donut_small_outlined),
          title: Text(l.analytics),
          onTap: () => _abrir(context, const AnalyticsScreen()),
        ),
        ListTile(
          leading: const Icon(Icons.insights_outlined),
          title: Text(l.weeklyReport),
          onTap: () => _abrir(context, const WeeklyReportScreen()),
        ),
        ListTile(
          leading: const Icon(Icons.auto_stories_outlined),
          title: Text(l.wrappedTitle),
          onTap: () => _abrir(context, const WrappedScreen()),
        ),
        titulo(l.sectionApp),
        ListTile(
          leading: const Icon(Icons.language),
          title: Text(l.language),
          subtitle: Text(user.idioma == 'en' ? 'English' : 'Español'),
          onTap: () async {
            final idioma = await _choose(context, l.language, {'es': 'Español', 'en': 'English'}, user.idioma);
            if (idioma != null && context.mounted) {
              final ok = await guarded(context, () => session.updateProfile({'idioma': idioma}));
              if (ok) {
                ref.invalidate(insightsProvider);
                refreshData(ref);
              }
            }
          },
        ),
        ListTile(
          leading: const Icon(Icons.dark_mode_outlined),
          title: Text(l.theme),
          subtitle: Text(_themeLabel(l, ajustes.themeMode)),
          onTap: () async {
            final modo = await _choose(
              context,
              l.theme,
              {for (final m in ThemeMode.values) m: _themeLabel(l, m)},
              ajustes.themeMode,
            );
            if (modo != null) ref.read(settingsProvider.notifier).setThemeMode(modo);
          },
        ),
        ListTile(
          leading: const Icon(Icons.shield_outlined),
          title: Text(l.privacy),
          onTap: () => _abrir(context, const PrivacyScreen()),
        ),
        ListTile(
          leading: const Icon(Icons.logout),
          title: Text(l.logout),
          onTap: session.logout,
        ),
        ListTile(
          leading: Icon(Icons.delete_forever_outlined, color: theme.colorScheme.error),
          title: Text(l.deleteAccount, style: TextStyle(color: theme.colorScheme.error)),
          onTap: () async {
            if (!await confirm(context, title: l.deleteAccount, body: l.deleteAccountBody, action: l.delete)) return;
            if (context.mounted) await guarded(context, session.deleteAccount);
          },
        ),
      ]),
    );
  }
}

class _SectionTitle extends StatelessWidget {
  const _SectionTitle(this.texto);

  final String texto;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Padding(
      padding: const EdgeInsets.fromLTRB(8, 20, 8, 8),
      child: Text(texto, style: theme.textTheme.titleSmall?.copyWith(color: theme.colorScheme.primary)),
    );
  }
}

/// Junta en una tarjeta los ajustes que siguen a cada título de sección.
List<Widget> _agrupar(List<Widget> items) {
  final salida = <Widget>[];
  var grupo = <Widget>[];
  void cerrar() {
    if (grupo.isEmpty) return;
    salida.add(BentoTile(padding: const EdgeInsets.symmetric(vertical: 4), child: Column(children: grupo)));
    grupo = [];
  }

  var enSeccion = false;
  for (final item in items) {
    if (item is _SectionTitle) {
      cerrar();
      enSeccion = true;
      salida.add(item);
    } else if (enSeccion) {
      grupo.add(item);
    } else {
      salida.add(item);
    }
  }
  cerrar();
  return salida;
}

/// Qué datos usa la app y para qué, en lenguaje claro.
class PrivacyScreen extends StatelessWidget {
  const PrivacyScreen({super.key});

  @override
  Widget build(BuildContext context) {
    final l = context.l;
    final theme = Theme.of(context);
    final puntos = [
      (Icons.receipt_long_outlined, l.privacyExpensesTitle, l.privacyExpensesBody),
      (Icons.photo_camera_outlined, l.privacyReceiptsTitle, l.privacyReceiptsBody),
      (Icons.mic_none, l.privacyVoiceTitle, l.privacyVoiceBody),
      (Icons.sms_outlined, l.privacySmsTitle, l.privacySmsBody),
      (Icons.auto_awesome_outlined, l.privacyAiTitle, l.privacyAiBody),
      (Icons.delete_forever_outlined, l.privacyDeleteTitle, l.privacyDeleteBody),
    ];
    return Scaffold(
      appBar: AppBar(title: Text(l.privacy)),
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          Text(l.privacyIntro, style: theme.textTheme.bodyLarge),
          const SizedBox(height: 16),
          ...staggered([
            for (final (icono, titulo, cuerpo) in puntos)
              SectionCard(
                child: Row(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    IconBadge(icon: icono),
                    const SizedBox(width: 12),
                    Expanded(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text(titulo, style: theme.textTheme.titleSmall),
                          const SizedBox(height: 2),
                          Text(cuerpo, style: theme.textTheme.bodyMedium),
                        ],
                      ),
                    ),
                  ],
                ),
              ),
          ]),
        ],
      ),
    );
  }
}
