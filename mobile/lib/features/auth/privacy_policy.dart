import 'package:flutter/gestures.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/config/app_config.dart';
import '../../core/widgets.dart';
import '../../data/session.dart';
import '../coach/coach_widgets.dart';

/// Texto de la política de privacidad, versión [politicaVersion]. La copia
/// para publicar está en `docs/privacidad.md`: si cambia una, cambia la otra
/// y se sube la versión (aquí y en el backend).
List<(String, String)> politicaDePrivacidad(String idioma) {
  final contacto = contactoPrivacidad.isEmpty ? null : contactoPrivacidad;
  if (idioma == 'en') {
    return [
      (
        'Who is responsible',
        'Pay&Check is in a pilot phase. The Pay&Check team is responsible for the processing '
            'of your personal data under Colombian Law 1581 of 2012 (habeas data) and Decree 1377 of 2013.',
      ),
      (
        'What data we keep',
        '• Your account: name, email, and an encrypted password or your Google ID; language and time zone.\n'
            '• Your finances in the app: budgets, expenses, income, fixed expenses, savings goals, mood check-ins, '
            'challenges, points and your conversations with the coach.\n'
            '• Your plan and AI usage: how many AI requests you make, tokens and response time. The text you '
            'write is not stored in that record.\n'
            '• The date and version of the privacy policy you accepted, and whether you allowed SMS reading.',
      ),
      (
        'What stays on your phone',
        '• Voice: your phone turns it into text; the app only receives the text.\n'
            '• Receipt photos: the text is recognized on your phone. The photo is never uploaded.\n'
            '• Bank SMS: only if you allow it separately. They are read on your phone and are not stored on our '
            'server.\n'
            '• Notifications from your payment apps (Nequi, Daviplata, your bank): only if you turn on access in '
            'Android settings. The app only looks at a fixed list of financial apps, keeps them on your phone and '
            'nothing leaves it until you choose to log a transaction.',
      ),
      (
        'In the web version',
        'In the browser version there is no reading of SMS, notifications or receipts. Voice is turned into text '
            'by the browser\'s own dictation service, which, depending on the browser, may process it on its '
            'provider\'s servers (Google in Chrome, Apple in Safari). Your session is stored, encrypted, in the '
            'browser until you log out.',
      ),
      (
        'What is sent to the AI service',
        'To understand what you write and draft the coach\'s messages we use Groq, an AI service whose servers '
            'are in the United States (international data transfer). If Groq does not respond, the same request '
            'may go to DeepInfra, also in the United States, with the same model. We send: your first name, the text you '
            'type or dictate to log a transaction, the text of an SMS or receipt you choose to log, your chat '
            'messages (with the last 10 turns) and a summary of your figures (available amount, totals, '
            'categories, expense descriptions and goal names).\n'
            'We never send your email, password, Google ID, location, photos or the SMS or notifications you did not choose. '
            'The AI does not save anything by itself: you confirm every transaction before it is stored.',
      ),
      (
        'What we use it for',
        'To calculate how much you can spend, log your transactions, give you tips, run your challenges and '
            'apply your plan\'s AI quota. We do not sell your data, we do not use it for advertising and we do '
            'not make automated decisions with legal effects about you.',
      ),
      (
        'Where it is stored and for how long',
        'On cloud providers: the API on Amazon Web Services (with Render as a backup), the PostgreSQL database '
            'on Neon and the web version on Vercel, which only serves the app and does not store your data. Your '
            'data is kept while '
            'your account exists. When you delete your account, everything is deleted immediately and for good.',
      ),
      (
        'How we protect it',
        'Encrypted connections (HTTPS), passwords stored only as a hash, session tokens that expire, request '
            'limits, and layers that stop the AI from following instructions hidden in your data.',
      ),
      (
        'Your rights',
        'You can know, update, correct and delete your data and revoke this authorization at any time: edit '
            'your profile, revoke the SMS permission in Android settings, or delete your account from Profile › '
            'Delete account.${contacto == null ? '' : ' You can also write to $contacto.'} If you are not '
            'satisfied with our answer, you can file a complaint with the Superintendencia de Industria y '
            'Comercio (SIC).',
      ),
      (
        'Minors',
        'If you are under 18, you need authorization from your parent or legal guardian to use the app.',
      ),
      (
        'Changes',
        'If this policy changes, the app will show you the new version and ask you to accept it again before '
            'you continue.',
      ),
    ];
  }
  return [
    (
      'Quién es responsable',
      'Pay&Check está en fase piloto. El equipo de Pay&Check es el responsable del '
          'tratamiento de tus datos personales, conforme a la Ley 1581 de 2012 (habeas data) y al Decreto 1377 de '
          '2013.',
    ),
    (
      'Qué datos guardamos',
      '• Tu cuenta: nombre, correo y una contraseña cifrada o tu identificador de Google; idioma y zona horaria.\n'
          '• Tus finanzas en la app: presupuestos, gastos, ingresos, gastos fijos, metas de ahorro, check-ins de '
          'ánimo, retos, puntos y tus conversaciones con el coach.\n'
          '• Tu plan y tu uso de la IA: cuántas solicitudes de IA haces, tokens y tiempo de respuesta. En ese '
          'registro no se guarda lo que escribes.\n'
          '• La fecha y la versión de la política que aceptaste, y si permitiste leer tus SMS.',
    ),
    (
      'Qué se queda en tu teléfono',
      '• La voz: tu teléfono la convierte en texto; la app solo recibe el texto.\n'
          '• Las fotos de recibos: el texto se reconoce en tu teléfono. La foto nunca se sube.\n'
          '• Los SMS del banco: solo si lo permites aparte. Se leen en tu teléfono y no se guardan en nuestro '
          'servidor.\n'
          '• Las notificaciones de tus apps de pago (Nequi, Daviplata, tu banco): solo si activas el acceso en los '
          'ajustes de Android. La app solo mira una lista fija de apps financieras, las guarda en tu teléfono y '
          'nada sale de él hasta que eliges registrar un movimiento.',
    ),
    (
      'En la versión web',
      'En la versión para el navegador no hay lectura de SMS, de notificaciones ni de recibos. La voz se convierte '
          'en texto con el servicio de dictado del propio navegador, que según el navegador puede procesarla en los '
          'servidores de su proveedor (Google en Chrome, Apple en Safari). Tu sesión queda guardada, cifrada, en el '
          'navegador hasta que cierres sesión.',
    ),
    (
      'Qué se envía al servicio de IA',
      'Para entender lo que escribes y redactar los mensajes del coach usamos Groq, un servicio de IA con '
          'servidores en Estados Unidos (transferencia internacional de datos). Si Groq no responde, la misma '
          'solicitud puede ir a DeepInfra, también en Estados Unidos, con el mismo modelo. Enviamos: tu nombre de pila, el '
          'texto que escribes o dictas para registrar un movimiento, el texto del SMS o del recibo que eliges '
          'registrar, tus mensajes del chat (con los últimos 10 turnos) y un resumen de tus cifras (disponible, '
          'totales, categorías, descripciones de gastos y nombres de metas).\n'
          'Nunca enviamos tu correo, tu contraseña, tu identificador de Google, tu ubicación, tus fotos ni los SMS '
          'o notificaciones que no elegiste. La IA no guarda nada por su cuenta: tú confirmas cada movimiento antes de guardarlo.',
    ),
    (
      'Para qué los usamos',
      'Para calcular cuánto puedes gastar, registrar tus movimientos, darte consejos, llevar tus retos y aplicar '
          'el cupo de IA de tu plan. No vendemos tus datos, no los usamos para publicidad y no tomamos decisiones '
          'automáticas con efectos legales sobre ti.',
    ),
    (
      'Dónde se guardan y por cuánto tiempo',
      'En proveedores en la nube: la API en Amazon Web Services (con Render como respaldo), la base de datos '
          'PostgreSQL en Neon y la versión web en Vercel, que solo sirve la app y no guarda tus datos. Tus datos se guardan '
          'mientras tengas cuenta. Al borrar tu cuenta se elimina todo de inmediato y para siempre.',
    ),
    (
      'Cómo los protegemos',
      'Conexiones cifradas (HTTPS), contraseñas guardadas solo como hash, sesiones que expiran, límites de '
          'solicitudes y capas que impiden que la IA obedezca instrucciones escondidas en tus datos.',
    ),
    (
      'Tus derechos',
      'Puedes conocer, actualizar, rectificar y suprimir tus datos y revocar esta autorización cuando quieras: '
          'edita tu perfil, quita el permiso de SMS en los ajustes de Android o borra tu cuenta en Perfil › '
          'Eliminar cuenta.${contacto == null ? '' : ' También puedes escribir a $contacto.'} Si no quedas '
          'conforme con nuestra respuesta, puedes presentar una queja ante la Superintendencia de Industria y '
          'Comercio (SIC).',
    ),
    (
      'Menores de edad',
      'Si eres menor de 18 años, necesitas la autorización de tu padre, madre o representante legal para usar la '
          'app.',
    ),
    (
      'Cambios',
      'Si esta política cambia, la app te mostrará la nueva versión y te pedirá aceptarla de nuevo antes de '
          'seguir.',
    ),
  ];
}

