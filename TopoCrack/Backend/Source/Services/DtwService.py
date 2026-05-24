import math
import numpy
import logging
import matplotlib.pyplot as pyplot

import sys
import ctypes

from pathlib import Path

logger = logging.getLogger(__name__)

# ------------------ Linking DtwCore.dll ------------------
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
    ctypes.c_double,
]

class DtwService:

    @staticmethod
    def FindBestMatch(crackPoints: numpy.ndarray, coastalData: numpy.ndarray) -> tuple[dict, float]:
        # ------------- 1. Preparazione dei punti -------------
        # Prepara la crepa e la sua versione riflessa sull'asse x.
        preparedCrackPoints  = DtwService._PreparePoints(crackPoints)
        mirAndRevCrackPoints = DtwService._MirrorAndReverseCrackPoints(preparedCrackPoints)
        
        # Aggiungiamo il controllo di curvatura: un rapporto percorso/corda > 3
        # indica una crepa che si arrotola su se stessa e probabilmente non
        # troverà mai un buon match in nessuna coastline reale.
        pathLength     = float(numpy.sum(numpy.linalg.norm(numpy.diff(preparedCrackPoints, axis=0), axis=1)))
        chordLength    = float(preparedCrackPoints[-1, 0])  # = 1.0 dopo la scala
        curvatureRatio = pathLength / max(chordLength, 1e-10)
        if curvatureRatio > 3.0:
            logger.warning(
                "High curvature ratio (%.2f): the crack path is %.1fx longer than "
                "its chord. The DTW match may be unreliable — no coastline has "
                "this degree of self-folding. Consider re-selecting the crack endpoints.",
                curvatureRatio, curvatureRatio,
            )

        validWindows = [w for w in coastalData if w["points"] is not None]
        
        # ------------- 2. DTW parallelo -------------
        # Misuriamo il tempo totale del DTW: è la parte più lenta dell'intera
        # pipeline e il suo monitoraggio è fondamentale per valutare la scalabilità.
        bestCost = numpy.inf
        bestMatch = None
        
        for window in validWindows:
            normalCost  = DtwService._DtwCostC(preparedCrackPoints, window["points"], bestCost)
            rotatedCost = DtwService._DtwCostC(mirAndRevCrackPoints, window["points"], min(bestCost, normalCost))
            cost        = min(normalCost, rotatedCost)
            
            if cost < bestCost:
                bestCost  = cost
                bestMatch = { **window, "cost": cost }
        
        DtwService._Visualize(preparedCrackPoints, mirAndRevCrackPoints, bestMatch)

        return bestMatch, curvatureRatio
    
    @staticmethod
    def _PreparePoints(crackPoints: numpy.ndarray) -> numpy.ndarray:
        # -------- 1. Traslazione all'origine --------
        traslatedPoints = crackPoints - crackPoints[0]

        # -------- 2. Calcola la rotazione -------
        traslatedEnd = traslatedPoints[-1]
        angle = math.atan2(traslatedEnd[1], traslatedEnd[0]) # Calcola l'arcotangente
        cos, sin = numpy.cos(-angle), numpy.sin(-angle) # Matrice di rotazione
        rotationMatrix = numpy.array([[cos, -sin], [sin, cos]])

        # -------- 3. Applicazione della rotazione a tutti i punti -------
        rotatedPoints = numpy.dot(traslatedPoints, rotationMatrix.T)
    
        # -------- 4. Forza y = 0 all'inizio e alla fine -------
        rotatedPoints[0, 1] = 0.0
        rotatedPoints[-1, 1] = 0.0
    
        # -------- 5. Scala uniformemente -------
        rotatedEnd = rotatedPoints[-1]

        if rotatedEnd[0] < 1e-10:
            raise ValueError("Degenerate crack points: zero horizontal extent after rotation.")

        i = 0
        for point in rotatedPoints:
            pointX = point[0]
            pointY = point[1]
            ratio  = pointX / rotatedEnd[0]
            if pointX != 0:
                point = [ratio, ratio * pointY / pointX]
            
            rotatedPoints[i] = point
            i += 1

        return rotatedPoints

    @staticmethod
    def _MirrorAndReverseCrackPoints(preparedCrackPoints: numpy.ndarray) -> numpy.ndarray:
        nPoints = len(preparedCrackPoints)
        result  = numpy.empty((nPoints, 2))
        
        # Il valore xf è la coordinata X dell'ultimo punto dell'array originale
        xf = preparedCrackPoints[nPoints - 1][0]
        
        for i, point in enumerate(preparedCrackPoints):
            # 1. Calcola la nuova X traslata rispetto a xf
            newX = xf - point[0]
            
            # 2. Specchia la Y cambiando il segno
            newY = point[1] * -1.0
            
            # 3. Inverte l'ordine di inserimento: 
            # il primo punto originale (i = 0) va in fondo al nuovo array (nPoints - 1)
            result[nPoints - 1 - i] = numpy.array([newX, newY])
        
        return result

    @staticmethod
    def _DtwCostC(pointsA: numpy.ndarray, pointsB: numpy.ndarray, bestCost: float) -> float:
        # numpy.ascontiguousarray garantisce che l'array sia in memoria contigua
        # (row-major, C-style): indispensabile per passarlo a C senza copie extra
        a = numpy.ascontiguousarray(pointsA, dtype=numpy.float64)
        b = numpy.ascontiguousarray(pointsB, dtype=numpy.float64)
        
        # Ottiene un puntatore grezzo all'inizio dell'array numpy senza copiare i dati
        pointerA = a.ctypes.data_as(ctypes.POINTER(ctypes.c_double))
        pointerB = b.ctypes.data_as(ctypes.POINTER(ctypes.c_double))
        doubleBC = ctypes.c_double(bestCost)
        
        # Chiamata alla funzione C. Tramite CDLL il GIL viene rilasciato
        # automaticamente 
        return _lib.DtwCost2D(pointerA, len(a), pointerB, len(b), doubleBC)
    
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
    def _Visualize(preparedCrackPoints: numpy.ndarray, rotatedCrackPoints: numpy.ndarray, bestMatch: dict):
        _, axes = pyplot.subplots(figsize=(8, 6))
        axes.plot(preparedCrackPoints[:, 0], preparedCrackPoints[:, 1], label="Crack", color="black", linewidth=2)
        axes.plot(rotatedCrackPoints[:, 0], rotatedCrackPoints[:, 1], label="Reflected crack (y → -y)", color="red", linewidth=2)
        
        points = bestMatch["points"]
        axes.plot(points[:, 0], points[:, 1], label=f"{bestMatch['featureIndex']}_{bestMatch['windowIndex']} ({bestMatch['cost']:.4f})")
        
        axes.set_aspect("equal", adjustable="box")
        axes.legend()
        axes.set_title("Best match")
        pyplot.show()
        