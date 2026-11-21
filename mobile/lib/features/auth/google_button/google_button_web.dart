import 'package:flutter/widgets.dart';
import 'package:google_sign_in_web/web_only.dart' as web;

/// Lo dibuja Google (un iframe): solo se le pueden elegir tema, forma, texto y ancho.
class GoogleWebButton extends StatelessWidget {
  const GoogleWebButton({super.key, required this.oscuro, required this.ancho});

  final bool oscuro;
  final double ancho;

  @override
  Widget build(BuildContext context) {
    return SizedBox(
      height: 44,
      child: web.renderButton(
        configuration: web.GSIButtonConfiguration(
          type: web.GSIButtonType.standard,
          theme: oscuro ? web.GSIButtonTheme.filledBlack : web.GSIButtonTheme.outline,
          size: web.GSIButtonSize.large,
          text: web.GSIButtonText.continueWith,
          shape: web.GSIButtonShape.pill,
          logoAlignment: web.GSIButtonLogoAlignment.center,
          locale: Localizations.localeOf(context).languageCode,
          // Google limita el ancho a 400 px.
          minimumWidth: ancho.clamp(200, 400),
        ),
      ),
    );
  }
}
