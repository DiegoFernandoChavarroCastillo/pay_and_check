import 'dart:async';

import 'package:flutter/foundation.dart' show kIsWeb;
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
import '../profile/plan_screen.dart';
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
  // "Recibiste", "te envió", "enviaste": así hablan las notificaciones de Nequi y Daviplata.
  r'compra|pago|pagaste|retiro|transacci|transferencia|d[ée]bito|consumo|recibiste|te envi|enviaste|abono'
  r'|purchase|payment|withdrawal|charged|received|sent you',
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

  /// Si la persona activó el acceso a notificaciones (Ajustes de Android) para leer las de Nequi, Daviplata…
  Future<bool> notifHasAccess() async => await _channel.invokeMethod<bool>('notifHasAccess') ?? false;

  Future<void> openNotifSettings() => _channel.invokeMethod<void>('openNotifSettings');

  /// Notificaciones de apps de pago guardadas en el teléfono por `BankNotificationListener.kt`; el remitente es
  /// el nombre del banco.
  Future<List<SmsMessage>> readNotifications(DateTime desde) async {
    final crudos = await _channel.invokeListMethod<Map<Object?, Object?>>(
      'readNotifications',
      {'since': desde.millisecondsSinceEpoch},
    );
    return (crudos ?? const []).map(SmsMessage.fromMap).toList();
  }
}

final smsSourceProvider = Provider<SmsSource>((ref) => const SmsSource());

/// Movimientos bancarios detectados en los SMS y todavía sin revisar.
class SmsInboxState {
  const SmsInboxState({this.permiso, this.notificaciones, this.mensajes = const [], this.error});

  /// null mientras no se sabe; false si la persona no ha dado el permiso.
  final bool? permiso;

  /// Acceso a las notificaciones de apps de pago: null mientras no se sabe.
  final bool? notificaciones;
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
    // En la versión web no hay SMS ni notificaciones de otras apps: la bandeja queda "al día" y Notificaciones
    // muestra solo los gastos fijos por pagar.
    if (kIsWeb) {
      if (ref.mounted) state = const SmsInboxState(permiso: true, notificaciones: true);
      return;
    }
    final fuente = ref.read(smsSourceProvider);
    try {
      // Sin el consentimiento de la app (PS-48) no se leen SMS, aunque Android ya tenga el permiso: la bandeja
      // se muestra como "sin permiso" y el botón pasa primero por la hoja de consentimiento.
      final consentido = ref.read(sessionProvider).value?.smsConsentido ?? false;
      var permiso = consentido && await fuente.hasPermission();
      if (consentido && !permiso && pedirPermiso) permiso = await fuente.requestPermission();

      // Las notificaciones de Nequi, Daviplata y bancos van con el mismo consentimiento y a la misma bandeja.
      final notificaciones = consentido && await fuente.notifHasAccess();

      final desde = DateTime.now().subtract(const Duration(days: _diasAtras));
      final revisados = _ids;
      bool pendiente(SmsMessage m) => pareceMovimientoBancario(m.cuerpo) && !revisados.contains('${m.id}');
      final sms = permiso ? (await fuente.read(desde)).where(pendiente).toList() : <SmsMessage>[];
      final avisos = notificaciones ? (await fuente.readNotifications(desde)).where(pendiente).toList() : <SmsMessage>[];
      // Los SMS ya llegan del más reciente al más antiguo; las notificaciones se intercalan por fecha.
      final mensajes = avisos.isEmpty ? sms : ([...sms, ...avisos]..sort((a, b) => b.fecha.compareTo(a.fecha)));
      if (ref.mounted) {
        state = SmsInboxState(permiso: permiso, notificaciones: notificaciones, mensajes: mensajes);
      }
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
      notificaciones: state.notificaciones,
      mensajes: state.mensajes.where((m) => m.id != mensaje.id).toList(),
    );
  }
}

final smsInboxProvider = NotifierProvider<SmsInbox, SmsInboxState>(SmsInbox.new);

