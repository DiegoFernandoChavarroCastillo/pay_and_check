import 'package:flutter/foundation.dart' show kIsWeb;
import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:google_sign_in/google_sign_in.dart';

import '../../core/config/app_config.dart';
import '../../core/widgets.dart';
import '../coach/coach_widgets.dart';
import '../../data/session.dart';
import '../../l10n/gen/app_localizations.dart';
import 'google_button/google_button.dart';
import 'privacy_policy.dart';

class LoginScreen extends ConsumerStatefulWidget {
  const LoginScreen({super.key});

  @override
  ConsumerState<LoginScreen> createState() => _LoginScreenState();
}

class _LoginScreenState extends ConsumerState<LoginScreen> {
  final _form = GlobalKey<FormState>();
  final _email = TextEditingController();
  final _password = TextEditingController();
  bool _busy = false;
  StreamSubscription<GoogleSignInAuthenticationEvent>? _google;
  bool _googleWebListo = false;

  @override
  void initState() {
    super.initState();
    if (kIsWeb && googleWebClientId.isNotEmpty) _prepararGoogleWeb();
  }

  /// En web el botón es de Google: al elegir la cuenta llega un evento con el id_token.
  Future<void> _prepararGoogleWeb() async {
    try {
      await ref.read(sessionProvider.notifier).prepareGoogleWeb();
    } catch (_) {
      return; // Sin Google (bloqueado por el navegador, sin red): queda el login con correo.
    }
    _google = GoogleSignIn.instance.authenticationEvents.listen((evento) {
      if (evento is! GoogleSignInAuthenticationEventSignIn || !mounted) return;
      final idToken = evento.user.authentication.idToken;
      if (idToken == null) return;
      _run(() => ref.read(sessionProvider.notifier).loginWithGoogleIdToken(idToken));
    }, onError: (_) {});
    if (mounted) setState(() => _googleWebListo = true);
  }

  @override
  void dispose() {
    _google?.cancel();
    _email.dispose();
    _password.dispose();
    super.dispose();
  }

  Future<void> _run(Future<void> Function() accion) async {
    setState(() => _busy = true);
    await guarded(context, accion);
    if (mounted) setState(() => _busy = false);
  }

  void _login() {
    if (!_form.currentState!.validate()) return;
    _run(() => ref.read(sessionProvider.notifier).login(_email.text.trim(), _password.text));
  }

  @override
  Widget build(BuildContext context) {
    final l = context.l;
    return _AuthScaffold(
      title: l.loginTitle,
      subtitle: l.loginSubtitle,
      form: _form,
      children: [
        _EmailField(controller: _email),
        const SizedBox(height: 12),
        _PasswordField(controller: _password, onSubmitted: _login),
        const SizedBox(height: 20),
        SaveButton(saving: _busy, onPressed: _login, label: l.loginAction),
        // En web, Google exige su propio botón (otro flujo y otra credencial): por ahora solo correo.
        if (googleServerClientId.isNotEmpty && !kIsWeb) ...[
          const SizedBox(height: 12),
          OutlinedButton.icon(
            onPressed: _busy ? null : () => _run(() => ref.read(sessionProvider.notifier).loginWithGoogle()),
            style: OutlinedButton.styleFrom(minimumSize: const Size.fromHeight(52)),
            icon: const Icon(Icons.account_circle_outlined),
            label: Text(l.continueWithGoogle),
          ),
        ],
        if (_googleWebListo) ...[
          const SizedBox(height: 12),
          Center(
            child: LayoutBuilder(
              builder: (context, c) => GoogleWebButton(
                oscuro: Theme.of(context).brightness == Brightness.dark,
                ancho: c.maxWidth,
              ),
            ),
          ),
        ],
        const SizedBox(height: 12),
        TextButton(onPressed: () => context.go('/register'), child: Text(l.goToRegister)),
      ],
    );
  }
}

class RegisterScreen extends ConsumerStatefulWidget {
  const RegisterScreen({super.key});

  @override
  ConsumerState<RegisterScreen> createState() => _RegisterScreenState();
}

class _RegisterScreenState extends ConsumerState<RegisterScreen> {
  final _form = GlobalKey<FormState>();
  final _nombre = TextEditingController();
  final _email = TextEditingController();
  final _password = TextEditingController();
  bool _busy = false;
  bool _aceptaPolitica = false;

  @override
  void dispose() {
    _nombre.dispose();
    _email.dispose();
    _password.dispose();
    super.dispose();
  }

  Future<void> _register() async {
    if (!_form.currentState!.validate()) return;
    setState(() => _busy = true);
    await guarded(
      context,
      () => ref.read(sessionProvider.notifier).register(_nombre.text.trim(), _email.text.trim(), _password.text),
    );
    if (mounted) setState(() => _busy = false);
  }

