import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/format.dart';
import '../../core/settings.dart';
import '../../core/widgets.dart';
import '../transactions/add_sheet.dart';

class SmsMessage {
  SmsMessage.fromMap(Map<Object?, Object?> m)
      : id = (m['id'] as num).toInt(),
        remitente = m['address'] as String? ?? '',
        cuerpo = m['body'] as String? ?? '',
        fecha = DateTime.fromMillisecondsSinceEpoch((m['date'] as num).toInt());

  final int id;
  final String remitente;
  final String cuerpo;
  final DateTime fecha;
}

/// Un SMS "parece" un movimiento bancario si menciona un monto y una palabra
/// típica de transacción. Es un filtro amplio a propósito: lo que pase de aquí
/// igual lo revisa la persona antes de guardarse.
final _monto = RegExp(r'\$\s?\d|\d{1,3}([.,]\d{3})+|\b(cop|usd)\b', caseSensitive: false);
final _transaccion = RegExp(
  r'compra|pago|pagaste|retiro|transacci|transferencia|d[ée]bito|consumo|purchase|payment|withdrawal|charged',
  caseSensitive: false,
);

bool pareceMovimientoBancario(String cuerpo) => _monto.hasMatch(cuerpo) && _transaccion.hasMatch(cuerpo);

/// Bandeja de SMS bancarios "por confirmar". Solo Android: el canal nativo
/// vive en `MainActivity.kt`.
class SmsInboxScreen extends ConsumerStatefulWidget {
  const SmsInboxScreen({super.key});

  @override
  ConsumerState<SmsInboxScreen> createState() => _SmsInboxScreenState();
}

class _SmsInboxScreenState extends ConsumerState<SmsInboxScreen> {
  static const _channel = MethodChannel('pay_and_check/sms');
  static const _revisados = 'sms_revisados';
  static const _diasAtras = 14;

  bool? _permiso;
  List<SmsMessage> _mensajes = const [];
  Object? _error;

  Set<String> get _ids => (ref.read(sharedPreferencesProvider).getStringList(_revisados) ?? const []).toSet();

  @override
  void initState() {
    super.initState();
    _cargar(pedirPermiso: false);
  }

  Future<void> _cargar({required bool pedirPermiso}) async {
    try {
      var permiso = await _channel.invokeMethod<bool>('hasPermission') ?? false;
      if (!permiso && pedirPermiso) permiso = await _channel.invokeMethod<bool>('requestPermission') ?? false;

      var mensajes = const <SmsMessage>[];
      if (permiso) {
        final desde = DateTime.now().subtract(const Duration(days: _diasAtras)).millisecondsSinceEpoch;
        final crudos = await _channel.invokeListMethod<Map<Object?, Object?>>('readInbox', {'since': desde});
        final revisados = _ids;
        mensajes = (crudos ?? const [])
            .map(SmsMessage.fromMap)
            .where((m) => pareceMovimientoBancario(m.cuerpo) && !revisados.contains('${m.id}'))
            .toList();
      }
      if (mounted) {
        setState(() {
          _permiso = permiso;
          _mensajes = mensajes;
          _error = null;
        });
      }
    } catch (e) {
      if (mounted) setState(() => _error = e);
    }
  }

  void _marcarRevisado(SmsMessage mensaje) {
    ref.read(sharedPreferencesProvider).setStringList(_revisados, [..._ids, '${mensaje.id}']);
    setState(() => _mensajes = _mensajes.where((m) => m.id != mensaje.id).toList());
  }

  Future<void> _registrar(SmsMessage mensaje) async {
    await Navigator.push(
      context,
      MaterialPageRoute<void>(builder: (_) => QuickAddScreen(initialText: mensaje.cuerpo, source: 'sms')),
    );
    if (mounted) _marcarRevisado(mensaje);
  }

  @override
  Widget build(BuildContext context) {
    final l = context.l;
    final Widget cuerpo;
    if (_error != null) {
      cuerpo = Center(child: EmptyView(icon: Icons.sms_failed_outlined, text: l.smsUnavailable));
    } else if (_permiso == null) {
      cuerpo = const Center(child: CircularProgressIndicator());
    } else if (_permiso == false) {
      cuerpo = Center(
        child: EmptyView(
          icon: Icons.sms_outlined,
          text: l.smsExplain,
          action: FilledButton(onPressed: () => _cargar(pedirPermiso: true), child: Text(l.smsAllow)),
        ),
      );
    } else if (_mensajes.isEmpty) {
      cuerpo = Center(child: EmptyView(icon: Icons.mark_email_read_outlined, text: l.smsEmpty));
    } else {
      cuerpo = ListView(
        padding: const EdgeInsets.all(16),
        children: [
          for (final m in _mensajes)
            SectionCard(
              title: '${m.remitente} · ${shortDate(context, m.fecha)}',
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(m.cuerpo),
                  const SizedBox(height: 8),
                  Row(
                    mainAxisAlignment: MainAxisAlignment.end,
                    children: [
                      TextButton(onPressed: () => _marcarRevisado(m), child: Text(l.smsDismiss)),
                      const SizedBox(width: 8),
                      FilledButton.tonal(onPressed: () => _registrar(m), child: Text(l.smsRegister)),
                    ],
                  ),
                ],
              ),
            ),
        ],
      );
    }

    return Scaffold(
      appBar: AppBar(
        title: Text(l.smsTitle),
        actions: [
          IconButton(
            tooltip: l.retry,
            icon: const Icon(Icons.refresh),
            onPressed: () => _cargar(pedirPermiso: false),
          ),
        ],
      ),
      body: cuerpo,
    );
  }
}