/// Pide el permiso de SMS, siempre después del consentimiento de la app: qué se
/// lee, dónde queda y cómo revocarlo. Si la persona no acepta, no se pide el
/// permiso de Android y la app sigue funcionando sin SMS.
Future<void> permitirSms(BuildContext context, WidgetRef ref) async {
  if (!await _asegurarConsentimiento(context, ref)) return;
  await ref.read(smsInboxProvider.notifier).cargar(pedirPermiso: true);
}

/// El consentimiento de la app (PS-48) antes de cualquier permiso de Android. True si ya está dado.
Future<bool> _asegurarConsentimiento(BuildContext context, WidgetRef ref) async {
  if (ref.read(sessionProvider).value?.smsConsentido ?? false) return true;
  final acepta = await showModalBottomSheet<bool>(
    context: context,
    isScrollControlled: true,
    showDragHandle: true,
    builder: (_) => const _ConsentimientoSms(),
  );
  if (acepta != true || !context.mounted) return false;
  return guarded(context, () => ref.read(sessionProvider.notifier).setSmsConsent(true));
}

/// Abre Ajustes → Acceso a notificaciones, tras el consentimiento. Al volver a la app se recarga la bandeja.
Future<void> permitirNotificaciones(BuildContext context, WidgetRef ref) async {
  if (!await _asegurarConsentimiento(context, ref)) return;
  final control = ref.read(smsInboxProvider.notifier);
  late final AppLifecycleListener escucha;
  escucha = AppLifecycleListener(
    onResume: () {
      escucha.dispose();
      control.cargar();
    },
  );
  await ref.read(smsSourceProvider).openNotifSettings();
}

/// La captura automática es de los planes pagos (docs/planes.md); el backend también lo exige.
bool capturaBloqueada(WidgetRef ref) => ref.watch(subscriptionProvider).value?.plan == 'gratis';

class _ConsentimientoSms extends StatelessWidget {
  const _ConsentimientoSms();

  @override
  Widget build(BuildContext context) {
    final l = context.l;
    final theme = Theme.of(context);
    final puntos = [
      (Icons.phone_android_outlined, l.smsConsentPoint1),
      (Icons.auto_awesome_outlined, l.smsConsentPoint2),
      (Icons.settings_outlined, l.smsConsentPoint3),
    ];
    // Desplazable: en pantallas bajas (o con letra grande) el texto no cabe entero.
    return SafeArea(
      child: SingleChildScrollView(
        padding: const EdgeInsets.fromLTRB(20, 0, 20, 16),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Text(l.smsConsentTitle, style: theme.textTheme.titleLarge),
            const SizedBox(height: 8),
            Text(l.smsConsentBody, style: theme.textTheme.bodyMedium),
            const SizedBox(height: 12),
            for (final (icono, texto) in puntos)
              Padding(
                padding: const EdgeInsets.symmetric(vertical: 6),
                child: Row(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Icon(icono, size: 20, color: theme.colorScheme.primary),
                    const SizedBox(width: 12),
                    Expanded(child: Text(texto, style: theme.textTheme.bodyMedium)),
                  ],
                ),
              ),
            const SizedBox(height: 16),
            FilledButton(
              key: const ValueKey('sms-consent-accept'),
              onPressed: () => Navigator.pop(context, true),
              style: FilledButton.styleFrom(minimumSize: const Size.fromHeight(52)),
              child: Text(l.smsConsentAccept),
            ),
            const SizedBox(height: 8),
            TextButton(onPressed: () => Navigator.pop(context, false), child: Text(l.smsConsentDecline)),
          ],
        ),
      ),
    );
  }
}

