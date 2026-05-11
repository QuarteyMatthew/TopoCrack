import math
import time
import numpy
import logging
import matplotlib.pyplot as pyplot

import sys
import ctypes

from pathlib import Path
from joblib import Parallel, delayed

logger = logging.getLogger(__name__)

# Path per la Native directory
_libraryDir = Path(__file__).parent / "Native" / "Build" / "Libraries"

# Mappa piattaforma: esetensione del file della shared library
_libExtensions = {
    "win32": "DtwCore.dll",
    "darwin": "DtwCore.dylib",
}

# Scelta del nome della shared library in base alla piattaforma; per Linux
# e per sistemi simili l'estensione di default è .so
_libName = _libExtensions.get(sys.platform, "DtwCore.so")
_libPath = _libraryDir / _libName

#  Errore se non esiste il path alla shared library
if not _libPath.exists():
    logger.critical(
        f"Native DTW library not found at '{_libPath}'.\n"
        f"Run 'python Scripts/BuildNative.py' from the Backend directory to compile it."
    )
    raise FileNotFoundError(f"'{_libPath}' not found")

# Carica la libreria C per il DTW 2D
_lib = ctypes.CDLL(str(_libPath))

# Dichiara la firma della funzione
_lib.DtwCost2D.restype = ctypes.c_double
_lib.DtwCost2D.argtypes = [
    ctypes.POINTER(ctypes.c_double), ctypes.c_int,
    ctypes.POINTER(ctypes.c_double), ctypes.c_int,
]

