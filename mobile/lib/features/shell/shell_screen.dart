import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/motion.dart';
import '../../core/theme.dart';
import '../../core/widgets.dart';
import '../../data/models.dart';
import '../../data/providers.dart';
import '../coach/coach_screen.dart';
import '../home/home_screen.dart';
import '../profile/profile_screen.dart';
import '../progress/progress_screen.dart';
import '../transactions/add_sheet.dart';
import '../transactions/transactions_screen.dart';

/// Contenedor de las cinco pestañas principales.
class ShellScreen extends ConsumerStatefulWidget {
  const ShellScreen({super.key});

  @override
  ConsumerState<ShellScreen> createState() => _ShellScreenState();
}

class _ShellScreenState extends ConsumerState<ShellScreen> with SingleTickerProviderStateMixin {
  int _index = 0;

  // Fundido corto al cambiar de pestaña. Se anima el contenedor y no cada
  // pestaña, para que todas conserven su estado dentro del IndexedStack.
  late final _fundido = AnimationController(vsync: this, duration: const Duration(milliseconds: 220), value: 1);

  @override
  void dispose() {
    _fundido.dispose();
    super.dispose();
  }

  void _irA(int i) {
    if (i == _index) return;
    setState(() => _index = i);
    if (!MediaQuery.disableAnimationsOf(context)) _fundido.forward(from: 0);
  }

  void _celebrar(GamificationProfile perfil) {
    final l = context.l;
    if (perfil.nuevasInsignias.isNotEmpty) {
      showDialog<void>(
        context: context,
        builder: (context) => _BadgeDialog(insignias: perfil.nuevasInsignias),
      );
    } else if (perfil.nuevosPuntos > 0) {
      showSnack(l.pointsEarned(perfil.nuevosPuntos));
    }
  }

  @override
  Widget build(BuildContext context) {
    final l = context.l;
    // El backend informa lo otorgado en cada consulta una sola vez: se celebra aquí.
    ref.listen(gamificationProvider, (_, actual) {
      final perfil = actual.value;
      if (perfil != null && !actual.isLoading) _celebrar(perfil);
    });

    final tieneBudget = ref.watch(summaryProvider).value != null;
    return Scaffold(
      body: SafeArea(
        child: FadeTransition(
          opacity: CurvedAnimation(parent: _fundido, curve: kMotionCurve),
          child: IndexedStack(
            index: _index,
            children: [
              HomeScreen(onOpenCoach: () => _irA(2)),
              const TransactionsScreen(),
              const CoachScreen(),
              const ProgressScreen(),
              const ProfileScreen(),
            ],
          ),
        ),
      ),
      floatingActionButton: _index <= 1 && tieneBudget
          ? FloatingActionButton.extended(
              onPressed: () => showAddSheet(context),
              icon: const Icon(Icons.add),
              label: Text(l.add),
            )
          : null,
      // Barra flotante: separada de los bordes y con las esquinas del mosaico.
      bottomNavigationBar: SafeArea(
        minimum: const EdgeInsets.fromLTRB(8, 0, 8, 10),
        child: ClipRRect(
          borderRadius: BorderRadius.circular(AppTokens.radius),
          child: MediaQuery(
            // Sin el margen inferior (ya lo da el SafeArea) y con la letra acotada para que quepan las etiquetas.
            data: MediaQuery.of(context).removePadding(removeBottom: true).copyWith(
                  textScaler: MediaQuery.textScalerOf(context).clamp(maxScaleFactor: 1.15),
                ),
            child: NavigationBar(
              selectedIndex: _index,
              onDestinationSelected: (i) {
                tapFeedback();
                _irA(i);
              },
              destinations: [
                NavigationDestination(icon: const Icon(Icons.home_outlined), selectedIcon: const Icon(Icons.home_rounded), label: l.tabHome),
                NavigationDestination(icon: const Icon(Icons.receipt_long_outlined), selectedIcon: const Icon(Icons.receipt_long), label: l.tabTransactions),
                NavigationDestination(icon: const Icon(Icons.auto_awesome_outlined), selectedIcon: const Icon(Icons.auto_awesome), label: l.tabCoach),
                NavigationDestination(icon: const Icon(Icons.emoji_events_outlined), selectedIcon: const Icon(Icons.emoji_events), label: l.tabProgress),
                NavigationDestination(icon: const Icon(Icons.person_outline), selectedIcon: const Icon(Icons.person), label: l.tabProfile),
              ],
            ),
          ),
        ),
      ),
    );
  }
}

/// Celebración de una insignia nueva: el ícono entra creciendo con un rebote.
class _BadgeDialog extends StatelessWidget {
  const _BadgeDialog({required this.insignias});

  final List<String> insignias;

  @override
  Widget build(BuildContext context) {
    final l = context.l;
    final theme = Theme.of(context);
    final scheme = theme.colorScheme;
    final tokens = context.tokens;
    return Stack(
      children: [
        AlertDialog(
          icon: TweenAnimationBuilder<double>(
            tween: Tween(begin: 0, end: 1),
            duration: motion(context, const Duration(milliseconds: 700)),
            curve: Curves.elasticOut,
            builder: (context, t, child) => Transform.scale(scale: t, child: child),
            child: CircleAvatar(
              radius: 40,
              backgroundColor: tokens.goals.container,
              child: Icon(Icons.military_tech, size: 48, color: tokens.goals.onContainer),
            ),
          ),
          title: Text(l.badgeUnlocked, textAlign: TextAlign.center),
          content: Text(insignias.join('\n'), textAlign: TextAlign.center, style: theme.textTheme.titleMedium),
          actionsAlignment: MainAxisAlignment.center,
          actions: [FilledButton(onPressed: () => Navigator.pop(context), child: Text(l.great))],
        ),
        Positioned.fill(
          child: ConfettiBurst(
            colors: [scheme.primary, tokens.goals.color, tokens.challenges.color, tokens.coach.color, tokens.income.color],
          ),
        ),
      ],
    );
  }
}
