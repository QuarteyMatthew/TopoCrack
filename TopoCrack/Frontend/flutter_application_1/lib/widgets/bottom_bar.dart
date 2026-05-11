import 'package:flutter/material.dart';

/// Barra inferiore con tre azioni: segnalibro, camera (pulsante centrale grande),
/// galleria. Corrisponde esattamente al design negli screenshot.
class BottomBar extends StatelessWidget {
  final bool isDark;
  final VoidCallback onBookmarkTap;
  final VoidCallback onCameraTap;
  final VoidCallback onGalleryTap;

  const BottomBar({
    super.key,
    required this.isDark,
    required this.onBookmarkTap,
    required this.onCameraTap,
    required this.onGalleryTap,
  });

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 24, left: 48, right: 48),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.spaceBetween,
        crossAxisAlignment: CrossAxisAlignment.end,
        children: [
          // ─── SEGNALIBRO ────────────────────────────────────────────────
          _SmallBarButton(
            isDark: isDark,
            onTap: onBookmarkTap,
            child: const Icon(
              Icons.bookmark_border,
              color: Colors.white,
              size: 22,
            ),
          ),

          // ─── CAMERA (pulsante centrale grande bianco) ───────────────────
          GestureDetector(
            onTap: onCameraTap,
            child: Container(
              width: 64,
              height: 64,
              decoration: BoxDecoration(
                color: isDark ? Colors.white : Colors.white,
                shape: BoxShape.circle,
                boxShadow: [
                  BoxShadow(
                    color: Colors.black.withOpacity(0.25),
                    blurRadius: 16,
                    offset: const Offset(0, 4),
                  ),
                ],
              ),
              child: Icon(
                Icons.camera_alt_outlined,
                size: 28,
                color: isDark ? Colors.black87 : Colors.black87,
              ),
            ),
          ),

          // ─── GALLERIA ──────────────────────────────────────────────────
          _SmallBarButton(
            isDark: isDark,
            onTap: onGalleryTap,
            child: const Icon(
              Icons.photo_outlined,
              color: Colors.white,
              size: 22,
            ),
          ),
        ],
      ),
    );
  }
}

class _SmallBarButton extends StatelessWidget {
  final bool isDark;
  final VoidCallback onTap;
  final Widget child;

  const _SmallBarButton({
    required this.isDark,
    required this.onTap,
    required this.child,
  });

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTap: onTap,
      child: Container(
        width: 44,
        height: 44,
        decoration: BoxDecoration(
          color: isDark
              ? Colors.white.withOpacity(0.12)
              : Colors.white.withOpacity(0.22),
          shape: BoxShape.circle,
          border: Border.all(
            color: Colors.white.withOpacity(0.20),
            width: 1,
          ),
        ),
        child: Center(child: child),
      ),
    );
  }
}
