import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

void main() {
  WidgetsFlutterBinding.ensureInitialized();
  SystemChrome.setSystemUIOverlayStyle(
    const SystemUiOverlayStyle(
      statusBarColor: Colors.transparent,
      statusBarIconBrightness: Brightness.light,
    ),
  );
  runApp(const MyApp());
}

class MyApp extends StatelessWidget {
  const MyApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'GeoShare',
      debugShowCheckedModeBanner: false,
      theme: ThemeData.dark(),
      home: const HomeScreen(),
    );
  }
}



// ─────────────────────────────────────────────
// HOME SCREEN
// ─────────────────────────────────────────────

class HomeScreen extends StatefulWidget {
  const HomeScreen({super.key});

  @override
  State<HomeScreen> createState() => _HomeScreenState();
}

class _HomeScreenState extends State<HomeScreen> {
  int _selectedTab = 1; // 0=bookmarks, 1=camera, 2=gallery

  void _onTabTap(int index) {
    setState(() => _selectedTab = index);
    // TODO: implementa la navigazione per ogni tab
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      extendBodyBehindAppBar: true,
      body: Stack(
        fit: StackFit.expand,
        children: [
          // ── 1. BACKGROUND IMAGE ──────────────────────
          _BackgroundImage(),

          // ── 2. DARK OVERLAY (leggero) ────────────────
          //Container(color: Colors.black.withOpacity(0.18)),

          // ── 3. TOP BAR ───────────────────────────────
          const _TopBar(),

          // ── 4. BOTTOM NAV BAR ────────────────────────
          Align(
            alignment: Alignment.bottomCenter,
            child: _BottomNavBar(
              selectedIndex: _selectedTab,
              onTap: _onTabTap,
            ),
          ),
        ],
      ),
    );
  }
}

// ─────────────────────────────────────────────
// BACKGROUND IMAGE
// ─────────────────────────────────────────────

class _BackgroundImage extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    return SizedBox.expand(
      child: Image.asset(
        'assets/bg.jpg',
        fit: BoxFit.cover,
      ),
    );
  }
}

// ─────────────────────────────────────────────
// TOP BAR
// ─────────────────────────────────────────────

class _TopBar extends StatelessWidget {
  const _TopBar();

  @override
  Widget build(BuildContext context) {
    final top = MediaQuery.of(context).padding.top;
    return Positioned(
      top: top + 8,
      left: 16,
      right: 16,
      child: Row(
        mainAxisAlignment: MainAxisAlignment.spaceBetween,
        children: [
          // Folder / menu icon
          _TopIconButton(
            icon: Icons.folder_rounded,
            onTap: () {
              // TODO: apri cartella / menu
            },
          ),
          // Profile icon
          _TopIconButton(
            icon: Icons.settings_rounded,
            //togliere lo sfondo dalle icone
            onTap: () {
              // TODO: apri menu
            },
          ),
        ],
      ),
    );
  }
}

class _TopIconButton extends StatelessWidget {
  final IconData icon;
  final VoidCallback onTap;

  const _TopIconButton({required this.icon, required this.onTap});

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTap: onTap,
      child: Container(
        width: 40,
        height: 40,
        decoration: BoxDecoration(
          color: Colors.black.withOpacity(0.35),
          borderRadius: BorderRadius.circular(12),
        ),
        child: Icon(icon, color: Colors.white, size: 22),
      ),
    );
  }
}

// ─────────────────────────────────────────────
// BOTTOM NAV BAR
// ─────────────────────────────────────────────

class _BottomNavBar extends StatelessWidget {
  final int selectedIndex;
  final ValueChanged<int> onTap;

  const _BottomNavBar({
    required this.selectedIndex,
    required this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    final bottom = MediaQuery.of(context).padding.bottom;
    return Padding(
      padding: EdgeInsets.only(bottom: bottom + 24, left: 40, right: 40),
      child: Container(
        height: 72,
        decoration: BoxDecoration(
          color: Colors.black.withOpacity(0.55),
          borderRadius: BorderRadius.circular(36),
          border: Border.all(
            color: Colors.white.withOpacity(0.12),
            width: 1,
          ),
          boxShadow: [
            BoxShadow(
              color: Colors.black.withOpacity(0.4),
              blurRadius: 20,
              offset: const Offset(0, 8),
            ),
          ],
        ),
        child: Row(
          mainAxisAlignment: MainAxisAlignment.spaceEvenly,
          children: [
            // ── Bookmarks ──
            _NavItem(
              icon: Icons.bookmark_border_rounded,
              iconSelected: Icons.bookmark_rounded,
              isSelected: selectedIndex == 0,
              isCenter: false,
              onTap: () => onTap(0),
            ),
            // ── Camera (center, elevated) ──
            _NavItem(
              icon: Icons.camera_alt_outlined,
              iconSelected: Icons.camera_alt_rounded,
              isSelected: selectedIndex == 1,
              isCenter: true,
              onTap: () => onTap(1),
            ),
            // ── Gallery ──
            _NavItem(
              icon: Icons.image_outlined,
              iconSelected: Icons.image_rounded,
              isSelected: selectedIndex == 2,
              isCenter: false,
              onTap: () => onTap(2),
            ),
          ],
        ),
      ),
    );
  }
}

class _NavItem extends StatelessWidget {
  final IconData icon;
  final IconData iconSelected;
  final bool isSelected;
  final bool isCenter;
  final VoidCallback onTap;

  const _NavItem({
    required this.icon,
    required this.iconSelected,
    required this.isSelected,
    required this.isCenter,
    required this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    if (isCenter) {
      return GestureDetector(
        onTap: onTap,
        child: AnimatedContainer(
          duration: const Duration(milliseconds: 250),
          curve: Curves.easeOutBack,
          width: 56,
          height: 56,
          decoration: BoxDecoration(
            shape: BoxShape.circle,
            color: isSelected ? Colors.white : const Color(0xFF2A2A2A),
            boxShadow: [
              BoxShadow(
                color: Colors.black.withOpacity(0.5),
                blurRadius: 12,
                offset: const Offset(0, 4),
              ),
            ],
          ),
          child: Icon(
            isSelected ? iconSelected : icon,
            color: isSelected ? Colors.black : Colors.white,
            size: 26,
          ),
        ),
      );
    }

    return GestureDetector(
      onTap: onTap,
      child: AnimatedScale(
        scale: isSelected ? 1.15 : 1.0,
        duration: const Duration(milliseconds: 200),
        child: Icon(
          isSelected ? iconSelected : icon,
          color: isSelected ? Colors.white : Colors.white54,
          size: 26,
        ),
      ),
    );
  }
}