/// Campana del inicio: cuántos movimientos detectados esperan revisión.
class NotificationsBell extends ConsumerWidget {
  const NotificationsBell({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    // Lo que espera a la persona: SMS del banco por revisar y gastos fijos por pagar.
    final pendientes = ref.watch(smsInboxProvider.select((s) => s.mensajes.length)) +
        (ref.watch(pendingPaymentsProvider).value?.length ?? 0);
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

    final pagos = ref.watch(pendingPaymentsProvider).value ?? const <PendingPayment>[];
    final titulo = Theme.of(context).textTheme.titleMedium;

    final bloqueada = !kIsWeb && capturaBloqueada(ref);
    // Arriba de todo, lo que falta para que la captura funcione: el plan o el acceso a las notificaciones.
    final Widget? aviso = bloqueada
        ? _AvisoCaptura(
            icono: Icons.lock_outline,
            texto: l.captureLocked,
            accion: l.seePlans,
            onPressed: () => Navigator.push(context, MaterialPageRoute<void>(builder: (_) => const PlanScreen())),
          )
        : bandeja.notificaciones == false
            ? _AvisoCaptura(
                icono: Icons.notifications_active_outlined,
                titulo: l.notifAccessTitle,
                texto: l.notifAccessBody,
                accion: l.notifAccessAction,
                onPressed: () => permitirNotificaciones(context, ref),
              )
            : null;
    final mensajes = bloqueada ? const <SmsMessage>[] : bandeja.mensajes;

    final Widget cuerpo;
    if (pagos.isEmpty && mensajes.isEmpty) {
      // Nada por revisar: se explica el estado de los SMS (sin permiso, no disponible o al día).
      final Widget vacio;
      if (bloqueada) {
        vacio = const SizedBox.shrink();
      } else if (bandeja.permiso == false) {
        vacio = EmptyView(
          icon: Icons.sms_outlined,
          text: l.smsExplain,
          action: FilledButton(onPressed: () => permitirSms(context, ref), child: Text(l.smsAllow)),
        );
      } else if (bandeja.permiso == null && bandeja.error == null) {
        vacio = const CircularProgressIndicator();
      } else {
        vacio = EmptyView(icon: Icons.mark_email_read_outlined, text: l.smsEmpty);
      }
      cuerpo = ListView(
        padding: const EdgeInsets.all(16),
        children: [
          ?aviso,
          const SizedBox(height: 24),
          Center(child: vacio),
        ],
      );
    } else {
      cuerpo = ListView(
        padding: const EdgeInsets.all(16),
        children: [
          ?aviso,
          if (pagos.isNotEmpty) ...[
            Padding(
              padding: const EdgeInsets.only(left: 4, bottom: 12),
              child: Text(l.paymentsDue, style: titulo),
            ),
            for (final p in pagos) _PaymentCard(key: ValueKey('pago-${p.recurringId}-${p.fecha}'), pago: p),
          ],
          if (mensajes.isNotEmpty) ...[
            Padding(
              padding: EdgeInsets.only(left: 4, bottom: 12, top: pagos.isEmpty ? 0 : 8),
              child: Text(l.notifDetected, style: titulo),
            ),
            for (final m in mensajes) _SmsCard(key: ValueKey(m.id), mensaje: m),
          ],
        ],
      );
    }

    return Scaffold(
      appBar: AppBar(
        title: Text(l.notifications),
        actions: [
          IconButton(
            tooltip: l.retry,
            icon: const Icon(Icons.refresh),
            onPressed: () {
              ref.invalidate(pendingPaymentsProvider);
              control.cargar();
            },
          ),
        ],
      ),
      body: cuerpo,
    );
  }
}

/// Tarjeta que explica qué falta para la captura automática (plan o acceso a notificaciones).
class _AvisoCaptura extends StatelessWidget {
  const _AvisoCaptura({required this.icono, this.titulo, required this.texto, required this.accion, required this.onPressed});

  final IconData icono;
  final String? titulo;
  final String texto;
  final String accion;
  final VoidCallback onPressed;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final acento = context.tokens.coach;
    return Padding(
      padding: const EdgeInsets.only(bottom: 16),
      child: SectionCard(
        color: acento.container,
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Icon(icono, color: acento.onContainer),
                const SizedBox(width: 12),
                Expanded(
                  child: Text(
                    titulo ?? texto,
                    style: (titulo == null ? theme.textTheme.bodyMedium : theme.textTheme.titleSmall)
                        ?.copyWith(color: acento.onContainer),
                  ),
                ),
              ],
            ),
            if (titulo != null) ...[
              const SizedBox(height: 8),
              Text(texto, style: theme.textTheme.bodyMedium?.copyWith(color: acento.onContainer)),
            ],
            const SizedBox(height: 12),
            FilledButton(onPressed: onPressed, child: Text(accion)),
          ],
        ),
      ),
    );
  }
}

