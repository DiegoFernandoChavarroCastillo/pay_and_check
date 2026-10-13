import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/charts.dart';
import '../../core/format.dart';
import '../../core/motion.dart';
import '../../core/theme.dart';
import '../../core/settings.dart';
import '../../core/widgets.dart';
import '../../data/api.dart';
import '../../data/models.dart';
import '../../data/providers.dart';
import '../../data/session.dart';
import '../transactions/add_sheet.dart';
import '../transactions/expense_form_screen.dart';

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

/// De dónde salen los SMS del teléfono. Solo Android: el canal nativo vive en
/// `MainActivity.kt`. En las pruebas se reemplaza por una lista fija.
class SmsSource {
  const SmsSource();

  static const _channel = MethodChannel('pay_and_check/sms');

  Future<bool> hasPermission() async => await _channel.invokeMethod<bool>('hasPermission') ?? false;

  Future<bool> requestPermission() async => await _channel.invokeMethod<bool>('requestPermission') ?? false;

  Future<List<SmsMessage>> read(DateTime desde) async {
    final crudos = await _channel.invokeListMethod<Map<Object?, Object?>>(
      'readInbox',
      {'since': desde.millisecondsSinceEpoch},
    );
    return (crudos ?? const []).map(SmsMessage.fromMap).toList();
  }
}

final smsSourceProvider = Provider<SmsSource>((ref) => const SmsSource());

/// Movimientos bancarios detectados en los SMS y todavía sin revisar.
class SmsInboxState {
  const SmsInboxState({this.permiso, this.mensajes = const [], this.error});

  /// null mientras no se sabe; false si la persona no ha dado el permiso.
  final bool? permiso;
  final List<SmsMessage> mensajes;
  final Object? error;
}

class SmsInbox extends Notifier<SmsInboxState> {
  /// Los revisados son de cada cuenta: descartar un SMS en una no lo oculta en otra.
  String get _revisados => 'sms_revisados_${ref.read(sessionProvider).value?.id ?? 0}';
  static const _diasAtras = 14;

  @override
  SmsInboxState build() {
    // Al cambiar de cuenta la bandeja se arma de nuevo con lo que esa cuenta ya revisó.
    ref.watch(sessionProvider.select((s) => s.value?.id));
    // Nunca pide el permiso por su cuenta: solo mira si ya lo tiene.
    unawaited(Future.microtask(cargar));
    return const SmsInboxState();
  }

  Set<String> get _ids => (ref.read(sharedPreferencesProvider).getStringList(_revisados) ?? const []).toSet();

  Future<void> cargar({bool pedirPermiso = false}) async {
    final fuente = ref.read(smsSourceProvider);
    try {
      var permiso = await fuente.hasPermission();
      if (!permiso && pedirPermiso) permiso = await fuente.requestPermission();

      var mensajes = const <SmsMessage>[];
      if (permiso) {
        final revisados = _ids;
        mensajes = (await fuente.read(DateTime.now().subtract(const Duration(days: _diasAtras))))
            .where((m) => pareceMovimientoBancario(m.cuerpo) && !revisados.contains('${m.id}'))
            .toList();
      }
      if (ref.mounted) state = SmsInboxState(permiso: permiso, mensajes: mensajes);
    } catch (e) {
      // Sin canal nativo (otra plataforma) no hay bandeja; no es un error que mostrar en el inicio.
      if (ref.mounted) state = SmsInboxState(error: e);
    }
  }

  /// Saca el mensaje de los pendientes, se haya registrado o descartado.
  void marcarRevisado(SmsMessage mensaje) {
    ref.read(sharedPreferencesProvider).setStringList(_revisados, [..._ids, '${mensaje.id}']);
    state = SmsInboxState(
      permiso: state.permiso,
      mensajes: state.mensajes.where((m) => m.id != mensaje.id).toList(),
    );
  }
}

final smsInboxProvider = NotifierProvider<SmsInbox, SmsInboxState>(SmsInbox.new);

