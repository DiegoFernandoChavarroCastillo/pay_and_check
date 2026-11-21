import 'package:flutter/foundation.dart' show kIsWeb;
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import 'core/settings.dart';
import 'core/theme.dart';
import 'core/widgets.dart';
import 'data/session.dart';
import 'features/auth/auth_screens.dart';
import 'features/auth/privacy_policy.dart';
import 'features/coach/coach_widgets.dart';
import 'features/shell/shell_screen.dart';
import 'l10n/gen/app_localizations.dart';

/// Rutas de primer nivel. La sesión decide a cuál se puede entrar; el resto
/// de pantallas se abren encima con `Navigator.push`.
final routerProvider = Provider<GoRouter>((ref) {
  final router = GoRouter(
    initialLocation: '/',
    routes: [
      GoRoute(path: '/', builder: (_, _) => const ShellScreen()),
      GoRoute(path: '/login', builder: (_, _) => const LoginScreen()),
      GoRoute(path: '/register', builder: (_, _) => const RegisterScreen()),
      GoRoute(path: '/splash', builder: (_, _) => const SplashScreen()),
      GoRoute(path: '/consent', builder: (_, _) => const ConsentScreen()),
    ],
    redirect: (context, state) {
      final session = ref.read(sessionProvider);
      final ruta = state.matchedLocation;
      // Cargando o con error de red al arrancar: el splash informa y reintenta.
      if (session.isLoading || session.hasError) return ruta == '/splash' ? null : '/splash';

      final publica = ruta == '/login' || ruta == '/register';
      final user = session.value;
      if (user == null) return publica ? null : '/login';
      // Con sesión pero sin la política vigente aceptada (Google, o una versión anterior): solo el consentimiento.
      if (!user.politicaVigente) return ruta == '/consent' ? null : '/consent';
      return publica || ruta == '/splash' || ruta == '/consent' ? '/' : null;
    },
  );
  ref.listen(sessionProvider, (_, _) => router.refresh());
  ref.onDispose(router.dispose);
  return router;
});

class PayAndCheckApp extends ConsumerWidget {
  const PayAndCheckApp({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final idioma = ref.watch(sessionProvider.select((s) => s.value?.idioma));
    return MaterialApp.router(
      onGenerateTitle: (context) => context.l.appName,
      scaffoldMessengerKey: messengerKey,
      routerConfig: ref.watch(routerProvider),
      theme: buildTheme(Brightness.light),
      darkTheme: buildTheme(Brightness.dark),
      themeMode: ref.watch(settingsProvider.select((s) => s.themeMode)),
      // Con sesión manda el idioma de la cuenta; sin sesión, el del teléfono.
      locale: idioma == null ? null : Locale(idioma),
      localizationsDelegates: AppLocalizations.localizationsDelegates,
      supportedLocales: AppLocalizations.supportedLocales,
      builder: kIsWeb ? (context, child) => WebFrame(child: child!) : null,
    );
  }
}

/// En la versión web, en una pantalla ancha (computador, tableta acostada) la app se ve como en el teléfono:
/// una columna centrada del ancho de un celular. En un celular no cambia nada.
class WebFrame extends StatelessWidget {
  const WebFrame({super.key, required this.child});

  static const ancho = 460.0;

  final Widget child;

  @override
  Widget build(BuildContext context) {
    final media = MediaQuery.of(context);
    if (media.size.width <= ancho + 40) return child;
    final scheme = Theme.of(context).colorScheme;
    return ColoredBox(
      color: scheme.surfaceContainerHighest,
      child: Center(
        child: Container(
          width: ancho,
          decoration: BoxDecoration(
            boxShadow: [BoxShadow(color: scheme.shadow.withValues(alpha: 0.12), blurRadius: 24)],
          ),
          // Las pantallas leen el ancho de MediaQuery para acomodarse: debe ser el de la columna, no el de la ventana.
          child: MediaQuery(
            data: media.copyWith(size: Size(ancho, media.size.height)),
            child: ClipRect(child: child),
          ),
        ),
      ),
    );
  }
}

class SplashScreen extends ConsumerWidget {
  const SplashScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final session = ref.watch(sessionProvider);
    return Scaffold(
      body: Center(
        child: session.hasError && !session.isLoading
            ? ErrorView(error: session.error!, onRetry: () => ref.invalidate(sessionProvider))
            : const Column(
                mainAxisSize: MainAxisSize.min,
                children: [
                  CoachOrb(size: 104),
                  SizedBox(height: 24),
                  SizedBox.square(dimension: 20, child: CircularProgressIndicator(strokeWidth: 2)),
                ],
              ),
      ),
    );
  }
}
