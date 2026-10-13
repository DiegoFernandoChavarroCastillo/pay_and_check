import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/format.dart';
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
            child: Align(
              alignment: Alignment.centerLeft,
              child: Text(l.tabCoach, style: Theme.of(context).textTheme.headlineSmall),
            ),
          ),
          TabBar(tabs: [Tab(text: l.coachTips), Tab(text: l.coachChat)]),
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
          padding: const EdgeInsets.all(16),
          children: [
            if (insights.isEmpty)
              EmptyView(icon: Icons.auto_awesome_outlined, text: l.noInsights)
            else
              for (final insight in insights) InsightCard(insight: insight),
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
    if (mensajes == null) return const Center(child: CircularProgressIndicator());

    return Column(
      children: [
        Expanded(
          child: mensajes.isEmpty
              ? Center(child: EmptyView(icon: Icons.forum_outlined, text: l.chatEmpty))
              : ListView.builder(
                  controller: _scroll,
                  padding: const EdgeInsets.all(16),
                  itemCount: mensajes.length + (_enviando ? 1 : 0),
                  itemBuilder: (context, i) => i == mensajes.length
                      ? const _Bubble(texto: '…', delCoach: true)
                      : _Bubble(texto: mensajes[i].contenido, delCoach: mensajes[i].esDelCoach),
                ),
        ),
        Padding(
          padding: const EdgeInsets.fromLTRB(16, 4, 8, 12),
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
  const _Bubble({required this.texto, required this.delCoach});

  final String texto;
  final bool delCoach;

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    return Align(
      alignment: delCoach ? Alignment.centerLeft : Alignment.centerRight,
      child: Container(
        margin: const EdgeInsets.only(bottom: 8),
        padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
        constraints: BoxConstraints(maxWidth: MediaQuery.sizeOf(context).width * 0.8),
        decoration: BoxDecoration(
          color: delCoach ? scheme.surfaceContainerHigh : scheme.primaryContainer,
          borderRadius: BorderRadius.circular(18),
        ),
        child: Text(
          texto,
          style: TextStyle(color: delCoach ? scheme.onSurface : scheme.onPrimaryContainer),
        ),
      ),
    );
  }
}