  @override
  Widget build(BuildContext context) {
    final l = context.l;
    // El login lleva aquí con context.go (reemplaza la pila): sin esto, "atrás" cerraba la app.
    return PopScope(
      canPop: false,
      onPopInvokedWithResult: (didPop, _) {
        if (!didPop) context.go('/login');
      },
      child: _registerForm(l),
    );
  }

  Widget _registerForm(AppLocalizations l) {
    return _AuthScaffold(
      title: l.registerTitle,
      subtitle: l.registerSubtitle,
      form: _form,
      children: [
        TextFormField(
          controller: _nombre,
          textCapitalization: TextCapitalization.words,
          decoration: InputDecoration(labelText: l.name),
          validator: (v) => (v ?? '').trim().isEmpty ? l.requiredField : null,
        ),
        const SizedBox(height: 12),
        _EmailField(controller: _email),
        const SizedBox(height: 12),
        _PasswordField(controller: _password, onSubmitted: _register, minLength: 8),
        const SizedBox(height: 12),
        // Sin aceptar la política no hay cuenta: el formulario no valida y el backend respondería 422.
        PolicyCheckbox(value: _aceptaPolitica, onChanged: (v) => setState(() => _aceptaPolitica = v)),
        const SizedBox(height: 20),
        SaveButton(saving: _busy, onPressed: _register, label: l.registerAction),
        const SizedBox(height: 12),
        TextButton(onPressed: () => context.go('/login'), child: Text(l.goToLogin)),
      ],
    );
  }
}

class _AuthScaffold extends StatelessWidget {
  const _AuthScaffold({required this.title, required this.subtitle, required this.form, required this.children});

  final String title;
  final String subtitle;
  final GlobalKey<FormState> form;
  final List<Widget> children;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final scheme = theme.colorScheme;
    return Scaffold(
      body: DecoratedBox(
        // Un degradado suave del verde de la marca hacia el fondo.
        decoration: BoxDecoration(
          gradient: LinearGradient(
            begin: Alignment.topCenter,
            end: Alignment.center,
            colors: [scheme.primaryContainer, theme.scaffoldBackgroundColor],
          ),
        ),
        child: SafeArea(
          child: Center(
            child: SingleChildScrollView(
              padding: const EdgeInsets.all(24),
              child: ConstrainedBox(
                constraints: const BoxConstraints(maxWidth: 420),
                child: Form(
                  key: form,
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.stretch,
                    children: [
                      const Center(child: CoachOrb(size: 104)),
                      const SizedBox(height: 16),
                      Text(title, style: theme.textTheme.headlineMedium, textAlign: TextAlign.center),
                      const SizedBox(height: 8),
                      Text(subtitle, style: theme.textTheme.bodyLarge, textAlign: TextAlign.center),
                      const SizedBox(height: 32),
                      ...children,
                    ],
                  ),
                ),
              ),
            ),
          ),
        ),
      ),
    );
  }
}

class _EmailField extends StatelessWidget {
  const _EmailField({required this.controller});

  final TextEditingController controller;

  @override
  Widget build(BuildContext context) {
    return TextFormField(
      controller: controller,
      keyboardType: TextInputType.emailAddress,
      autofillHints: const [AutofillHints.email],
      decoration: InputDecoration(labelText: context.l.email),
      validator: (v) => RegExp(r'^\S+@\S+\.\S+$').hasMatch((v ?? '').trim()) ? null : context.l.invalidEmail,
    );
  }
}

class _PasswordField extends StatefulWidget {
  const _PasswordField({required this.controller, required this.onSubmitted, this.minLength = 1});

  final TextEditingController controller;
  final VoidCallback onSubmitted;
  final int minLength;

  @override
  State<_PasswordField> createState() => _PasswordFieldState();
}

class _PasswordFieldState extends State<_PasswordField> {
  bool _oculta = true;

  @override
  Widget build(BuildContext context) {
    final l = context.l;
    return TextFormField(
      controller: widget.controller,
      obscureText: _oculta,
      onFieldSubmitted: (_) => widget.onSubmitted(),
      decoration: InputDecoration(
        labelText: l.password,
        suffixIcon: IconButton(
          tooltip: _oculta ? l.showPassword : l.hidePassword,
          icon: Icon(_oculta ? Icons.visibility : Icons.visibility_off),
          onPressed: () => setState(() => _oculta = !_oculta),
        ),
      ),
      validator: (v) {
        final clave = v ?? '';
        if (clave.isEmpty) return l.passwordRequired;
        return clave.length < widget.minLength ? l.passwordTooShort(widget.minLength) : null;
      },
    );
  }
}
