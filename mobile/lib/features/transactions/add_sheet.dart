import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:google_mlkit_text_recognition/google_mlkit_text_recognition.dart';
import 'package:image_picker/image_picker.dart';
import 'package:speech_to_text/speech_to_text.dart';

import '../../core/format.dart';
import '../../core/widgets.dart';
import '../../data/api.dart';
import '../../data/models.dart';
import '../../data/providers.dart';
import 'expense_form_screen.dart';

void _abrir(BuildContext context, Widget pantalla) =>
    Navigator.push(context, MaterialPageRoute<void>(builder: (_) => pantalla));

/// Las formas de registrar un movimiento.
void showAddSheet(BuildContext context) {
  final l = context.l;
  showModalBottomSheet<void>(
    context: context,
    showDragHandle: true,
    builder: (sheet) {
      void elegir(VoidCallback accion) {
        Navigator.pop(sheet);
        accion();
      }

      return SafeArea(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            ListTile(
              leading: const Icon(Icons.mic_none),
              title: Text(l.addByText),
              subtitle: Text(l.addByTextHint),
              onTap: () => elegir(() => _abrir(context, const QuickAddScreen())),
            ),
            ListTile(
              leading: const Icon(Icons.photo_camera_outlined),
              title: Text(l.addByReceipt),
              subtitle: Text(l.addByReceiptHint),
              onTap: () => elegir(() => _abrir(context, const ReceiptScanScreen(source: ImageSource.camera))),
            ),
            ListTile(
              leading: const Icon(Icons.photo_library_outlined),
              title: Text(l.addByGallery),
              onTap: () => elegir(() => _abrir(context, const ReceiptScanScreen(source: ImageSource.gallery))),
            ),
            ListTile(
              leading: const Icon(Icons.edit_outlined),
              title: Text(l.addManual),
              onTap: () => elegir(() => _abrir(context, const ExpenseFormScreen())),
            ),
            ListTile(
              leading: const Icon(Icons.south_west),
              title: Text(l.addIncome),
              subtitle: Text(l.addIncomeHint),
              onTap: () => elegir(() => _abrir(context, const IncomeFormScreen())),
            ),
            const SizedBox(height: 8),
          ],
        ),
      );
    },
  );
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
    if (draft != null) {
      Navigator.pushReplacement(
        context,
        MaterialPageRoute<void>(builder: (_) => ExpenseFormScreen(draft: draft)),
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
                IconButton.filled(
                  iconSize: 36,
                  padding: const EdgeInsets.all(20),
                  style: IconButton.styleFrom(backgroundColor: _escuchando ? scheme.tertiary : scheme.primary),
                  tooltip: _escuchando ? l.voiceStop : l.voiceStart,
                  onPressed: _busy ? null : _dictar,
                  icon: Icon(_escuchando ? Icons.stop : Icons.mic),
                ),
                const SizedBox(height: 8),
                Text(_escuchando ? l.voiceListening : l.voiceStart),
              ],
            ),
          ),
          const SizedBox(height: 24),
          SaveButton(saving: _busy, onPressed: _analizar, label: l.analyze),
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
  const IncomeFormScreen({super.key});

  @override
  ConsumerState<IncomeFormScreen> createState() => _IncomeFormScreenState();
}

class _IncomeFormScreenState extends ConsumerState<IncomeFormScreen> {
  final _form = GlobalKey<FormState>();
  final _monto = TextEditingController();
  final _descripcion = TextEditingController();
  DateTime _fecha = today();
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
    return Scaffold(
      appBar: AppBar(title: Text(l.addIncome)),
      body: Form(
        key: _form,
        child: ListView(
          padding: const EdgeInsets.all(16),
          children: [
            Text(l.addIncomeHint, style: Theme.of(context).textTheme.bodyMedium),
            const SizedBox(height: 16),
            MoneyField(controller: _monto, label: l.amount, autofocus: true),
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