/// Texto completo de la política. Se abre desde el registro, la pantalla de
/// consentimiento y Perfil › Privacidad.
class PrivacyPolicyScreen extends StatelessWidget {
  const PrivacyPolicyScreen({super.key});

  static Future<void> abrir(BuildContext context) =>
      Navigator.push(context, MaterialPageRoute<void>(builder: (_) => const PrivacyPolicyScreen()));

  @override
  Widget build(BuildContext context) {
    final l = context.l;
    return Scaffold(
      appBar: AppBar(title: Text(l.policyTitle)),
      body: SafeArea(child: _TextoPolitica(idioma: Localizations.localeOf(context).languageCode)),
    );
  }
}

class _TextoPolitica extends StatelessWidget {
  const _TextoPolitica({required this.idioma, this.encabezado});

  final String idioma;
  final Widget? encabezado;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return ListView(
      padding: const EdgeInsets.fromLTRB(20, 16, 20, 24),
      children: [
        ?encabezado,
        Text(
          context.l.policyVersion(politicaVersion),
          style: theme.textTheme.labelMedium?.copyWith(color: theme.colorScheme.onSurfaceVariant),
        ),
        for (final (titulo, cuerpo) in politicaDePrivacidad(idioma)) ...[
          const SizedBox(height: 16),
          Text(titulo, style: theme.textTheme.titleMedium),
          const SizedBox(height: 6),
          Text(cuerpo, style: theme.textTheme.bodyMedium),
        ],
      ],
    );
  }
}