/// Un gasto fijo que ya venció. "Ya lo pagué" lo registra como gasto y lo descuenta del disponible;
/// "Omitir" lo salta hasta el siguiente vencimiento.
class _PaymentCard extends ConsumerStatefulWidget {
  const _PaymentCard({super.key, required this.pago});

  final PendingPayment pago;

  @override
  ConsumerState<_PaymentCard> createState() => _PaymentCardState();
}

class _PaymentCardState extends ConsumerState<_PaymentCard> {
  bool _busy = false;

  Future<void> _resolver({required bool pagado}) async {
    final l = context.l;
    final api = ref.read(apiProvider);
    setState(() => _busy = true);
    Expense? gasto;
    final ok = await guarded(context, () async {
      if (pagado) {
        gasto = await api.payRecurring(widget.pago.recurringId);
      } else {
        await api.skipRecurring(widget.pago.recurringId);
      }
    });
    if (!mounted) return;
    if (!ok) return setState(() => _busy = false);

    if (pagado) unawaited(HapticFeedback.lightImpact());
    refreshData(ref);
    showSnack(pagado ? l.paymentLogged : l.paymentSkipped);
    final nuevo = gasto;
    if (nuevo != null) unawaited(api.reaction(nuevo.id).then(showSnack, onError: (_) {}));
  }

  @override
  Widget build(BuildContext context) {
    final l = context.l;
    final theme = Theme.of(context);
    final acento = context.tokens.goals;
    final p = widget.pago;
    return SectionCard(
      color: acento.container,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              IconBadge(icon: Icons.event_available_outlined, color: acento.color, foreground: acento.container),
              const SizedBox(width: 12),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(p.descripcion, style: theme.textTheme.titleSmall?.copyWith(color: acento.onContainer)),
                    Text(
                      l.dueSince(shortDate(context, p.fecha)),
                      style: theme.textTheme.bodySmall?.copyWith(color: acento.onContainer),
                    ),
                  ],
                ),
              ),
              Text(
                money(p.monto),
                style: theme.textTheme.titleMedium?.copyWith(color: acento.onContainer, fontFeatures: kTabular),
              ),
            ],
          ),
          const SizedBox(height: 12),
          if (_busy)
            const Shimmer(child: SkeletonBox(height: 48, radius: AppTokens.radiusField))
          else
            Align(
              alignment: Alignment.centerRight,
              child: OverflowBar(
                alignment: MainAxisAlignment.end,
                overflowAlignment: OverflowBarAlignment.end,
                spacing: 8,
                overflowSpacing: 4,
                children: [
                  TextButton(onPressed: () => _resolver(pagado: false), child: Text(l.skipAction)),
                  FilledButton(onPressed: () => _resolver(pagado: true), child: Text(l.paidAction)),
                ],
              ),
            ),
        ],
      ),
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
    try {
      propuesta = await ref.read(apiProvider).parseText(_m.cuerpo, source: 'sms');
    } catch (e) {
      if (!mounted) return;
      showSnack(errorMessage(e, context.l));
      if (esSinIA(e)) {
        // Sin IA se registra con el formulario manual; si se guarda, el SMS queda revisado.
        setState(() => _busy = false);
        final guardado = await Navigator.push<bool>(
          context,
          MaterialPageRoute(builder: (_) => ExpenseFormScreen(draft: borradorManual(_m.cuerpo, descripcion: _m.remitente))),
        );
        if (guardado == true) ref.read(smsInboxProvider.notifier).marcarRevisado(_m);
        return;
      }
    }
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
                  [if (!p.esIngreso && p.categoria != null) catLabel(context, p.categoria!), ?p.descripcion].join(' · '),
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
