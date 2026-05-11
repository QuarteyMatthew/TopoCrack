import pickle
import numpy
import logging
from pathlib import Path

from ._CoastlineProcessing import DownloadCoastline, ExplodeToSections, NormalizeAllSections

CACHE_DIR      = Path("Cache/NeturalEarthData")
PICKLE_PATH    = Path("Cache/NormalizedSections.pkl")
SECTION_LENGTH = 1_000_000  # 1000 km
N_POINTS       = 50

logger = logging.getLogger(__name__)

class CoastlineService:
    
    # _CacheDir      = Path("Cache/NeturalEarthData")
    # _PicklePath    = Path("Cache/NormalizedSections.pkl")
    # _SectionLength = 1_000_000 # 1000 km
    # _NPoints       = 100

    @staticmethod
    def LoadOrBuild() -> numpy.ndarray:
        # ---- 1. Controlla che il pickle file esista nella cache ----
        # Il file esiste: viene caricato dalla cache
        if PICKLE_PATH.exists():
            fileSizeMb = PICKLE_PATH.stat().st_size / 1_000_000
            logger.info("Pickle cache found at '%s' (%.1f MB). Loading...",PICKLE_PATH, fileSizeMb)
            
            with open(PICKLE_PATH, "rb") as f:
                data = pickle.load(f)
            
            logger.info("Coastal data loaded from cache: %d sections.", len(data))
            
            return data
        
        # ---- 2. Il file non esiste (cache miss): esegue i coastline services ----
        # Il file non esiste: viene riscaricato, diviso in sezioni e
        # queste ultime tutte normalizzate
        logger.info("Pickle not found at '%s'. Starting full build pipeline...", PICKLE_PATH)
        
        logger.info("Step 1/3: Downloading coastline data (resolution=10m)...")
        coastlines = DownloadCoastline(resolution="10m", cacheDir=CACHE_DIR)
        logger.info("Step 1/3 complete: %d coastline features loaded.", len(coastlines))

        logger.info("Step 2/3: Exploding coastlines into sections of %d km...", SECTION_LENGTH // 1000)
        sections = ExplodeToSections(coastlines, sectionLengthMetre=SECTION_LENGTH)
        logger.info("Step 2/3 complete: %d sections created.", len(sections))

        logger.info("Step 3/3: Normalizing all sections (%d points each)...", N_POINTS)
        normalized = NormalizeAllSections(sections, nPoints=N_POINTS)
        validCount = sum(1 for s in normalized if s["points"] is not None)
        logger.info("Step 3/3 complete: %d sections normalized (%d valid, %d degenerate).", len(normalized), validCount, len(normalized) - validCount)
        
        # ---- 2.2. Visualizza il risultato dei coastline services ----
        # VisualizeCoastline(coastlines, normalized)
        
        # ---- 3. Legge, carica e restitusce i dati del pickle file ----
        logger.info("Saving normalized coastal data to '%s'...", PICKLE_PATH)
        
        PICKLE_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(PICKLE_PATH, "wb") as f:
            pickle.dump(normalized, f)
            
        savedSizeMb = PICKLE_PATH.stat().st_size  / 1_000_000
        logger.info("Pickle saved successfully (%.1f MB). Returning %d sections.", savedSizeMb, len(normalized))
        
        return normalized

# CoastlineService.LoadOrBuild()