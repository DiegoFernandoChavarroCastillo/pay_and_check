import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:google_mlkit_text_recognition/google_mlkit_text_recognition.dart';
import 'package:image_picker/image_picker.dart';
import 'package:speech_to_text/speech_to_text.dart';

import '../../core/format.dart';
import '../../core/motion.dart';
import '../../core/theme.dart';
import '../../core/widgets.dart';
import '../../data/api.dart';
import '../../data/models.dart';
import '../../data/providers.dart';
import '../coach/coach_widgets.dart';
import 'expense_form_screen.dart';

void _abrir(BuildContext context, Widget pantalla) =>
    Navigator.push(context, MaterialPageRoute<void>(builder: (_) => pantalla));

/// Las formas de registrar un movimiento.
void showAddSheet(BuildContext context) {
  final l = context.l;
  showModalBottomSheet<void>(
    context: context,
    showDragHandle: true,
    isScrollControlled: true,
    builder: (sheet) {
      void elegir(VoidCallback accion) {
        Navigator.pop(sheet);
        accion();
      }

      final scheme = Theme.of(sheet).colorScheme;
      final tokens = sheet.tokens;
      // Mosaico: lo más rápido (decirlo o escribirlo) ocupa la tarjeta grande.
      return SafeArea(
        child: SingleChildScrollView(
          padding: const EdgeInsets.fromLTRB(16, 0, 16, 16),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: staggered([
              _AddTile(
                icon: Icons.mic_none,
                title: l.addByText,
                subtitle: l.addByTextHint,
                color: scheme.primaryContainer,
                foreground: scheme.onPrimaryContainer,
                large: true,
                onTap: () => elegir(() => _abrir(context, const QuickAddScreen())),
              ),
              BentoRow(
                children: [
                  _AddTile(
                    icon: Icons.photo_camera_outlined,
                    title: l.addByReceipt,
                    subtitle: l.addByReceiptHint,
                    color: tokens.coach.container,
                    foreground: tokens.coach.onContainer,
                    onTap: () => elegir(() => _abrir(context, const ReceiptScanScreen(source: ImageSource.camera))),
                  ),
                  _AddTile(
                    icon: Icons.photo_library_outlined,
                    title: l.addByGallery,
                    color: tokens.challenges.container,
                    foreground: tokens.challenges.onContainer,
                    onTap: () => elegir(() => _abrir(context, const ReceiptScanScreen(source: ImageSource.gallery))),
                  ),
                ],
              ),
              BentoRow(
                children: [
                  _AddTile(
                    icon: Icons.edit_outlined,
                    title: l.addManual,
                    onTap: () => elegir(() => _abrir(context, const ExpenseFormScreen())),
                  ),
                  _AddTile(
                    icon: Icons.south_west,
                    title: l.addIncome,
                    subtitle: l.addIncomeHint,
                    color: tokens.income.container,
                    foreground: tokens.income.onContainer,
                    onTap: () => elegir(() => _abrir(context, const IncomeFormScreen())),
                  ),
                ],
              ),
            ].expand((t) => [t, const SizedBox(height: AppTokens.gap)]).toList()..removeLast()),
          ),
        ),
      );
    },
  );
}

/// Una forma de registrar, como tarjeta del mosaico.
class _AddTile extends StatelessWidget {
  const _AddTile({
    required this.icon,
    required this.title,
    required this.onTap,
    this.subtitle,
    this.color,
    this.foreground,
    this.large = false,
  });

  final IconData icon;
  final String title;
  final String? subtitle;
  final Color? color;
  final Color? foreground;
  final bool large;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final tinta = foreground ?? theme.colorScheme.onSurface;
    final icono = Icon(icon, size: large ? 32 : 26, color: tinta);
    final textos = Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(title, style: (large ? theme.textTheme.titleLarge : theme.textTheme.titleSmall)?.copyWith(color: tinta)),
        if (subtitle != null)
          Padding(
            padding: const EdgeInsets.only(top: 2),
            child: Text(
              subtitle!,
              style: theme.textTheme.bodySmall?.copyWith(color: tinta.withValues(alpha: 0.8)),
            ),
          ),
      ],
    );
    return BentoTile(
      color: color,
      onTap: onTap,
      padding: EdgeInsets.all(large ? 20 : 16),
      child: large
          ? Row(children: [icono, const SizedBox(width: 16), Expanded(child: textos)])
          : Column(crossAxisAlignment: CrossAxisAlignment.start, children: [icono, const SizedBox(height: 12), textos]),
    );
  }
}