/// Casilla obligatoria del registro: "He leído y acepto la política…", con el
/// enlace al texto completo. Valida con el formulario.
class PolicyCheckbox extends StatelessWidget {
  const PolicyCheckbox({super.key, required this.value, required this.onChanged});

  final bool value;
  final ValueChanged<bool> onChanged;

  @override
  Widget build(BuildContext context) {
    final l = context.l;
    final theme = Theme.of(context);
    return FormField<bool>(
      initialValue: value,
      validator: (_) => value ? null : l.policyRequired,
      builder: (campo) => Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Checkbox(
                key: const ValueKey('policy-checkbox'),
                value: value,
                onChanged: (v) {
                  onChanged(v ?? false);
                  campo.didChange(v);
                },
              ),
              Expanded(
                child: Padding(
                  padding: const EdgeInsets.only(top: 12),
                  child: Text.rich(
                    TextSpan(
                      style: theme.textTheme.bodyMedium,
                      children: [
                        TextSpan(text: l.policyAcceptPrefix),
                        TextSpan(
                          text: l.policyAcceptLink,
                          style: TextStyle(
                            color: theme.colorScheme.primary,
                            decoration: TextDecoration.underline,
                            fontWeight: FontWeight.w600,
                          ),
                          recognizer: TapGestureRecognizer()..onTap = () => PrivacyPolicyScreen.abrir(context),
                        ),
                      ],
                    ),
                  ),
                ),
              ),
            ],
          ),
          if (campo.hasError)
            Padding(
              padding: const EdgeInsets.only(left: 12),
              child: Text(
                campo.errorText!,
                style: theme.textTheme.bodySmall?.copyWith(color: theme.colorScheme.error),
              ),
            ),
        ],
      ),
    );
  }
}

/// Pantalla bloqueante para quien tiene sesión pero no ha aceptado la política
/// vigente: cuentas creadas con Google o que aceptaron una versión anterior.
class ConsentScreen extends ConsumerStatefulWidget {
  const ConsentScreen({super.key});

  @override
  ConsumerState<ConsentScreen> createState() => _ConsentScreenState();
}

class _ConsentScreenState extends ConsumerState<ConsentScreen> {
  bool _busy = false;

  Future<void> _run(Future<void> Function() accion) async {
    setState(() => _busy = true);
    await guarded(context, accion);
    if (mounted) setState(() => _busy = false);
  }

  @override
  Widget build(BuildContext context) {
    final l = context.l;
    final theme = Theme.of(context);
    final session = ref.read(sessionProvider.notifier);
    final cambio = ref.watch(sessionProvider.select((s) => s.value?.aceptoPoliticaAntes ?? false));
    return Scaffold(
      body: SafeArea(
        child: Column(
          children: [
            Expanded(
              child: _TextoPolitica(
                idioma: Localizations.localeOf(context).languageCode,
                encabezado: Column(
                  crossAxisAlignment: CrossAxisAlignment.stretch,
                  children: [
                    const Center(child: CoachOrb(size: 72)),
                    const SizedBox(height: 12),
                    Text(l.consentTitle, style: theme.textTheme.headlineSmall, textAlign: TextAlign.center),
                    const SizedBox(height: 8),
                    Text(cambio ? l.consentUpdated : l.consentBody, style: theme.textTheme.bodyLarge),
                    const SizedBox(height: 8),
                    const Divider(),
                  ],
                ),
              ),
            ),
            Padding(
              padding: const EdgeInsets.fromLTRB(20, 8, 20, 16),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  SaveButton(saving: _busy, onPressed: () => _run(session.acceptPolicy), label: l.consentAccept),
                  const SizedBox(height: 8),
                  TextButton(onPressed: _busy ? null : () => _run(session.logout), child: Text(l.consentDecline)),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }
}
