import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import 'core/settings.dart';
import 'core/theme.dart';
import 'core/widgets.dart';
import 'data/session.dart';
import 'features/auth/auth_screens.dart';
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
    ],
    redirect: (context, state) {
      final session = ref.read(sessionProvider);
      final ruta = state.matchedLocation;
      // Cargando o con error de red al arrancar: el splash informa y reintenta.
      if (session.isLoading || session.hasError) return ruta == '/splash' ? null : '/splash';

      final publica = ruta == '/login' || ruta == '/register';
      if (session.value == null) return publica ? null : '/login';
      return publica || ruta == '/splash' ? '/' : null;
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
            : const CircularProgressIndicator(),
      ),
    );
  }
}
