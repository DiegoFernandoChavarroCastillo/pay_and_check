import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/format.dart';
import '../../core/motion.dart';
import '../../core/theme.dart';
import '../../core/widgets.dart';
import '../../data/api.dart';
import '../../data/models.dart';
import '../../data/providers.dart';
import 'coach_widgets.dart';

/// Coach: consejos accionables del día y chat.
class CoachScreen extends StatelessWidget {
  const CoachScreen({super.key});

  @override
  Widget build(BuildContext context) {
    final l = context.l;
    return DefaultTabController(
      length: 2,
      child: Column(
        children: [
          Padding(
            padding: const EdgeInsets.fromLTRB(16, 16, 16, 0),
            child: Row(
              children: [
                const CoachAvatar(size: 56),
                const SizedBox(width: 12),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(l.tabCoach, style: Theme.of(context).textTheme.headlineSmall),
                      Text(
                        l.coachTagline,
                        style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                              color: Theme.of(context).colorScheme.onSurfaceVariant,
                            ),
                      ),
                    ],
                  ),
                ),
              ],
            ),
          ),
          PillTabs(labels: [l.coachTips, l.coachChat]),
          const Expanded(child: TabBarView(children: [_Insights(), _Chat()])),
        ],
      ),
    );
  }
}

class _Insights extends ConsumerWidget {
  const _Insights();

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final l = context.l;
    return RefreshIndicator(
      // Tirar para refrescar pide al backend recalcular con los datos de ahora.
      onRefresh: () async {
        await ref.read(apiProvider).insights(refresh: true);
        ref.invalidate(insightsProvider);
        await ref.read(insightsProvider.future);
      },
      child: AsyncView(
        value: ref.watch(insightsProvider),
        onRetry: () => ref.invalidate(insightsProvider),
        builder: (insights) => ListView(
          padding: EdgeInsets.fromLTRB(16, 16, 16, 16 + bottomInset(context)),
          children: [
            if (insights.isEmpty)
              EmptyView(icon: Icons.auto_awesome_outlined, text: l.noInsights)
            else
              ...staggered([for (final insight in insights) InsightCard(insight: insight)]),
            Padding(
              padding: const EdgeInsets.only(top: 8),
              child: Text(
                l.coachDisclaimer,
                style: Theme.of(context).textTheme.bodySmall,
                textAlign: TextAlign.center,
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _Chat extends ConsumerStatefulWidget {
  const _Chat();

  @override
  ConsumerState<_Chat> createState() => _ChatState();
}

class _ChatState extends ConsumerState<_Chat> with AutomaticKeepAliveClientMixin {
  final _input = TextEditingController();
  final _scroll = ScrollController();
  List<ChatMessage>? _mensajes;
  Object? _error;
  bool _enviando = false;

  @override
  bool get wantKeepAlive => true;

  @override
  void initState() {
    super.initState();
    _cargar();
  }

  @override
  void dispose() {
    _input.dispose();
    _scroll.dispose();
    super.dispose();
  }

  Future<void> _cargar() async {
    setState(() => _error = null);
    try {
      final historial = await ref.read(apiProvider).chatHistory();
      if (mounted) setState(() => _mensajes = historial);
      _alFinal();
    } catch (e) {
      if (mounted) setState(() => _error = e);
    }
  }

  void _alFinal() {
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (_scroll.hasClients) _scroll.jumpTo(_scroll.position.maxScrollExtent);
    });
  }

  Future<void> _enviar() async {
    final texto = _input.text.trim();
    final mensajes = _mensajes;
    if (texto.isEmpty || mensajes == null || _enviando) return;

    final l = context.l;
    final propio = ChatMessage.local(texto);
    setState(() {
      mensajes.add(propio);
      _enviando = true;
    });
    _input.clear();
    _alFinal();

    try {
      final respuesta = await ref.read(apiProvider).sendChat(texto);
      if (mounted) setState(() => mensajes.add(respuesta));
    } catch (e) {
      // El backend no guardó nada: se devuelve el texto para reintentar.
      if (mounted) {
        setState(() => mensajes.remove(propio));
        _input.text = texto;
        showSnack(errorMessage(e, l));
      }
    } finally {
      if (mounted) setState(() => _enviando = false);
      _alFinal();
    }
  }

  @override
  Widget build(BuildContext context) {
    super.build(context);
    final l = context.l;
    final mensajes = _mensajes;
    if (_error != null) return Center(child: ErrorView(error: _error!, onRetry: _cargar));
    if (mensajes == null) {
      return const Padding(
        padding: EdgeInsets.all(16),
        child: Shimmer(
          child: Column(
            children: [
              Align(alignment: Alignment.centerLeft, child: SkeletonBox(height: 56, width: 240, radius: 20)),
              SizedBox(height: 8),
              Align(alignment: Alignment.centerRight, child: SkeletonBox(height: 40, width: 180, radius: 20)),
              SizedBox(height: 8),
              Align(alignment: Alignment.centerLeft, child: SkeletonBox(height: 72, width: 260, radius: 20)),
            ],
          ),
        ),
      );
    }

    return Column(
      children: [
        Expanded(
          child: mensajes.isEmpty
              ? Center(child: EmptyView(icon: Icons.forum_outlined, text: l.chatEmpty))
              : ListView.builder(
                  controller: _scroll,
                  padding: const EdgeInsets.all(16),
                  itemCount: mensajes.length + (_enviando ? 1 : 0),
                  itemBuilder: (context, i) {
                    if (i == mensajes.length) return const _Bubble(delCoach: true, child: _Typing());
                    final burbuja = _Bubble(texto: mensajes[i].contenido, delCoach: mensajes[i].esDelCoach);
                    // Solo lo recién dicho entra animado; el historial ya estaba ahí.
                    return i >= mensajes.length - 2 ? FadeSlideIn(key: ValueKey(mensajes[i]), child: burbuja) : burbuja;
                  },
                ),
        ),
        Padding(
          // El campo queda por encima de la barra flotante (o del teclado, si está abierto).
          padding: EdgeInsets.fromLTRB(16, 4, 12, 12 + bottomInset(context)),
          child: Row(
            children: [
              Expanded(
                child: TextField(
                  controller: _input,
                  minLines: 1,
                  maxLines: 4,
                  maxLength: 1000,
                  textCapitalization: TextCapitalization.sentences,
                  decoration: InputDecoration(hintText: l.chatHint, counterText: ''),
                  onSubmitted: (_) => _enviar(),
                ),
              ),
              const SizedBox(width: 8),
              IconButton.filled(
                tooltip: l.send,
                onPressed: _enviando ? null : _enviar,
                icon: const Icon(Icons.send),
              ),
            ],
          ),
        ),
      ],
    );
  }
}

class _Bubble extends StatelessWidget {
  const _Bubble({this.texto, required this.delCoach, this.child});

  final String? texto;
  final bool delCoach;
  final Widget? child;

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    final coach = context.tokens.coach;
    const redondo = Radius.circular(AppTokens.radiusInner);
    const pico = Radius.circular(6);
    return Align(
      alignment: delCoach ? Alignment.centerLeft : Alignment.centerRight,
      child: Container(
        margin: const EdgeInsets.only(bottom: 8),
        padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
        constraints: BoxConstraints(maxWidth: MediaQuery.sizeOf(context).width * 0.8),
        decoration: BoxDecoration(
          color: delCoach ? coach.container : scheme.primary,
          // La esquina "de quien habla" es la menos redonda.
          borderRadius: BorderRadius.only(
            topLeft: redondo,
            topRight: redondo,
            bottomLeft: delCoach ? pico : redondo,
            bottomRight: delCoach ? redondo : pico,
          ),
        ),
        child: child ??
            Text(
              texto!,
              style: Theme.of(context).textTheme.bodyLarge?.copyWith(
                    color: delCoach ? coach.onContainer : scheme.onPrimary,
                  ),
            ),
      ),
    );
  }
}

/// Tres puntos que saltan mientras el coach escribe.
class _Typing extends StatefulWidget {
  const _Typing();

  @override
  State<_Typing> createState() => _TypingState();
}

class _TypingState extends State<_Typing> with SingleTickerProviderStateMixin {
  late final _c = AnimationController(vsync: this, duration: const Duration(milliseconds: 1100));

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    if (!ambient(context)) {
      _c.stop();
    } else if (!_c.isAnimating) {
      _c.repeat();
    }
  }

  @override
  void dispose() {
    _c.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final color = context.tokens.coach.onContainer;
    return Semantics(
      label: '…',
      child: SizedBox(
        height: 20,
        child: AnimatedBuilder(
          animation: _c,
          builder: (context, _) => Row(
            mainAxisSize: MainAxisSize.min,
            children: [
              for (var i = 0; i < 3; i++)
                Padding(
                  padding: const EdgeInsets.symmetric(horizontal: 3),
                  child: Transform.translate(
                    // Cada punto sube y baja con un pequeño retraso respecto al anterior.
                    offset: Offset(0, -5 * Curves.easeInOut.transform((1 - ((_c.value - i * 0.18) % 1 * 2 - 1).abs()).clamp(0, 1).toDouble())),
                    child: Container(
                      width: 7,
                      height: 7,
                      decoration: BoxDecoration(color: color.withValues(alpha: 0.7), shape: BoxShape.circle),
                    ),
                  ),
                ),
            ],
          ),
        ),
      ),
    );
  }
}
