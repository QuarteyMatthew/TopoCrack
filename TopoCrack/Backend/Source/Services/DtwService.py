import numpy
from joblib import Parallel, delayed

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
        
        return bestMatch
    
    @staticmethod
    def _ComputeCost(crackPoints: numpy.ndarray, section: dict) -> dict:
        cost = DtwService._DtwCost(crackPoints, section["points"])
        return { **section, "cost": cost }
    
    @staticmethod
    def _PreparePoints(crackPoints: numpy.ndarray) -> numpy.ndarray:
        pass
    
    @staticmethod
    def _DtwCost(pointsA: numpy.ndarray, pointsB: numpy.ndarray) -> float:
        pass