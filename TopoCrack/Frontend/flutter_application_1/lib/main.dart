import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'screens/home_screen.dart';

void main() {
  WidgetsFlutterBinding.ensureInitialized();

  // Forza orientamento portrait
  SystemChrome.setPreferredOrientations([
    DeviceOrientation.portraitUp,
    DeviceOrientation.portraitDown,
  ]);

  runApp(const TopoCrackApp());
}

class TopoCrackApp extends StatefulWidget {
  const TopoCrackApp({super.key});

  @override
  State<TopoCrackApp> createState() => _TopoCrackAppState();
}

class _TopoCrackAppState extends State<TopoCrackApp> {
  ThemeMode _themeMode = ThemeMode.system;

  void toggleTheme() {
    setState(() {
      _themeMode =
          _themeMode == ThemeMode.dark ? ThemeMode.light : ThemeMode.dark;
    });
  }

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'TopoCrack',
      debugShowCheckedModeBanner: false,
      themeMode: _themeMode,

      // ─── TEMA CHIARO ────────────────────────────────────────────────────
      theme: ThemeData(
        brightness: Brightness.light,
        useMaterial3: true,
        colorScheme: ColorScheme.fromSeed(
          seedColor: const Color(0xFF2C5F6E),
          brightness: Brightness.light,
        ),
        scaffoldBackgroundColor: Colors.transparent,
        fontFamily: 'SF Pro Display',
      ),

      // ─── TEMA SCURO ─────────────────────────────────────────────────────
      darkTheme: ThemeData(
        brightness: Brightness.dark,
        useMaterial3: true,
        colorScheme: ColorScheme.fromSeed(
          seedColor: const Color(0xFF2C5F6E),
          brightness: Brightness.dark,
        ),
        scaffoldBackgroundColor: Colors.transparent,
        fontFamily: 'SF Pro Display',
      ),

      home: HomeScreen(onToggleTheme: toggleTheme, themeMode: _themeMode),
    );
  }
}