class DtwService:

    @staticmethod
    def FindBestMatch(crackPoints: numpy.ndarray, coastalData: list) -> dict:
        """
        Restituisce la sezione costiera con il DTW score più basso.
        """
        
        logger.info("FindBestMatch called with %d crack points and %d coastal sections.", len(crackPoints), len(coastalData))
        
        # ------------- 1. Preparazione dei punti -------------
        preparedCrackPoints = DtwService._PreparePoints(crackPoints)
        logger.debug(
            "Crack points prepared: start=(%.3f, %.3f), end=(%.3f, %.3f). "
            "x range=[%.3f, %.3f], y range=[%.3f, %.3f].",
            preparedCrackPoints[0, 0],  preparedCrackPoints[0, 1],
            preparedCrackPoints[-1, 0], preparedCrackPoints[-1, 1],
            float(preparedCrackPoints[:, 0].min()), float(preparedCrackPoints[:, 0].max()),
            float(preparedCrackPoints[:, 1].min()), float(preparedCrackPoints[:, 1].max()),
        )
        
        # ------------- 2. DTW parallelo -------------
        validSections = [s for s in coastalData if s["points"] is not None]
        skippedSections = len(coastalData) - len(validSections)

        if skippedSections > 0:
            logger.warning(
                "%d coastal sections skipped (points=None). "
                "%d valid sections will be compared.",
                skippedSections, len(validSections),
            )
        else:
            logger.info("All %d coastal sections are valid. Starting parallel DTW...", len(validSections))

        # Misuriamo il tempo totale del DTW: è la parte più lenta dell'intera
        # pipeline e il suo monitoraggio è fondamentale per valutare la scalabilità.
        dtwStartTime = time.perf_counter()

        results = Parallel(n_jobs=-1, prefer="threads")(
            delayed(DtwService._ComputeCost)(preparedCrackPoints, section)
            for section in validSections
        )

        dtwElapsed = time.perf_counter() - dtwStartTime

        logger.info(
            "Parallel DTW complete: %d comparisons in %.2f seconds (%.1f comparisons/sec).",
            len(results), dtwElapsed, len(results) / max(dtwElapsed, 1e-9)
        )
        
        # ------------- 3. Best match -------------
        # Trova il profilo costiero con il cost più basso
        bestMatch  = min(results, key=lambda r: r["cost"])
        worstMatch = max(results, key=lambda r: r["cost"])
        
        logger.info(
            "Best match:  featureIndex=%s, sectionIndex=%s, cost=%.6f. "
            "Worst match: cost=%.6f. Score range: %.6f.",
            bestMatch["featureIndex"], bestMatch["sectionIndex"], bestMatch["cost"],
            worstMatch["cost"], worstMatch["cost"] - bestMatch["cost"],
        )
        
        # Un range di score molto piccolo è un segnale di warning: significa
        # che tutti i profili costieri hanno punteggi simili, il che indica
        # che la crepa preparata potrebbe essere degenere (es. quasi piatta).
        scoreRange = worstMatch["cost"] - bestMatch["cost"]
        if scoreRange < 0.01:
            logger.warning(
                "Very small DTW score range (%.6f). The crack shape may be too simple "
                "or degenerate to discriminate between coastal profiles.",
                scoreRange,
            )
        
        # DtwService._Visualize(preparedCrackPoints, coastalData, bestMatch)

        return bestMatch
    
    @staticmethod
    def _ComputeCost(crackPoints: numpy.ndarray, section: dict) -> dict:
        # cost = DtwService._DtwCostPython(crackPoints, section["points"])
        cost = DtwService._DtwCostC(crackPoints, section["points"])
        return { **section, "cost": cost }
    
    @staticmethod
    def _PreparePoints(crackPoints: numpy.ndarray) -> numpy.ndarray:
        # -------- 1. Traslazione all'origine --------
        traslatedPoints = crackPoints - crackPoints[0]

        # -------- 2. Calcola la rotazione -------
        traslatedEnd = traslatedPoints[-1]

        # Calcola l'arcotangente
        angle = math.atan2(traslatedEnd[1], traslatedEnd[0])

        logger.debug("_PreparePoints: rotation angle=%.4f rad (%.1f deg).", angle, math.degrees(angle))
        
        # Matrice di rotazione
        cos, sin = numpy.cos(-angle), numpy.sin(-angle)
        rotationMatrix = numpy.array([[cos, -sin], [sin, cos]])

        # -------- 3. Applicazione della rotazione a tutti i punti -------
        rotatedPoints = numpy.dot(traslatedPoints, rotationMatrix.T)
    
        # -------- 4. Forza y=0 all'inizio e alla fine -------
        rotatedPoints[0, 1] = 0.0
        rotatedPoints[-1, 1] = 0.0
    
        # -------- 5. Scala uniformemente -------
        rotatedEnd = rotatedPoints[-1]

        if rotatedEnd[0] < 1e-10:
            logger.error(
                "_PreparePoints: degenerate crack — end point x=%.6f after rotation. "
                "The crack may be a single point or have zero horizontal extent.",
                float(rotatedEnd[0]),
            )
            raise ValueError("Degenerate crack points: zero horizontal extent after rotation.")


        i = 0
        for point in rotatedPoints:
            pointX = point[0]
            pointY = point[1]
            ratio = pointX / rotatedEnd[0]
            if pointX != 0:
                point = [ratio, ratio * pointY / pointX]
            
            rotatedPoints[i] = point
            i += 1

        return rotatedPoints
    
    @staticmethod
    def _DtwCostC(pointsA: numpy.ndarray, pointsB: numpy.ndarray) -> float:
        # numpy.ascontiguousarray garantisce che l'array sia in memoria contigua
        # (row-major, C-style): indispensabile per passarlo a C senza copie extra
        a = numpy.ascontiguousarray(pointsA, dtype=numpy.float64)
        b = numpy.ascontiguousarray(pointsB, dtype=numpy.float64)
        
        # Ottiene un puntatore grezzo all'inizio dell'array numpy senza copiare i dati
        pointerA = a.ctypes.data_as(ctypes.POINTER(ctypes.c_double))
        pointerB = b.ctypes.data_as(ctypes.POINTER(ctypes.c_double))
        
        # Chiamata alla funzione C. Tramite CDLL il GIL viene rilasciato
        # automaticamente 
        return _lib.DtwCost2D(pointerA, len(a), pointerB, len(b))
    
    @staticmethod
    def _DtwCostPython(pointsA: numpy.ndarray, pointsB: numpy.ndarray) -> float:
        n, m = len(pointsA), len(pointsB)
        costMatrix = numpy.full((n + 1, m + 1), numpy.inf, dtype=float)
        costMatrix[0, 0] = 0.0
        
        for i in range(1, n + 1):
            for j in range(1, m + 1):
                distance = numpy.linalg.norm(pointsA[i - 1] - pointsB[j - 1])
                costMatrix[i, j] = distance + min(
                    costMatrix[i - 1, j],    # Insertion
                    costMatrix[i, j - 1],    # deletion
                    costMatrix[i - 1, j - 1] # match
                )
        
        return float(costMatrix[n, m])
    
    @staticmethod
    def _Visualize(preparedCrackPoints: numpy.ndarray, coastalData: list, bestMatch: dict):
        _, axes = pyplot.subplots(figsize=(8, 6))
        axes.plot(preparedCrackPoints[:, 0], preparedCrackPoints[:, 1], label="User path", color="black", linewidth=2)
        
        bestCoastalData = next(
        (coast for coast in coastalData 
            if coast["featureIndex"] == bestMatch["featureIndex"] and coast["sectionIndex"] == bestMatch["sectionIndex"]),
            None
        )

        points = bestCoastalData["points"]
        axes.plot(points[:, 0], points[:, 1], label=f"{bestMatch['featureIndex']}_{bestMatch['sectionIndex']} ({bestMatch['cost']:.4f})")
        
        axes.set_aspect("equal", adjustable="box")
        axes.legend()
        axes.set_title("Best match")
        pyplot.show()