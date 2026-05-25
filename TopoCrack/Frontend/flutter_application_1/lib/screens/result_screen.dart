import 'dart:io';
import 'package:flutter/material.dart';
import 'package:url_launcher/url_launcher.dart';
import 'crack_editor_screen.dart';

class ResultScreen extends StatefulWidget {
  final File imageFile;
  final CrackPoint startPoint;
  final CrackPoint endPoint;
  final double startLatitude;
  final double startLongitude;
  final double endLatitude;
  final double endLongitude;
  final String coastName;
  final String warning;

  const ResultScreen({
    super.key,
    required this.imageFile,
    required this.startPoint,
    required this.endPoint,
    required this.startLatitude,
    required this.startLongitude,
    required this.endLatitude,
    required this.endLongitude,
    required this.coastName,
    required this.warning,
  });

  @override
  State<ResultScreen> createState() => _ResultScreenState();
}

class _ResultScreenState extends State<ResultScreen> {
  double? _imageRatio;

  @override
  void initState() {
    super.initState();
    _getImageRatio();
  }

  void _getImageRatio() {
    final image = Image.file(widget.imageFile);
    image.image.resolve(const ImageConfiguration()).addListener(
      ImageStreamListener((ImageInfo info, bool _) {
        if (mounted) {
          setState(() {
            _imageRatio = info.image.width / info.image.height;
          });
        }
      }),
    );
  }

