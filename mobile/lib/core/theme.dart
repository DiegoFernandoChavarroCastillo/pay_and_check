import 'package:flutter/material.dart';

/// Verde profundo: transmite calma y dinero sin el rojo/verde de "bien/mal"
/// que la app evita a propósito (principio de cero culpa).
const _seed = Color(0xFF1F6F5C);

const kFont = 'PlusJakartaSans';

/// Color de acento de una zona de la app, con su fondo suave y el texto que
/// va encima de ese fondo.
typedef Accent = ({Color color, Color container, Color onContainer});

Accent _accent(Color semilla, Brightness brillo) {
  final s = ColorScheme.fromSeed(seedColor: semilla, brightness: brillo);
  return (color: s.primary, container: s.primaryContainer, onContainer: s.onPrimaryContainer);
}

/// Lo que el tema de Material no cubre: radios, separaciones y un acento por
/// zona (coach, metas, retos, ingresos). Ningún acento es rojo ni verde "de
/// semáforo". Se lee con `context.tokens`.
@immutable
class AppTokens extends ThemeExtension<AppTokens> {
  const AppTokens({required this.coach, required this.goals, required this.challenges, required this.income});

  factory AppTokens.of(Brightness brillo) => AppTokens(
        coach: _accent(const Color(0xFF8A63D2), brillo),
        goals: _accent(const Color(0xFFE0A23B), brillo),
        challenges: _accent(const Color(0xFFE07A5F), brillo),
        income: _accent(const Color(0xFF3B7DD8), brillo),
      );

  final Accent coach;
  final Accent goals;
  final Accent challenges;
  final Accent income;

  /// Radio de las tarjetas del mosaico.
  static const double radius = 28;

  /// Radio de lo que va dentro de una tarjeta (chips grandes, burbujas).
  static const double radiusInner = 20;

  /// Radio de campos y botones.
  static const double radiusField = 16;

  /// Separación entre tarjetas.
  static const double gap = 12;

  @override
  AppTokens copyWith() => this;

  @override
  AppTokens lerp(AppTokens? other, double t) => t < 0.5 || other == null ? this : other;
}

extension TokensX on BuildContext {
  AppTokens get tokens {
    final tema = Theme.of(this);
    return tema.extension<AppTokens>() ?? AppTokens.of(tema.brightness);
  }
}

/// Estilo de los montos: cifras de ancho fijo, para que no "bailen" al contar.
const kTabular = [FontFeature.tabularFigures()];