/// Registro por frase libre, escrita o dictada: "me compré un helado de 5000".
class QuickAddScreen extends ConsumerStatefulWidget {
  const QuickAddScreen({super.key, this.initialText, this.source});

  /// Texto precargado (ej. un SMS del banco) y el origen con que se guardará.
  final String? initialText;
  final String? source;

  @override
  ConsumerState<QuickAddScreen> createState() => _QuickAddScreenState();
}

class _QuickAddScreenState extends ConsumerState<QuickAddScreen> {
  late final _texto = TextEditingController(text: widget.initialText ?? '');
  final _speech = SpeechToText();
  bool _escuchando = false;
  bool _dictado = false;
  bool _busy = false;

  @override
  void dispose() {
    _speech.stop();
    _texto.dispose();
    super.dispose();
  }

  Future<void> _dictar() async {
    final l = context.l;
    if (_escuchando) {
      await _speech.stop();
      setState(() => _escuchando = false);
      return;
    }

    final disponible = await _speech.initialize(
      onStatus: (estado) {
        if (mounted && estado != 'listening') setState(() => _escuchando = false);
      },
      onError: (_) {
        if (mounted) setState(() => _escuchando = false);
      },
    );
    if (!disponible) {
      showSnack(l.voiceUnavailable);
      return;
    }

    setState(() => _escuchando = true);
    await _speech.listen(
      listenOptions: SpeechListenOptions(localeId: l.localeName == 'en' ? 'en_US' : 'es_CO'),
      onResult: (resultado) {
        if (!mounted) return;
        setState(() {
          _texto.text = resultado.recognizedWords;
          _dictado = true;
        });
      },
    );
  }

  Future<void> _analizar() async {
    final texto = _texto.text.trim();
    if (texto.isEmpty) return;
    await _speech.stop();
    if (!mounted) return;
    setState(() {
      _busy = true;
      _escuchando = false;
    });

    ExpenseDraft? draft;
    final source = widget.source ?? (_dictado ? 'voz' : 'texto');
    await guarded(context, () async => draft = await ref.read(apiProvider).parseText(texto, source: source));
    if (!mounted) return;
    setState(() => _busy = false);
    final borrador = draft;
    if (borrador != null) {
      Navigator.pushReplacement(
        context,
        MaterialPageRoute<void>(
          // "Me pagaron…" no es un gasto: se confirma en el formulario de ingresos.
          builder: (_) =>
              borrador.esIngreso ? IncomeFormScreen(draft: borrador) : ExpenseFormScreen(draft: borrador),
        ),
      );
    }
  }