  /// Apre Google Maps centrato sul baricentro della crepa
  Future<void> _openMaps(BuildContext context) async {
    final latitude = (widget.startLatitude + widget.endLatitude) / 2;
    final longitude = (widget.startLongitude + widget.endLongitude) / 2;

    // URL per visualizzare il punto con un pin, senza navigazione
    final String urlString = 'https://www.google.com/maps/search/?api=1&query=$latitude,$longitude';

    final uri = Uri.parse(urlString);
    if (await canLaunchUrl(uri)) {
      await launchUrl(uri, mode: LaunchMode.externalApplication);
    } else {
      if (context.mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Impossibile aprire Maps')),
        );
      }
    }
  }





  @override
  Widget build(BuildContext context) {
    final isDark = Theme.of(context).brightness == Brightness.dark;

    return Scaffold(
      backgroundColor: isDark ? const Color(0xFF0D0D0D) : const Color(0xFFF5F5F5),
      body: Stack(
        children: [
          // ─── SFONDO SFUMATO ─────────────────────────────────────────────
          Positioned.fill(
            child: Image.asset(
              'assets/images/bg.jpg',
              fit: BoxFit.cover,
            ),
          ),
          Positioned.fill(
            child: Container(
              color: isDark
                  ? Colors.black.withOpacity(0.65)
                  : Colors.white.withOpacity(0.15),
            ),
          ),

          // ─── CONTENUTO ──────────────────────────────────────────────────
          SafeArea(
            child: Column(
              children: [
                // Header
                Padding(
                  padding:
                      const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
                  child: Row(
                    children: [
                      GestureDetector(
                        onTap: () => Navigator.of(context).pop(),
                        child: Container(
                          width: 40,
                          height: 40,
                          decoration: BoxDecoration(
                            color: isDark
                                ? Colors.black.withOpacity(0.55)
                                : Colors.white.withOpacity(0.75),
                            shape: BoxShape.circle,
                          ),
                          child: Icon(
                            Icons.arrow_back_ios_new,
                            size: 16,
                            color: isDark ? Colors.white : Colors.black87,
                          ),
                        ),
                      ),
                      const SizedBox(width: 12),
                      Expanded(
                        child: Text(
                          'Risultato Analisi',
                          style: TextStyle(
                            fontSize: 18,
                            fontWeight: FontWeight.w700,
                            color: Colors.white,
                            shadows: [
                              Shadow(
                                color: Colors.black.withOpacity(0.7),
                                blurRadius: 6,
                              ),
                            ],
                          ),
                        ),
                      ),
                    ],
                  ),
                ),

                const SizedBox(height: 12),

                // ─── ANTEPRIMA IMMAGINE CON PUNTI ───────────────────────
                Expanded(
                  flex: 3,
                  child: Padding(
                    padding: const EdgeInsets.symmetric(horizontal: 16),
                    child: Center(
                      child: ClipRRect(
                        borderRadius: BorderRadius.circular(20),
                        child: _imageRatio == null
                            ? const CircularProgressIndicator()
                            : AspectRatio(
                                aspectRatio: _imageRatio!,
                                child: Stack(
                                  fit: StackFit.expand,
                                  children: [
                                    Image.file(
                                      widget.imageFile,
                                      fit: BoxFit.fill,
                                    ),
                                    // Overlay con la linea della crepa
                                    CustomPaint(
                                      painter: _ResultLinePainter(
                                        start: widget.startPoint.position,
                                        end: widget.endPoint.position,
                                      ),
                                    ),
                                  ],
                                ),
                              ),
                      ),
                    ),
                  ),
                ),

                const SizedBox(height: 20),

                // ─── CARD RISULTATO ──────────────────────────────────────
                Expanded(
                  flex: 2,
                  child: Padding(
                    padding: const EdgeInsets.symmetric(horizontal: 16),
                    child: Container(
                      width: double.infinity,
                      padding: const EdgeInsets.all(20),
                      decoration: BoxDecoration(
                        color: isDark
                            ? Colors.white.withOpacity(0.10)
                            : Colors.white.withOpacity(0.82),
                        borderRadius: BorderRadius.circular(24),
                        border: Border.all(
                          color: isDark
                              ? Colors.white.withOpacity(0.15)
                              : Colors.black.withOpacity(0.08),
                        ),
                      ),
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          // ─ Label ─
                          Text(
                            'Costa Corrispondente',
                            style: TextStyle(
                              fontSize: 12,
                              fontWeight: FontWeight.w600,
                              color: isDark
                                  ? Colors.white54
                                  : Colors.black45,
                              letterSpacing: 1.2,
                            ),
                          ),
                          const SizedBox(height: 6),

                          // ─ Nome costa ─
                          Text(
                            widget.coastName,
                            style: TextStyle(
                              fontSize: 22,
                              fontWeight: FontWeight.w800,
                              color: isDark ? Colors.white : Colors.black87,
                            ),
                          ),
                          const SizedBox(height: 4),
                          Text(
                            'Warning: ${widget.warning}',
                            style: TextStyle(
                              fontSize: 15,
                              fontWeight: FontWeight.w800,
                              color: isDark ? Colors.white : Colors.black87,
                            ),
                          ),
                          const SizedBox(height: 2),

                          // ─ Coordinate ─
                          Text(
                            'Inizio: ${widget.startLatitude.toStringAsFixed(4)}°N  ${widget.startLongitude.toStringAsFixed(4)}°E',
                            style: TextStyle(
                              fontSize: 13,
                              color: isDark ? Colors.white54 : Colors.black45,
                              fontFeatures: const [FontFeature.tabularFigures()],
                            ),
                          ),
                          Text(
                            'Fine: ${widget.endLatitude.toStringAsFixed(4)}°N  ${widget.endLongitude.toStringAsFixed(4)}°E',
                            style: TextStyle(
                              fontSize: 13,
                              color: isDark ? Colors.white54 : Colors.black45,
                              fontFeatures: const [FontFeature.tabularFigures()],
                            ),
                          ),

                          const Spacer(),

                          // ─ Bottone Apri Maps ─
                          GestureDetector(
                            onTap: () => _openMaps(context),
                            child: Container(
                              width: double.infinity,
                              height: 50,
                              decoration: BoxDecoration(
                                color: isDark
                                    ? Colors.white.withOpacity(0.9)
                                    : Colors.black.withOpacity(0.85),
                                borderRadius: BorderRadius.circular(16),
                              ),
                              child: Row(
                                mainAxisAlignment: MainAxisAlignment.center,
                                children: [
                                  Icon(
                                    Icons.map_outlined,
                                    color: isDark ? Colors.black : Colors.white,
                                    size: 18,
                                  ),
                                  const SizedBox(width: 10),
                                  Text(
                                    'Vedi sulla mappa',
                                    style: TextStyle(
                                      color: isDark ? Colors.black : Colors.white,
                                      fontSize: 14,
                                      fontWeight: FontWeight.w600,
                                      letterSpacing: 0.3,
                                    ),
                                  ),
                                ],
                              ),
                            ),
                          ),
                        ],
                      ),
                    ),
                  ),
                ),

                const SizedBox(height: 24),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

class _ResultLinePainter extends CustomPainter {
  final Offset start;
  final Offset end;

  _ResultLinePainter({required this.start, required this.end});

  @override
  void paint(Canvas canvas, Size size) {
    final startPx = Offset(start.dx * size.width, start.dy * size.height);
    final endPx = Offset(end.dx * size.width, end.dy * size.height);

    final paint = Paint()
      ..color =  Colors.white.withOpacity(0.9)
      ..strokeWidth = 2.5
      ..strokeCap = StrokeCap.round
      ..style = PaintingStyle.stroke;

    canvas.drawLine(startPx, endPx, paint);

    // Dot start
    canvas.drawCircle(
      startPx,
      4,
      Paint()
        ..color = const Color(0xFF00E5AA)
        ..style = PaintingStyle.fill,
    );
    // Dot end
    canvas.drawCircle(
      endPx,
      4,
      Paint()
        ..color = const Color(0xFFFF6B6B)
        ..style = PaintingStyle.fill,
    );
  }

  @override
  bool shouldRepaint(_ResultLinePainter old) =>
      old.start != start || old.end != end;
}
