import 'package:flutter/material.dart';

/// Menu dropdown utente: appare quando si preme l'icona profilo.
/// Corrisponde esattamente al terzo schermo negli screenshot:
/// User Info | Application Settings | TopoCrack
class UserMenu extends StatelessWidget {
  final bool isDark;
  final VoidCallback onUserInfo;
  final VoidCallback onSettings;
  final VoidCallback onTopoCrack;

  const UserMenu({
    super.key,
    required this.isDark,
    required this.onUserInfo,
    required this.onSettings,
    required this.onTopoCrack,
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      width: 220,
      decoration: BoxDecoration(
        // Glassmorphism card come nello screenshot
        color: isDark
            ? Colors.black.withOpacity(0.55)
            : Colors.white.withOpacity(0.82),
        borderRadius: BorderRadius.circular(20),
        border: Border.all(
          color: isDark
              ? Colors.white.withOpacity(0.12)
              : Colors.black.withOpacity(0.06),
          width: 1,
        ),
        boxShadow: [
          BoxShadow(
            color: Colors.black.withOpacity(isDark ? 0.45 : 0.15),
            blurRadius: 24,
            offset: const Offset(0, 8),
          ),
        ],
      ),
      child: ClipRRect(
        borderRadius: BorderRadius.circular(20),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            _MenuItem(
              isDark: isDark,
              label: 'User Info',
              icon: Icons.person_outline,
              onTap: onUserInfo,
              showDivider: true,
            ),
            _MenuItem(
              isDark: isDark,
              label: 'Application Settings',
              icon: Icons.settings_outlined,
              onTap: onSettings,
              showDivider: true,
            ),
            _MenuItem(
              isDark: isDark,
              label: 'TopoCrack',
              icon: null, // nello screenshot non ha icona a sinistra
              onTap: onTopoCrack,
              showDivider: false,
            ),
          ],
        ),
      ),
    );
  }
}

class _MenuItem extends StatelessWidget {
  final bool isDark;
  final String label;
  final IconData? icon;
  final VoidCallback onTap;
  final bool showDivider;

  const _MenuItem({
    required this.isDark,
    required this.label,
    required this.icon,
    required this.onTap,
    required this.showDivider,
  });

  @override
  Widget build(BuildContext context) {
    final textColor = isDark ? Colors.white : Colors.black87;
    final dividerColor = isDark
        ? Colors.white.withOpacity(0.10)
        : Colors.black.withOpacity(0.08);

    return Column(
      children: [
        InkWell(
          onTap: onTap,
          splashColor: Colors.white12,
          child: Padding(
            padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 16),
            child: Row(
              children: [
                // Icona sinistra (solo su alcune voci)
                if (icon != null) ...[
                  Icon(icon, size: 18, color: textColor),
                  const SizedBox(width: 12),
                ] else
                  const SizedBox(width: 30), // allineamento

                // Label
                Expanded(
                  child: Text(
                    label,
                    style: TextStyle(
                      fontSize: 15,
                      fontWeight: FontWeight.w500,
                      color: textColor,
                    ),
                  ),
                ),

                // Icona destra settings (solo su "Application Settings")
                if (label == 'Application Settings')
                  Icon(Icons.settings_outlined,
                      size: 16, color: textColor.withOpacity(0.5)),
              ],
            ),
          ),
        ),
        if (showDivider)
          Divider(height: 1, thickness: 1, color: dividerColor),
      ],
    );
  }
}
