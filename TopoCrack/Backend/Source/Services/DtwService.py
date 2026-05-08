import math
import numpy

import matplotlib.pyplot as pyplot
from joblib import Parallel, delayed
from pathlib import Path

class DtwService:

    @staticmethod
    def FindBestMatch(crackPoints: numpy.ndarray, coastalData: list) -> dict:
        """
        Restituisce la sezione costiera con il DTW score più basso.
        """
        
        preparedCarckPoints = DtwService._PreparePoints(crackPoints)
        
        results = Parallel(n_jobs=-1, prefer="threads")(
            delayed(DtwService._ComputeCost)(preparedCarckPoints, section)
            for section in coastalData
            if section["pts"] is not None
        )
        
        # Trova il profilo costiero con il cost più basso
        bestMatch = min(results, key=lambda result: result["cost"])
        
        DtwService._Visualize(crackPoints, coastalData, bestMatch)

        return bestMatch
    
    @staticmethod
    def _ComputeCost(crackPoints: numpy.ndarray, section: dict) -> dict:
        cost = DtwService._DtwCost(crackPoints, section["points"])
        return { **section, "cost": cost }
    
    @staticmethod
    def _PreparePoints(crackPoints: numpy.ndarray) -> numpy.ndarray:
        # -------- 1. Traslazione all'origine --------
        traslatedPoints = crackPoints - crackPoints[0]

        # -------- 2. Calcola la rotazione -------
        traslatedEnd = traslatedPoints[-1]

        # Calcola l'arcotangente
        angle = math.atan2(traslatedEnd[1], traslatedEnd[0])

        # Matrice di rotazione
        cos, sin = numpy.cos(-angle), numpy.sin(-angle)
        rotationMatrix = numpy.array([[cos, -sin], [sin, cos]])

        # -------- 3. Applicazione della rotazione a tutti i punti -------
        rotatedPoints = numpy.array(numpy.dot(traslatedPoints, rotationMatrix.T))
    
        # -------- 4. Scale -------
        rotatedEnd = rotatedPoints[-1]

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
    def _DtwCost(pointsA: numpy.ndarray, pointsB: numpy.ndarray) -> float:
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
    def _Visualize(crackPoints: numpy.ndarray, coastalData: list, bestMatch: dict):
        _, axes = pyplot.subplots(figsize=(8, 6))
        axes.plot(crackPoints[:, 0], crackPoints[:, 1], label="User path", color="black", linewidth=2)
        
        bestCoastalData = next(
        (coast for coast in coastalData 
            if coast["featureIndex"] == bestMatch[0] and coast["sectionIndex"] == bestMatch[1]),
            None
        )

        points = bestCoastalData["points"]
        axes.plot(points[:, 0], points[:, 1], label=f"{bestMatch[0]}_{bestMatch[1]} ({bestMatch[2]:.4f})")
        
        axes.set_aspect("equal", adjustable="box")
        axes.legend()
        axes.set_title("Best match")
        pyplot.show()