ThemeData buildTheme(Brightness brightness) {
  final scheme = ColorScheme.fromSeed(seedColor: _seed, brightness: brightness);
  final claro = brightness == Brightness.light;
  // El fondo queda un tono por debajo de las tarjetas para que el mosaico se lea.
  final fondo = claro ? scheme.surfaceContainerLow : scheme.surface;
  final tarjeta = claro ? scheme.surfaceContainerLowest : scheme.surfaceContainer;

  final base = ThemeData(colorScheme: scheme, fontFamily: kFont);
  final t = base.textTheme;
  final campo = RoundedRectangleBorder(borderRadius: BorderRadius.circular(AppTokens.radiusField));

  return base.copyWith(
    extensions: [AppTokens.of(brightness)],
    scaffoldBackgroundColor: fondo,
    textTheme: t.copyWith(
      displayMedium: t.displayMedium?.copyWith(fontWeight: FontWeight.w800, letterSpacing: -1.5),
      displaySmall: t.displaySmall?.copyWith(fontWeight: FontWeight.w800, letterSpacing: -1),
      headlineMedium: t.headlineMedium?.copyWith(fontWeight: FontWeight.w700, letterSpacing: -0.5),
      headlineSmall: t.headlineSmall?.copyWith(fontWeight: FontWeight.w700, letterSpacing: -0.5),
      titleLarge: t.titleLarge?.copyWith(fontWeight: FontWeight.w700),
      titleMedium: t.titleMedium?.copyWith(fontWeight: FontWeight.w700),
      titleSmall: t.titleSmall?.copyWith(fontWeight: FontWeight.w600),
      labelLarge: t.labelLarge?.copyWith(fontWeight: FontWeight.w600),
    ),
    appBarTheme: AppBarTheme(
      backgroundColor: fondo,
      scrolledUnderElevation: 0,
      centerTitle: false,
      titleTextStyle: t.titleLarge?.copyWith(fontWeight: FontWeight.w700, color: scheme.onSurface),
    ),
    cardTheme: CardThemeData(
      elevation: 0,
      color: tarjeta,
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(AppTokens.radius)),
    ),
    inputDecorationTheme: InputDecorationTheme(
      filled: true,
      fillColor: claro ? scheme.surfaceContainerHigh : scheme.surfaceContainerHighest,
      border: OutlineInputBorder(
        borderRadius: BorderRadius.circular(AppTokens.radiusField),
        borderSide: BorderSide.none,
      ),
    ),
    filledButtonTheme: FilledButtonThemeData(
      // Objetivos táctiles de al menos 48 px (accesibilidad).
      style: FilledButton.styleFrom(shape: campo, minimumSize: const Size(64, 48)),
    ),
    outlinedButtonTheme: OutlinedButtonThemeData(
      style: OutlinedButton.styleFrom(shape: campo, minimumSize: const Size(64, 48)),
    ),
    textButtonTheme: TextButtonThemeData(style: TextButton.styleFrom(shape: campo)),
    floatingActionButtonTheme: FloatingActionButtonThemeData(
      elevation: 2,
      highlightElevation: 2,
      backgroundColor: scheme.primary,
      foregroundColor: scheme.onPrimary,
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(AppTokens.radiusInner)),
      extendedTextStyle: t.labelLarge?.copyWith(fontWeight: FontWeight.w700),
    ),
    navigationBarTheme: NavigationBarThemeData(
      height: 68,
      elevation: 0,
      backgroundColor: claro ? tarjeta : scheme.surfaceContainerHigh,
      indicatorColor: scheme.primaryContainer,
      indicatorShape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(18)),
      labelTextStyle: WidgetStateProperty.resolveWith(
        (estados) => t.labelSmall?.copyWith(
          fontSize: 10.5,
          letterSpacing: -0.2,
          fontWeight: estados.contains(WidgetState.selected) ? FontWeight.w700 : FontWeight.w500,
          color: estados.contains(WidgetState.selected) ? scheme.onSurface : scheme.onSurfaceVariant,
        ),
      ),
    ),
    chipTheme: ChipThemeData(
      shape: const StadiumBorder(),
      side: BorderSide.none,
      backgroundColor: claro ? scheme.surfaceContainerHigh : scheme.surfaceContainerHighest,
      selectedColor: scheme.primaryContainer,
      labelStyle: t.labelLarge?.copyWith(color: scheme.onSurface),
    ),
    bottomSheetTheme: BottomSheetThemeData(
      backgroundColor: fondo,
      showDragHandle: true,
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(AppTokens.radius)),
      ),
    ),
    dialogTheme: DialogThemeData(
      backgroundColor: tarjeta,
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(AppTokens.radius)),
    ),
    listTileTheme: ListTileThemeData(
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(AppTokens.radiusInner)),
    ),
    // Pestañas como píldoras: la elegida se rellena en vez de subrayarse.
    tabBarTheme: TabBarThemeData(
      dividerColor: Colors.transparent,
      indicatorSize: TabBarIndicatorSize.tab,
      indicator: BoxDecoration(color: scheme.primaryContainer, borderRadius: BorderRadius.circular(AppTokens.radiusField)),
      splashBorderRadius: BorderRadius.circular(AppTokens.radiusField),
      labelColor: scheme.onPrimaryContainer,
      unselectedLabelColor: scheme.onSurfaceVariant,
      labelStyle: t.titleSmall?.copyWith(fontWeight: FontWeight.w700),
      unselectedLabelStyle: t.titleSmall?.copyWith(fontWeight: FontWeight.w500),
    ),
    progressIndicatorTheme: ProgressIndicatorThemeData(
      linearTrackColor: scheme.surfaceContainerHighest,
      circularTrackColor: scheme.surfaceContainerHighest,
    ),
    // Las pantallas nuevas entran con un fundido y un desliz corto.
    pageTransitionsTheme: const PageTransitionsTheme(
      builders: {TargetPlatform.android: FadeForwardsPageTransitionsBuilder()},
    ),
    snackBarTheme: SnackBarThemeData(
      behavior: SnackBarBehavior.floating,
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(AppTokens.radiusField)),
    ),
  );
}