  @override
  Widget build(BuildContext context) {
    final l = context.l;
    final scheme = Theme.of(context).colorScheme;
    return Scaffold(
      appBar: AppBar(title: Text(l.addByText)),
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          TextField(
            controller: _texto,
            autofocus: widget.initialText == null,
            minLines: 3,
            maxLines: 6,
            textCapitalization: TextCapitalization.sentences,
            onChanged: (_) => _dictado = false,
            decoration: InputDecoration(hintText: l.quickAddExample),
          ),
          const SizedBox(height: 16),
          Center(
            child: Column(
              children: [
                // Mientras escucha, el micrófono emite ondas.
                _Ripple(
                  active: _escuchando,
                  color: scheme.tertiary,
                  child: IconButton.filled(
                    iconSize: 36,
                    padding: const EdgeInsets.all(20),
                    style: IconButton.styleFrom(backgroundColor: _escuchando ? scheme.tertiary : scheme.primary),
                    tooltip: _escuchando ? l.voiceStop : l.voiceStart,
                    onPressed: _busy ? null : _dictar,
                    icon: Icon(_escuchando ? Icons.stop : Icons.mic),
                  ),
                ),
                const SizedBox(height: 8),
                Text(_escuchando ? l.voiceListening : l.voiceStart),
              ],
            ),
          ),
          const SizedBox(height: 24),
          // Mientras la IA interpreta, se asoma la forma del gasto que va a proponer.
          AnimatedSize(
            duration: motion(context),
            curve: kMotionCurve,
            alignment: Alignment.topCenter,
            child: _busy
                ? const Padding(
                    padding: EdgeInsets.only(bottom: 24),
                    child: Shimmer(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          SkeletonBox(height: 28, width: 140),
                          SizedBox(height: 10),
                          SkeletonBox(height: 16),
                          SizedBox(height: 8),
                          SkeletonBox(height: 16, width: 200),
                        ],
                      ),
                    ),
                  )
                : const SizedBox(width: double.infinity),
          ),
          SaveButton(saving: _busy, onPressed: _analizar, label: l.analyze),
        ],
      ),
    );
  }
}

/// Ondas que salen de un botón mientras está activo (el micrófono escuchando).
class _Ripple extends StatefulWidget {
  const _Ripple({required this.active, required this.color, required this.child});

  final bool active;
  final Color color;
  final Widget child;

  @override
  State<_Ripple> createState() => _RippleState();
}

class _RippleState extends State<_Ripple> with SingleTickerProviderStateMixin {
  late final _c = AnimationController(vsync: this, duration: const Duration(milliseconds: 1600));

  void _sincronizar() {
    if (widget.active && ambient(context)) {
      if (!_c.isAnimating) _c.repeat();
    } else {
      _c.stop();
      _c.value = 0;
    }
  }

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    _sincronizar();
  }

  @override
  void didUpdateWidget(_Ripple old) {
    super.didUpdateWidget(old);
    _sincronizar();
  }

  @override
  void dispose() {
    _c.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return SizedBox.square(
      dimension: 140,
      child: Stack(
        alignment: Alignment.center,
        children: [
          AnimatedBuilder(
            animation: _c,
            builder: (context, _) => Stack(
              alignment: Alignment.center,
              children: [
                for (final desfase in const [0.0, 0.5])
                  if (widget.active && _c.isAnimating)
                    Builder(
                      builder: (context) {
                        final t = (_c.value + desfase) % 1;
                        return Container(
                          width: 76 + 64 * t,
                          height: 76 + 64 * t,
                          decoration: BoxDecoration(
                            shape: BoxShape.circle,
                            color: widget.color.withValues(alpha: 0.28 * (1 - t)),
                          ),
                        );
                      },
                    ),
              ],
            ),
          ),
          widget.child,
        ],
      ),
    );
  }
}

/// Foto de un recibo → texto reconocido en el teléfono → gasto propuesto.
/// La imagen nunca sale del dispositivo: al backend solo viaja el texto.
class ReceiptScanScreen extends ConsumerStatefulWidget {
  const ReceiptScanScreen({super.key, required this.source});

  final ImageSource source;

  @override
  ConsumerState<ReceiptScanScreen> createState() => _ReceiptScanScreenState();
}

