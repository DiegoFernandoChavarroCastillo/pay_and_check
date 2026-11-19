import 'dart:ui' as ui;

import 'package:flutter/material.dart';
import 'package:flutter/rendering.dart';
import 'package:share_plus/share_plus.dart';

import '../../core/theme.dart';
import '../../core/widgets.dart';

/// Tarjeta vertical (formato historia) para compartir un logro o el resumen del mes. Nunca lleva montos ni
/// gastos: solo logros ("21 días seguidos", "Primera meta cumplida"). Es lo que hace que la app se vea en
/// Instagram sin exponer el dinero de nadie.
Future<void> showShareCard(
  BuildContext context, {
  required String titulo,
  required String destacado,
  List<String> lineas = const [],
}) {
  return showDialog<void>(
    context: context,
    builder: (_) => _ShareDialog(titulo: titulo, destacado: destacado, lineas: lineas),
  );
}

class _ShareDialog extends StatefulWidget {
  const _ShareDialog({required this.titulo, required this.destacado, required this.lineas});

  final String titulo;
  final String destacado;
  final List<String> lineas;

  @override
  State<_ShareDialog> createState() => _ShareDialogState();
}

class _ShareDialogState extends State<_ShareDialog> {
  final _llave = GlobalKey();
  bool _compartiendo = false;

  Future<void> _compartir() async {
    final l = context.l;
    setState(() => _compartiendo = true);
    try {
      final borde = _llave.currentContext!.findRenderObject()! as RenderRepaintBoundary;
      final imagen = await borde.toImage(pixelRatio: 3);
      final bytes = await imagen.toByteData(format: ui.ImageByteFormat.png);
      if (bytes == null) return;
      await SharePlus.instance.share(
        ShareParams(
          files: [XFile.fromData(bytes.buffer.asUint8List(), mimeType: 'image/png', name: 'payandcheck.png')],
          text: l.shareText,
        ),
      );
    } catch (_) {
      showSnack(l.shareError);
    } finally {
      if (mounted) setState(() => _compartiendo = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final l = context.l;
    return Dialog(
      insetPadding: const EdgeInsets.all(24),
      backgroundColor: Colors.transparent,
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          Flexible(
            child: RepaintBoundary(
              key: _llave,
              child: AspectRatio(aspectRatio: 9 / 16, child: _Tarjeta(widget: widget)),
            ),
          ),
          const SizedBox(height: 16),
          Row(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              TextButton(
                onPressed: () => Navigator.pop(context),
                style: TextButton.styleFrom(foregroundColor: Colors.white),
                child: Text(l.close),
              ),
              const SizedBox(width: 12),
              FilledButton.icon(
                onPressed: _compartiendo ? null : _compartir,
                icon: const Icon(Icons.ios_share),
                label: Text(l.share),
              ),
            ],
          ),
        ],
      ),
    );
  }
}

class _Tarjeta extends StatelessWidget {
  const _Tarjeta({required this.widget});

  final _ShareDialog widget;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    const tinta = Colors.white;
    return DecoratedBox(
      decoration: BoxDecoration(
        borderRadius: BorderRadius.circular(AppTokens.radius),
        gradient: const LinearGradient(
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
          colors: [Color(0xFF14524A), Color(0xFF1B4A5A), Color(0xFF4A3B78)],
        ),
      ),
      child: Padding(
        padding: const EdgeInsets.all(28),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text('Pay&Check', style: theme.textTheme.titleMedium?.copyWith(color: const Color(0xFFB9E8D8))),
            const Spacer(),
            const Icon(Icons.military_tech, size: 72, color: Color(0xFFF2C96B)),
            const SizedBox(height: 16),
            Text(widget.titulo, style: theme.textTheme.titleMedium?.copyWith(color: const Color(0xFFB9E8D8))),
            const SizedBox(height: 8),
            Text(
              widget.destacado,
              style: theme.textTheme.headlineMedium?.copyWith(color: tinta, fontWeight: FontWeight.w700),
            ),
            const SizedBox(height: 12),
            for (final linea in widget.lineas)
              Padding(
                padding: const EdgeInsets.only(bottom: 6),
                child: Text('• $linea', style: theme.textTheme.titleSmall?.copyWith(color: tinta)),
              ),
            const Spacer(),
            Text(
              context.l.shareFooter,
              style: theme.textTheme.bodyMedium?.copyWith(color: const Color(0xFFB9E8D8)),
            ),
          ],
        ),
      ),
    );
  }
}