/// Campana del inicio: cuántos movimientos detectados esperan revisión.
class NotificationsBell extends ConsumerWidget {
  const NotificationsBell({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final pendientes = ref.watch(smsInboxProvider.select((s) => s.mensajes.length));
    return IconButton(
      tooltip: context.l.notifications,
      onPressed: () => Navigator.push(
        context,
        MaterialPageRoute<void>(builder: (_) => const NotificationsScreen()),
      ),
      icon: Badge(
        isLabelVisible: pendientes > 0,
        // Con el color de la marca: un aviso rojo se leería como alarma.
        backgroundColor: Theme.of(context).colorScheme.primary,
        textColor: Theme.of(context).colorScheme.onPrimary,
        label: Text('$pendientes'),
        child: Icon(pendientes > 0 ? Icons.notifications : Icons.notifications_outlined),
      ),
    );
  }
}

/// Notificaciones: los movimientos que la app detectó en los SMS del banco,
/// para aprobarlos o descartarlos sin salir de la lista.
class NotificationsScreen extends ConsumerWidget {
  const NotificationsScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final l = context.l;
    final bandeja = ref.watch(smsInboxProvider);
    final control = ref.read(smsInboxProvider.notifier);

    final Widget cuerpo;
    if (bandeja.error != null) {
      cuerpo = Center(child: EmptyView(icon: Icons.sms_failed_outlined, text: l.smsUnavailable));
    } else if (bandeja.permiso == null) {
      cuerpo = const Center(child: CircularProgressIndicator());
    } else if (bandeja.permiso == false) {
      cuerpo = Center(
        child: EmptyView(
          icon: Icons.sms_outlined,
          text: l.smsExplain,
          action: FilledButton(onPressed: () => control.cargar(pedirPermiso: true), child: Text(l.smsAllow)),
        ),
      );
    } else if (bandeja.mensajes.isEmpty) {
      cuerpo = Center(child: EmptyView(icon: Icons.mark_email_read_outlined, text: l.smsEmpty));
    } else {
      cuerpo = ListView(
        padding: const EdgeInsets.all(16),
        children: [
          Padding(
            padding: const EdgeInsets.only(left: 4, bottom: 12),
            child: Text(l.notifDetected, style: Theme.of(context).textTheme.titleMedium),
          ),
          for (final m in bandeja.mensajes) _SmsCard(key: ValueKey(m.id), mensaje: m),
        ],
      );
    }

    return Scaffold(
      appBar: AppBar(
        title: Text(l.notifications),
        actions: [IconButton(tooltip: l.retry, icon: const Icon(Icons.refresh), onPressed: control.cargar)],
      ),
      body: cuerpo,
    );
  }
}

/// Un SMS bancario por revisar. "Aprobar" le pide a la IA que lo interprete y
/// muestra ahí mismo lo que entendió; "Guardar" lo registra sin abrir otra pantalla.
class _SmsCard extends ConsumerStatefulWidget {
  const _SmsCard({super.key, required this.mensaje});

  final SmsMessage mensaje;

  @override
  ConsumerState<_SmsCard> createState() => _SmsCardState();
}

class _SmsCardState extends ConsumerState<_SmsCard> {
  ExpenseDraft? _propuesta;
  bool _busy = false;

  SmsMessage get _m => widget.mensaje;

  Future<void> _aprobar() async {
    setState(() => _busy = true);
    ExpenseDraft? propuesta;
    await guarded(context, () async => propuesta = await ref.read(apiProvider).parseText(_m.cuerpo, source: 'sms'));
    if (mounted) {
      setState(() {
        _busy = false;
        _propuesta = propuesta;
      });
    }
  }

  Future<void> _guardar(ExpenseDraft p) async {
    final l = context.l;
    final api = ref.read(apiProvider);
    final fecha = p.fecha ?? today();
    setState(() => _busy = true);

    Expense? creado;
    final ok = await guarded(context, () async {
      if (p.esIngreso) {
        await api.createIncome(p.monto!, p.descripcion ?? _m.remitente, fecha);
      } else {
        final categorias = await ref.read(categoriesProvider.future);
        final categoria = categorias.firstWhere((c) => c.nombre == p.categoria, orElse: () => categorias.first);
        creado = await api.createExpense({
          'monto': p.monto,
          'category_id': categoria.id,
          'descripcion': p.descripcion ?? _m.remitente,
          'fecha': isoDate(fecha),
          'comercio': null,
          'source': 'sms',
          'texto_original': _m.cuerpo,
        });
      }
    });
    if (!mounted) return;
    if (!ok) return setState(() => _busy = false);

    unawaited(HapticFeedback.lightImpact());
    refreshData(ref);
    ref.read(smsInboxProvider.notifier).marcarRevisado(_m);
    showSnack(p.esIngreso ? l.notifSavedIncome : l.notifSavedExpense);
    // Igual que en el formulario: el mensaje del coach llega después y sin bloquear.
    final nuevo = creado;
    if (nuevo != null) unawaited(api.reaction(nuevo.id).then(showSnack, onError: (_) {}));
  }