class _ReceiptScanScreenState extends ConsumerState<ReceiptScanScreen> {
  Object? _error;
  String? _aviso;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) => _escanear());
  }

  Future<void> _escanear() async {
    final l = context.l;
    setState(() {
      _error = null;
      _aviso = null;
    });

    try {
      final foto = await ImagePicker().pickImage(source: widget.source, maxWidth: 2000, imageQuality: 90);
      if (foto == null) {
        if (mounted) Navigator.pop(context);
        return;
      }

      final recognizer = TextRecognizer();
      final String texto;
      try {
        texto = (await recognizer.processImage(InputImage.fromFilePath(foto.path))).text.trim();
      } finally {
        await recognizer.close();
      }
      if (texto.isEmpty) {
        if (mounted) setState(() => _aviso = l.receiptUnreadable);
        return;
      }

      final draft = await ref.read(apiProvider).parseReceipt(texto);
      if (!mounted) return;
      Navigator.pushReplacement(
        context,
        MaterialPageRoute<void>(builder: (_) => ExpenseFormScreen(draft: draft)),
      );
    } catch (e) {
      if (mounted) setState(() => _error = e);
    }
  }

  @override
  Widget build(BuildContext context) {
    final l = context.l;
    final Widget cuerpo;
    if (_aviso != null) {
      cuerpo = EmptyView(
        icon: Icons.receipt_long_outlined,
        text: _aviso!,
        action: FilledButton(onPressed: _escanear, child: Text(l.retry)),
      );
    } else if (_error != null) {
      cuerpo = ErrorView(error: _error!, onRetry: _escanear);
    } else {
      cuerpo = Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          const CircularProgressIndicator(),
          const SizedBox(height: 16),
          Text(l.receiptReading),
        ],
      );
    }
    return Scaffold(
      appBar: AppBar(title: Text(l.addByReceipt)),
      body: Center(child: cuerpo),
    );
  }
}

class IncomeFormScreen extends ConsumerStatefulWidget {
  const IncomeFormScreen({super.key, this.draft});

  /// Ingreso propuesto por la IA a partir de un texto; se precarga para confirmar.
  final ExpenseDraft? draft;

  @override
  ConsumerState<IncomeFormScreen> createState() => _IncomeFormScreenState();
}

class _IncomeFormScreenState extends ConsumerState<IncomeFormScreen> {
  final _form = GlobalKey<FormState>();
  late final _monto = TextEditingController(text: widget.draft?.monto?.round().toString() ?? '');
  late final _descripcion = TextEditingController(text: widget.draft?.descripcion ?? '');
  late DateTime _fecha = widget.draft?.fecha ?? today();
  bool _saving = false;

  @override
  void dispose() {
    _monto.dispose();
    _descripcion.dispose();
    super.dispose();
  }

  Future<void> _save() async {
    if (!_form.currentState!.validate()) return;
    setState(() => _saving = true);
    final ok = await guarded(
      context,
      () => ref.read(apiProvider).createIncome(parseMoney(_monto.text)!, _descripcion.text.trim(), _fecha),
    );
    if (!mounted) return;
    setState(() => _saving = false);
    if (ok) {
      refreshData(ref);
      Navigator.pop(context);
    }
  }

  @override
  Widget build(BuildContext context) {
    final l = context.l;
    final esConfirmacion = widget.draft != null;
    return Scaffold(
      appBar: AppBar(title: Text(esConfirmacion ? l.confirmIncome : l.addIncome)),
      body: Form(
        key: _form,
        child: ListView(
          padding: const EdgeInsets.all(16),
          children: [
            if (esConfirmacion)
              SectionCard(
                color: context.tokens.coach.container,
                child: Row(
                  children: [
                    const CoachAvatar(size: 40),
                    const SizedBox(width: 12),
                    Expanded(
                      child: Text(
                        l.confirmIncomeHint,
                        style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                              color: context.tokens.coach.onContainer,
                            ),
                      ),
                    ),
                  ],
                ),
              )
            else ...[
              Text(l.addIncomeHint, style: Theme.of(context).textTheme.bodyMedium),
              const SizedBox(height: 16),
            ],
            MoneyField(controller: _monto, label: l.amount, autofocus: !esConfirmacion, hero: true),
            const SizedBox(height: 12),
            TextFormField(
              controller: _descripcion,
              textCapitalization: TextCapitalization.sentences,
              decoration: InputDecoration(labelText: l.description),
              validator: (v) => (v ?? '').trim().isEmpty ? l.requiredField : null,
            ),
            const SizedBox(height: 12),
            DateField(label: l.date, value: _fecha, onChanged: (d) => setState(() => _fecha = d)),
            const SizedBox(height: 24),
            SaveButton(saving: _saving, onPressed: _save),
          ],
        ),
      ),
    );
  }
}
