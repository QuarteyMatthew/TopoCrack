import 'package:flutter/material.dart';

/// Barra superiore con icona folder, icona profilo e pulsante "-"
/// corrisponde esattamente al design negli screenshot forniti
class TopBar extends StatelessWidget {
  final bool isDark;
  final bool showUserMenu;
  final VoidCallback onFolderTap;
  final VoidCallback onProfileTap;
  final VoidCallback onMinusTap;

  const TopBar({
    super.key,
    required this.isDark,
    required this.showUserMenu,
    required this.onFolderTap,
    required this.onProfileTap,
    required this.onMinusTap,
  });

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
      child: Row(
        children: [
          // ─── ICONA FOLDER (sinistra) ─────────────────────────────────
          _TopBarButton(
            isDark: isDark,
            highlighted: false,
            onTap: onFolderTap,
            child: const Icon(
              Icons.folder,
              color: Colors.white,
              size: 22,
            ),
          ),

          const Spacer(),

          // ─── ICONA PROFILO (destra, prima del "-") ──────────────────
          _TopBarButton(
            isDark: isDark,
            highlighted: showUserMenu,
            onTap: onProfileTap,
            child: const Icon(
              Icons.person_outline,
              color: Colors.white,
              size: 22,
            ),
          ),

          const SizedBox(width: 10),

          // ─── PULSANTE "–" (destra) ──────────────────────────────────
          _TopBarButton(
            isDark: isDark,
            highlighted: false,
            onTap: onMinusTap,
            child: const Icon(
              Icons.remove,
              color: Colors.white,
              size: 22,
            ),
          ),
        ],
      ),
    );
  }
}

class _TopBarButton extends StatelessWidget {
  final bool isDark;
  final bool highlighted;
  final VoidCallback onTap;
  final Widget child;

  const _TopBarButton({
    required this.isDark,
    required this.highlighted,
    required this.onTap,
    required this.child,
  });

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTap: onTap,
      child: AnimatedContainer(
        duration: const Duration(milliseconds: 200),
        width: 44,
        height: 44,
        decoration: BoxDecoration(
          // glassmorphism leggero come nello screenshot
          color: highlighted
              ? Colors.white.withOpacity(0.30)
              : (isDark
                  ? Colors.black.withOpacity(0.40)
                  : Colors.white.withOpacity(0.28)),
          shape: BoxShape.circle,
          border: Border.all(
            color: Colors.white.withOpacity(0.25),
            width: 1,
          ),
          boxShadow: [
            BoxShadow(
              color: Colors.black.withOpacity(0.15),
              blurRadius: 8,
              offset: const Offset(0, 2),
            ),
          ],
        ),
        child: Center(child: child),
      ),
    );
  }
}
