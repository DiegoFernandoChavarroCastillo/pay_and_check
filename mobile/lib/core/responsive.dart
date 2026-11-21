import 'package:flutter/material.dart';

import 'theme.dart';

/// Tres tamaños de pantalla. La app se diseñó para el celular; en una tableta o un computador (la versión
/// web) la navegación pasa a un riel lateral y el contenido se reparte en columnas.
enum Ancho {
  /// Celular: menos de 600 px. Es la app de siempre.
  compacto,

  /// Tableta o ventana mediana: riel lateral con íconos.
  medio,

  /// Computador: riel lateral con nombres.
  expandido;

  static Ancho of(BuildContext context) {
    final ancho = MediaQuery.sizeOf(context).width;
    if (ancho < 600) return Ancho.compacto;
    if (ancho < 1200) return Ancho.medio;
    return Ancho.expandido;
  }

  bool get esCompacto => this == Ancho.compacto;
}

/// Anchos máximos del contenido: más allá, las líneas de texto y las tarjetas se vuelven difíciles de leer.
abstract final class AnchoMax {
  /// Listas, chat y formularios.
  static const lectura = 760.0;

  /// Tableros con dos columnas (Inicio, Progreso).
  static const tablero = 1180.0;
}

/// Centra [child] con un ancho máximo. Las pantallas acomodan su diseño leyendo el ancho de `MediaQuery`
/// (`BentoRow` decide si apila), así que se les informa el ancho de la columna y no el de la ventana.
class ContenidoCentrado extends StatelessWidget {
  const ContenidoCentrado({super.key, this.maxWidth = AnchoMax.lectura, required this.child});

  final double maxWidth;
  final Widget child;

  @override
  Widget build(BuildContext context) {
    return LayoutBuilder(
      builder: (context, c) {
        if (c.maxWidth <= maxWidth) return child;
        return Align(
          alignment: Alignment.topCenter,
          child: SizedBox(width: maxWidth, child: AnchoInformado(ancho: maxWidth, child: child)),
        );
      },
    );
  }
}

/// Le dice a [child] que la pantalla mide [ancho]: lo que lee `MediaQuery.sizeOf` para acomodarse.
class AnchoInformado extends StatelessWidget {
  const AnchoInformado({super.key, required this.ancho, required this.child});

  final double ancho;
  final Widget child;

  @override
  Widget build(BuildContext context) {
    final media = MediaQuery.of(context);
    return MediaQuery(data: media.copyWith(size: Size(ancho, media.size.height)), child: child);
  }
}

/// Dos columnas cuando hay espacio (tablero de Inicio, Progreso); una sola, en el orden de siempre, en el
/// celular. Cada columna recibe la mitad del ancho como si fuera su pantalla.
class DosColumnas extends StatelessWidget {
  const DosColumnas({super.key, required this.principal, required this.secundaria, this.minimo = 840});

  final List<Widget> principal;
  final List<Widget> secundaria;

  /// Ancho a partir del cual se parte en dos.
  final double minimo;

  @override
  Widget build(BuildContext context) {
    return LayoutBuilder(
      builder: (context, c) {
        if (c.maxWidth < minimo) {
          return Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [...principal, ...secundaria]);
        }
        final mitad = (c.maxWidth - AppTokens.gap * 2) / 2;
        Widget columna(List<Widget> hijos) => SizedBox(
              width: mitad,
              child: AnchoInformado(
                ancho: mitad,
                child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: hijos),
              ),
            );
        return Row(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [columna(principal), const SizedBox(width: AppTokens.gap * 2), columna(secundaria)],
        );
      },
    );
  }
}

/// Las pantallas que se abren encima (formularios, reportes, ajustes) no se estiran a todo el ancho de un
/// computador: se muestran como una columna centrada sobre el fondo. Se aplica desde el tema
/// (`pageTransitionsTheme`), así ninguna pantalla tiene que acordarse de hacerlo.
class PaginaCentradaTransitionsBuilder extends PageTransitionsBuilder {
  const PaginaCentradaTransitionsBuilder(this.base);

  final PageTransitionsBuilder base;

  @override
  Widget buildTransitions<T>(
    PageRoute<T> route,
    BuildContext context,
    Animation<double> animation,
    Animation<double> secondaryAnimation,
    Widget child,
  ) {
    // Las rutas de go_router (inicio, login, registro) son la base de la app: esas ocupan todo el ancho.
    final esPaginaBase = route.settings is Page;
    return base.buildTransitions(
      route,
      context,
      animation,
      secondaryAnimation,
      esPaginaBase ? child : _PaginaCentrada(child: child),
    );
  }
}

class _PaginaCentrada extends StatelessWidget {
  const _PaginaCentrada({required this.child});

  final Widget child;

  @override
  Widget build(BuildContext context) {
    final media = MediaQuery.of(context);
    const ancho = AnchoMax.lectura;
    if (media.size.width <= ancho + 80) return child;
    final scheme = Theme.of(context).colorScheme;
    return ColoredBox(
      color: scheme.surfaceContainerHighest,
      child: Center(
        child: Container(
          width: ancho,
          clipBehavior: Clip.antiAlias,
          decoration: BoxDecoration(
            color: Theme.of(context).scaffoldBackgroundColor,
            boxShadow: [BoxShadow(color: scheme.shadow.withValues(alpha: 0.10), blurRadius: 24)],
          ),
          child: MediaQuery(data: media.copyWith(size: Size(ancho, media.size.height)), child: child),
        ),
      ),
    );
  }
}
