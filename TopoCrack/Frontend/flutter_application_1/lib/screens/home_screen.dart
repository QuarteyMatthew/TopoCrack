import 'dart:io';
import 'package:flutter/material.dart';
import 'package:image_picker/image_picker.dart';
import '../widgets/top_bar.dart';
import '../widgets/bottom_bar.dart';
import '../widgets/user_menu.dart';
import 'crack_editor_screen.dart';

class HomeScreen extends StatefulWidget {
  final VoidCallback onToggleTheme;
  final ThemeMode themeMode;

  const HomeScreen({
    super.key,
    required this.onToggleTheme,
    required this.themeMode,
  });

  @override
  State<HomeScreen> createState() => _HomeScreenState();
}

class _HomeScreenState extends State<HomeScreen>
    with SingleTickerProviderStateMixin {
  final ImagePicker _picker = ImagePicker();
  bool _showUserMenu = false;
  late AnimationController _menuAnimController;
  late Animation<double> _menuFadeAnim;
  late Animation<Offset> _menuSlideAnim;

  @override
  void initState() {
    super.initState();
    _menuAnimController = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 220),
    );
    _menuFadeAnim = CurvedAnimation(
      parent: _menuAnimController,
      curve: Curves.easeOut,
    );
    _menuSlideAnim = Tween<Offset>(
      begin: const Offset(0.1, -0.05),
      end: Offset.zero,
    ).animate(CurvedAnimation(
      parent: _menuAnimController,
      curve: Curves.easeOut,
    ));
  }

  @override
  void dispose() {
    _menuAnimController.dispose();
    super.dispose();
  }

  void _toggleUserMenu() {
    setState(() {
      _showUserMenu = !_showUserMenu;
      if (_showUserMenu) {
        _menuAnimController.forward();
      } else {
        _menuAnimController.reverse();
      }
    });
  }

  void _closeMenu() {
    if (_showUserMenu) {
      setState(() {
        _showUserMenu = false;
        _menuAnimController.reverse();
      });
    }
  }

  /// Apre la galleria e naviga all'editor
  Future<void> _pickFromGallery() async {
    _closeMenu();
    final XFile? image = await _picker.pickImage(
      source: ImageSource.gallery,
      imageQuality: 95,
    );
    if (image != null && mounted) {
      _navigateToEditor(File(image.path));
    }
  }

  /// Scatta una foto con la camera e naviga all'editor
  Future<void> _takePhoto() async {
    _closeMenu();
    final XFile? image = await _picker.pickImage(
      source: ImageSource.camera,
      imageQuality: 95,
    );
    if (image != null && mounted) {
      _navigateToEditor(File(image.path));
    }
  }

  void _navigateToEditor(File imageFile) {
    Navigator.of(context).push(
      MaterialPageRoute(
        builder: (_) => CrackEditorScreen(imageFile: imageFile),
      ),
    );
  }

  bool get _isDark =>
      widget.themeMode == ThemeMode.dark ||
      (widget.themeMode == ThemeMode.system &&
          MediaQuery.platformBrightnessOf(context) == Brightness.dark);

  @override
  Widget build(BuildContext context) {
    final isDark = _isDark;

    return GestureDetector(
      onTap: _closeMenu,
      child: Scaffold(
        extendBodyBehindAppBar: true,
        body: Stack(
          fit: StackFit.expand,
          children: [
            // ─── SFONDO ───────────────────────────────────────────────────
            Image.asset(
              'assets/images/bg.jpg',
              fit: BoxFit.cover,
            ),

            // ─── OVERLAY colore tema ──────────────────────────────────────
            AnimatedContainer(
              duration: const Duration(milliseconds: 350),
              color: isDark
                  ? Colors.black.withOpacity(0.35)
                  : Colors.white.withOpacity(0.08),
            ),

            // ─── LINEA ORIZZONTALE CENTRALE (separatore crepa/costa) ──────
            // qui devo fare... aggiungere la logica di visualizzazione della
            // linea che divide crepa da costa una volta che l'utente seleziona
            // la foto e torna alla home
            Center(
              child: Container(
                height: 1,
                width: double.infinity,
                color: isDark
                    ? Colors.white.withOpacity(0.35)
                    : Colors.white.withOpacity(0.55),
                margin: const EdgeInsets.symmetric(horizontal: 0),
              ),
            ),

            // ─── ICONA FOLDER CENTRALE ────────────────────────────────────
            Center(
              child: Icon(
                Icons.folder,
                size: 40,
                color: Colors.white.withOpacity(0.75),
              ),
            ),

            // ─── TOP BAR ──────────────────────────────────────────────────
            Positioned(
              top: 0,
              left: 0,
              right: 0,
              child: SafeArea(
                child: TopBar(
                  isDark: isDark,
                  showUserMenu: _showUserMenu,
                  onFolderTap: _pickFromGallery,
                  onProfileTap: _toggleUserMenu,
                  onMinusTap: () {
                    // qui devo fare... implementare la funzione di "rimuovi sessione"
                    // o minimizza la vista corrente
                  },
                ),
              ),
            ),

            // ─── BOTTOM BAR ───────────────────────────────────────────────
            Positioned(
              left: 0,
              right: 0,
              bottom: 0,
              child: SafeArea(
                child: BottomBar(
                  isDark: isDark,
                  onBookmarkTap: () {
                    // qui devo fare... aprire la lista delle sessioni salvate
                  },
                  onCameraTap: _takePhoto,
                  onGalleryTap: _pickFromGallery,
                ),
              ),
            ),

            // ─── MENU UTENTE (dropdown) ───────────────────────────────────
            if (_showUserMenu)
              Positioned(
                top: MediaQuery.of(context).padding.top + 56,
                right: 12,
                child: FadeTransition(
                  opacity: _menuFadeAnim,
                  child: SlideTransition(
                    position: _menuSlideAnim,
                    child: UserMenu(
                      isDark: isDark,
                      onUserInfo: () {
                        _closeMenu();
                        // qui devo fare... navigare alla schermata info utente
                      },
                      onSettings: () {
                        _closeMenu();
                        // qui devo fare... navigare alle impostazioni app
                      },
                      onTopoCrack: () {
                        _closeMenu();
                        // qui devo fare... mostrare info su TopoCrack / about
                      },
                    ),
                  ),
                ),
              ),
          ],
        ),
      ),
    );
  }
}
