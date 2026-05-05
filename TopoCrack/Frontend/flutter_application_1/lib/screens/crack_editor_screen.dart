import 'dart:io';
import 'dart:convert';
import 'package:flutter/material.dart';
import 'package:http/http.dart' as http;
import 'result_screen.dart';

/// Modello per un punto selezionato sull'immagine
class CrackPoint {
  final Offset position; // posizione relativa (0.0 – 1.0)
  CrackPoint(this.position);
}

class CrackEditorScreen extends StatefulWidget {
  final File imageFile;

  const CrackEditorScreen({super.key, required this.imageFile});

  @override
  State<CrackEditorScreen> createState() => _CrackEditorScreenState();
}

class _CrackEditorScreenState extends State<CrackEditorScreen>
    with SingleTickerProviderStateMixin {
  CrackPoint? _startPoint;
  CrackPoint? _endPoint;
  final GlobalKey _imageKey = GlobalKey();
  late AnimationController _pulseController;
  late Animation<double> _pulseAnim;
  bool _isLoading = false;

  // Indica quale punto stiamo aspettando: 0 = start, 1 = end
  int _currentStep = 0;

  @override
  void initState() {
    super.initState();
    _pulseController = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 900),
    )..repeat(reverse: true);
    _pulseAnim = Tween<double>(begin: 0.85, end: 1.15).animate(
      CurvedAnimation(parent: _pulseController, curve: Curves.easeInOut),
    );
  }

  @override
  void dispose() {
    _pulseController.dispose();
    super.dispose();
  }

  /// Converte un tap in posizione relativa rispetto all'immagine renderizzata
  Offset? _toRelativePosition(TapDownDetails details) {
    final RenderBox? box =
    _imageKey.currentContext?.findRenderObject() as RenderBox?;
    if (box == null) return null;
    final localPos = box.globalToLocal(details.globalPosition);
    final size = box.size;
    return Offset(
      (localPos.dx / size.width).clamp(0.0, 1.0),
      (localPos.dy / size.height).clamp(0.0, 1.0),
    );
  }

  void _onImageTap(TapDownDetails details) {
    final rel = _toRelativePosition(details);
    if (rel == null) return;

    setState(() {
      if (_currentStep == 0) {
        _startPoint = CrackPoint(rel);
        _currentStep = 1;
      } else {
        _endPoint = CrackPoint(rel);
        _currentStep = 2; // entrambi selezionati
      }
    });
  }

  void _resetPoints() {
    setState(() {
      _startPoint = null;
      _endPoint = null;
      _currentStep = 0;
    });
  }

  Future<void> _confirmAndSend() async {
    if (_startPoint == null || _endPoint == null) return;

    setState(() => _isLoading = true);

    try {
      // l'URL reale de server
      final uri = Uri.parse('http://10.0.2.2:5000/analyze'); 
      final request = http.MultipartRequest('POST', uri);

      // Immagine
      request.files.add(await http.MultipartFile.fromPath('file', widget.imageFile.path));

      // I due punti come campi form (coordinate relative 0.0 - 1.0)
      request.fields['x1'] = _startPoint!.position.dx.toString();
      request.fields['y1'] = _startPoint!.position.dy.toString();
      request.fields['x2'] = _endPoint!.position.dx.toString();
      request.fields['y2'] = _endPoint!.position.dy.toString();

      final response = await request.send();

      if (response.statusCode == 200) {
        final bodyText = await response.stream.bytesToString();
        final body = jsonDecode(bodyText);

        if (mounted) {
          Navigator.of(context).push(
            MaterialPageRoute(
              builder: (_) => ResultScreen(
                imageFile: widget.imageFile,
                startPoint: _startPoint!,
                endPoint: _endPoint!,
                latitude: (body['lat_start'] as num?)?.toDouble() ?? 39.7157,
                longitude: (body['lon_start'] as num?)?.toDouble() ?? 2.9681,
                coastName: body['coast_name'] ?? 'Località rilevata',
              ),
            ),
          );
        }
      } else {
        throw Exception('Errore server: ${response.statusCode}');
      }
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Errore: $e')),
        );
      }
    } finally {
      if (mounted) setState(() => _isLoading = false);
    }
  }

  String get _instructionText {
    switch (_currentStep) {
      case 0:
        return 'Punto A';
      case 1:
        return 'Punto B';
      case 2:
        return 'Analisi';
      default:
        return '';
    }
  }

  @override
  Widget build(BuildContext context) {
    final isDark = Theme.of(context).brightness == Brightness.dark;

    return Scaffold(
      backgroundColor: Colors.black,
      body: SafeArea(
        child: Column(
          children: [
            // ─── TOP HEADER ─────────────────────────────────────────
            Padding(
              padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
              child: Row(
                children: [
                  // Pulsante indietro
                  GestureDetector(
                    onTap: () => Navigator.of(context).pop(),
                    child: Container(
                      width: 40,
                      height: 40,
                      decoration: BoxDecoration(
                        color: isDark
                            ? Colors.black.withOpacity(0.55)
                            : Colors.white.withOpacity(0.7),
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
                  // Titolo
                  Expanded(
                    child: Text(
                      'Seleziona Crepa',
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
                  // Reset
                  if (_startPoint != null)
                    GestureDetector(
                      onTap: _resetPoints,
                      child: Container(
                        width: 40,
                        height: 40,
                        decoration: BoxDecoration(
                          color: Colors.black.withOpacity(0.5),
                          shape: BoxShape.circle,
                        ),
                        child: const Icon(
                          Icons.refresh,
                          size: 18,
                          color: Colors.white,
                        ),
                      ),
                    ),
                ],
              ),
            ),

            // ─── AREA EDITOR (Centrata e con BoxFit.contain) ────────────────
            Expanded(
              child: Center(
                child: Padding(
                  padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
                  child: GestureDetector(
                    onTapDown: _currentStep < 2 ? _onImageTap : null,
                    child: LayoutBuilder(
                      builder: (context, constraints) {
                        return Stack(
                          alignment: Alignment.center,
                          children: [
                            // Immagine con BoxFit.contain per vedere tutto
                            Image.file(
                              widget.imageFile,
                              key: _imageKey,
                              fit: BoxFit.contain,
                            ),

                            // Overlay scuro leggero sull'immagine
                            Positioned.fill(
                              child: Container(
                                color: Colors.black.withOpacity(0.15),
                              ),
                            ),

                            // Linea tra i due punti
                            if (_startPoint != null && _endPoint != null)
                              Positioned.fill(
                                child: CustomPaint(
                                  painter: _CrackLinePainter(
                                    start: _startPoint!.position,
                                    end: _endPoint!.position,
                                  ),
                                ),
                              ),

                            // Punto START
                            if (_startPoint != null)
                              _buildDot(
                                context,
                                _startPoint!.position,
                                const Color(0xFF00E5AA),
                                'A',
                              ),

                            // Punto END
                            if (_endPoint != null)
                              _buildDot(
                                context,
                                _endPoint!.position,
                                const Color(0xFFFF6B6B),
                                'B',
                              ),
                          ],
                        );
                      },
                    ),
                  ),
                ),
              ),
            ),

            // ─── ISTRUZIONE BOTTOM ──────────────────────────────────
            Padding(
              padding: const EdgeInsets.only(bottom: 24, top: 16),
              child: Column(
                children: [
                  // Testo istruzione
                  AnimatedSwitcher(
                    duration: const Duration(milliseconds: 300),
                    child: Text(
                      _instructionText.toUpperCase(),
                      key: ValueKey(_instructionText),
                      style: TextStyle(
                        color: Colors.white.withOpacity(0.8),
                        fontSize: 12,
                        fontWeight: FontWeight.w700,
                        letterSpacing: 1.5,
                      ),
                    ),
                  ),
                  const SizedBox(height: 20),

                  // Bottone Minimal
                  AnimatedOpacity(
                    opacity: _currentStep == 2 ? 1.0 : 0.0,
                    duration: const Duration(milliseconds: 300),
                    child: GestureDetector(
                      onTap: (_currentStep == 2 && !_isLoading) ? _confirmAndSend : null,
                      child: Container(
                        width: 140,
                        height: 44,
                        decoration: BoxDecoration(
                          color: Colors.white.withOpacity(0.95),
                          borderRadius: BorderRadius.circular(22),
                        ),
                        child: Center(
                          child: _isLoading
                              ? const SizedBox(
                                  width: 20,
                                  height: 20,
                                  child: CircularProgressIndicator(
                                    strokeWidth: 2,
                                    color: Colors.black,
                                  ),
                                )
                              : const Text(
                                  'OK',
                                  style: TextStyle(
                                    color: Colors.black,
                                    fontSize: 13,
                                    fontWeight: FontWeight.w900,
                                  ),
                                ),
                        ),
                      ),
                    ),
                  ),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }


  /// Costruisce un punto PIN animato sull'immagine
  Widget _buildDot(
      BuildContext context, Offset rel, Color color, String label) {
    return LayoutBuilder(
      builder: (ctx, constraints) {
        final x = rel.dx * constraints.maxWidth;
        final y = rel.dy * constraints.maxHeight;
        return Positioned(
          left: x - 18,
          top: y - 18,
          child: ScaleTransition(
            scale: _pulseAnim,
            child: Container(
              width: 36,
              height: 36,
              decoration: BoxDecoration(
                color: color,
                shape: BoxShape.circle,
                border: Border.all(color: Colors.white, width: 2.5),
                boxShadow: [
                  BoxShadow(
                    color: color.withOpacity(0.55),
                    blurRadius: 12,
                    spreadRadius: 2,
                  ),
                ],
              ),
              child: Center(
                child: Text(
                  label,
                  style: const TextStyle(
                    color: Colors.white,
                    fontWeight: FontWeight.w800,
                    fontSize: 14,
                  ),
                ),
              ),
            ),
          ),
        );
      },
    );
  }
}

/// CustomPainter che disegna la linea tra i due punti della crepa
class _CrackLinePainter extends CustomPainter {
  final Offset start;
  final Offset end;

  _CrackLinePainter({required this.start, required this.end});

  @override
  void paint(Canvas canvas, Size size) {
    final paint = Paint()
      ..color = Colors.white.withOpacity(0.85)
      ..strokeWidth = 2.5
      ..style = PaintingStyle.stroke
      ..strokeCap = StrokeCap.round;

    // Linea tratteggiata tra i due punti
    final dashPaint = Paint()
      ..color = const Color(0xFF00E5AA).withOpacity(0.9)
      ..strokeWidth = 2.0
      ..style = PaintingStyle.stroke
      ..strokeCap = StrokeCap.round;

    final startPx = Offset(start.dx * size.width, start.dy * size.height);
    final endPx = Offset(end.dx * size.width, end.dy * size.height);

    // Disegna linea piena
    canvas.drawLine(startPx, endPx, paint);

    // Disegna linea tratteggiata sovrapposta
    _drawDashedLine(canvas, startPx, endPx, dashPaint, 10, 6);
  }

  void _drawDashedLine(Canvas canvas, Offset start, Offset end, Paint paint,
      double dashLength, double gapLength) {
    final distance = (end - start).distance;
    if (distance == 0) return;
    final direction = (end - start) / distance;
    double traveled = 0;
    bool drawing = true;

    while (traveled < distance) {
      final segmentLength =
      drawing ? dashLength : gapLength;
      final remaining = distance - traveled;
      final segEnd = traveled + (segmentLength > remaining ? remaining : segmentLength);

      if (drawing) {
        canvas.drawLine(
          start + direction * traveled,
          start + direction * segEnd,
          paint,
        );
      }
      traveled = segEnd;
      drawing = !drawing;
    }
  }

  @override
  bool shouldRepaint(_CrackLinePainter old) =>
      old.start != start || old.end != end;
}