  /// Si la propuesta no convence, se corrige en el formulario de siempre.
  Future<void> _editar(ExpenseDraft p) async {
    await Navigator.push(
      context,
      MaterialPageRoute<void>(
        builder: (_) => p.esIngreso ? IncomeFormScreen(draft: p) : ExpenseFormScreen(draft: p),
      ),
    );
    if (mounted) ref.read(smsInboxProvider.notifier).marcarRevisado(_m);
  }

  @override
  Widget build(BuildContext context) {
    final l = context.l;
    final theme = Theme.of(context);
    final p = _propuesta;
    return SectionCard(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              const IconBadge(icon: Icons.sms_outlined),
              const SizedBox(width: 12),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(_m.remitente, style: theme.textTheme.titleSmall),
                    Text(
                      shortDate(context, _m.fecha),
                      style: theme.textTheme.bodySmall?.copyWith(color: theme.colorScheme.onSurfaceVariant),
                    ),
                  ],
                ),
              ),
            ],
          ),
          const SizedBox(height: 12),
          Text(_m.cuerpo, style: theme.textTheme.bodyMedium),
          // Lo que entendió la IA se despliega dentro de la misma tarjeta.
          AnimatedSize(
            duration: motion(context),
            curve: kMotionCurve,
            alignment: Alignment.topCenter,
            child: p == null ? const SizedBox(width: double.infinity) : _Propuesta(propuesta: p),
          ),
          const SizedBox(height: 12),
          if (_busy)
            const Shimmer(child: SkeletonBox(height: 48, radius: AppTokens.radiusField))
          else
            // Los botones van en un renglón; si no caben (pantalla angosta, letra grande), se apilan.
            Align(
              alignment: Alignment.centerRight,
              child: OverflowBar(
                alignment: MainAxisAlignment.end,
                overflowAlignment: OverflowBarAlignment.end,
                spacing: 8,
                overflowSpacing: 4,
                children: [
                  TextButton(
                    onPressed: () => ref.read(smsInboxProvider.notifier).marcarRevisado(_m),
                    child: Text(l.smsDismiss),
                  ),
                  if (p == null)
                    FilledButton(onPressed: _aprobar, child: Text(l.notifApprove))
                  else ...[
                    // Un poco más angostos que lo normal: son tres y deben caber en un teléfono común.
                    FilledButton.tonal(
                      style: FilledButton.styleFrom(padding: const EdgeInsets.symmetric(horizontal: 16)),
                      onPressed: () => _editar(p),
                      child: Text(l.notifEdit),
                    ),
                    FilledButton(
                      style: FilledButton.styleFrom(padding: const EdgeInsets.symmetric(horizontal: 16)),
                      onPressed: () => _guardar(p),
                      child: Text(l.save),
                    ),
                  ],
                ],
              ),
            ),
        ],
      ),
    );
  }
}

class _Propuesta extends ConsumerWidget {
  const _Propuesta({required this.propuesta});

  final ExpenseDraft propuesta;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final l = context.l;
    final theme = Theme.of(context);
    final p = propuesta;
    final acento = p.esIngreso ? context.tokens.income : null;
    final fondo = acento?.container ?? theme.colorScheme.primaryContainer;
    final tinta = acento?.onContainer ?? theme.colorScheme.onPrimaryContainer;
    final categorias = ref.watch(categoriesProvider).value ?? const <Category>[];
    final color = categoryColors(categorias.map((c) => c.nombre), theme.brightness)[p.categoria];
    return Container(
      margin: const EdgeInsets.only(top: 12),
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(color: fondo, borderRadius: BorderRadius.circular(AppTokens.radiusInner)),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            p.esIngreso ? l.notifIsIncome : l.notifIsExpense,
            style: theme.textTheme.labelLarge?.copyWith(color: tinta),
          ),
          FittedBox(
            fit: BoxFit.scaleDown,
            alignment: Alignment.centerLeft,
            child: AnimatedMoney(
              value: p.monto ?? 0,
              style: theme.textTheme.headlineMedium?.copyWith(color: tinta, fontFeatures: kTabular),
            ),
          ),
          const SizedBox(height: 4),
          Row(
            children: [
              if (!p.esIngreso && p.categoria != null) ...[
                CircleAvatar(radius: 5, backgroundColor: color ?? tinta),
                const SizedBox(width: 6),
              ],
              Expanded(
                child: Text(
                  [if (!p.esIngreso) ?p.categoria, ?p.descripcion].join(' · '),
                  style: theme.textTheme.bodyMedium?.copyWith(color: tinta),
                ),
              ),
            ],
          ),
        ],
      ),
    );
  }
}
