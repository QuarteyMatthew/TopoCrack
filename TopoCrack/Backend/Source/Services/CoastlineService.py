import pickle
from pathlib import Path

from Services._CoastlineProcessing import DownloadCoastline, ExplodeToSections, NormalizeAllSections

CACHE_DIR      = Path("../Cache/Data/ne_data")
PICKLE_PATH    = Path("../Cache/NormalizedSections.pkl")
SECTION_LENGTH = 1_000_000  # 1000 km
N_POINTS       = 100

class CoastlineService:
    
    @staticmethod
    def LoadOrBuild() -> list:
        # Il file esiste: viene caricato dalla cache
        if PICKLE_PATH.exists():
            print("Loading coastal sections from cache...")
            with open(PICKLE_PATH, "rb") as f:
                return pickle.load(f)
            
        # Il file non esiste: viene riscaricato, diviso in sezioni e
        # queste ultime tutte normalizzate
        print("Pickle not found. Downloading and processing in progress...")
        coast = DownloadCoastline(resolution="10m", cacheDir=CACHE_DIR)
        sections = ExplodeToSections(coast, sectionLengthMetre=SECTION_LENGTH)
        normalized = NormalizeAllSections(sections, nPoints=N_POINTS)
        
        PICKLE_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(PICKLE_PATH, "wb") as f:
            pickle.dump(normalized, f)
            
        print("Pickle saved")
        
        return normalized
            