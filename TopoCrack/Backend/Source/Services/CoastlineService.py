import pickle
import numpy
from pathlib import Path

from _CoastlineProcessing import DownloadCoastline, ExplodeToSections, NormalizeAllSections

CACHE_DIR      = Path("../Cache/NeturalEarthData")
PICKLE_PATH    = Path("../Cache/NormalizedSections.pkl")
SECTION_LENGTH = 1_000_000  # 1000 km
N_POINTS       = 100

class CoastlineService:
    
    @staticmethod
    def LoadOrBuild() -> numpy.ndarray:
        # Il file esiste: viene caricato dalla cache
        if PICKLE_PATH.exists():
            print("Loading coastal sections from cache...")
            with open(PICKLE_PATH, "rb") as f:
                return pickle.load(f)
            
        # Il file non esiste: viene riscaricato, diviso in sezioni e
        # queste ultime tutte normalizzate
        print("Pickle not found. Downloading and processing geographic data...")
        
        print("Downloading geographic data...")
        coastlines = DownloadCoastline(resolution="10m", cacheDir=CACHE_DIR)
        print(f"Divirding coastlines into sections of {SECTION_LENGTH} metre each...")
        sections = ExplodeToSections(coastlines, sectionLengthMetre=SECTION_LENGTH)
        print("Normalizing all sections...")
        normalized = NormalizeAllSections(sections, nPoints=N_POINTS)
        
        # Visualizzazione
        # VisualizeCoastline(coastlines, normalized)
        
        PICKLE_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(PICKLE_PATH, "wb") as f:
            pickle.dump(normalized, f)
            
        print("Pickle saved")
        
        return normalized

CoastlineService.LoadOrBuild()