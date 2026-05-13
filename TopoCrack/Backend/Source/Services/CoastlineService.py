import pickle
import numpy
import logging
from pathlib import Path

from ._CoastlineProcessing import DownloadCoastline, BuildSlidingWindowDataset
from ._CoastlineProcessing import ExplodeToSections, NormalizeAllSections

logger = logging.getLogger(__name__)

class CoastlineService:
    
    _CachePath         = Path("Cache/NeturalEarthData")
    _PicklePath        = Path("Cache/NormalizedSections.pkl")
    _SectionLength     = 1_000_000 # 1000 km
    _NPoints           = 50
    _PointSpacingKm    = 20 # distanza tra punti consecutivi
    _WindowSize        = 50 # punti per finestra
    _Stride            = 3  # avanzamento
    _Normalized_Points = 50 # punti DTW per finestra (uguale a windowSize)

    @staticmethod
    def LoadOrBuildCoastlineIntoSlidingWindows() -> numpy.ndarray:
        # ---- 1. Controlla che il pickle file esista nella cache ----
        # Il file esiste: viene caricato dalla cache
        if CoastlineService._PicklePath.exists():
            fileSizeMb = CoastlineService._PicklePath.stat().st_size / 1_000_000
            logger.info("Pickle cache found at '%s' (%.1f MB). Loading...",CoastlineService._PicklePath, fileSizeMb)
            
            with open(CoastlineService._PicklePath, "rb") as f:
                data = pickle.load(f)
            
            logger.info("Coastal data loaded from cache: %d sections.", len(data))
            
            return data

        logger.info("Pickle not found. Starting full build pipeline...")

        logger.info("Step 1/2 — Downloading coastline data (resolution=10m)...")
        coastlines = DownloadCoastline(resolution="10m", cacheDir=CoastlineService._CachePath)
        logger.info("Step 1/2 complete: %d coastline features loaded.", len(coastlines))

        logger.info(
            "Step 2/2 — Building sliding window dataset "
            "(spacing=%.0fkm, window=%.0fkm, stride=%.0fkm)...",
            CoastlineService._PointSpacingKm,
            CoastlineService._WindowSize * CoastlineService._PointSpacingKm,
            CoastlineService._Stride * CoastlineService._PointSpacingKm,
        )
        normalized = BuildSlidingWindowDataset(
            coastlines=coastlines,
            pointSpacingKm=CoastlineService._PointSpacingKm,
            windowSize=CoastlineService._WindowSize,
            stride=CoastlineService._Stride,
            nNormalizedPoints=CoastlineService._Normalized_Points,
        )
        logger.info("Step 2/2 complete: %d windows generated.", len(normalized))

        logger.info("Saving to '%s'...", CoastlineService._PicklePath)
        
        CoastlineService._PicklePath.parent.mkdir(parents=True, exist_ok=True)
        with open(CoastlineService._PicklePath, "wb") as f:
            pickle.dump(normalized, f)

        savedSizeMb = CoastlineService._PicklePath.stat().st_size / 1_000_000
        logger.info("Pickle saved (%.1f MB). Returning %d windows.", savedSizeMb, len(normalized))

        return normalized

    @staticmethod
    def LoadOrBuildCoastlineIntoSections() -> numpy.ndarray:
        # ---- 1. Controlla che il pickle file esista nella cache ----
        # Il file esiste: viene caricato dalla cache
        if CoastlineService._PicklePath.exists():
            fileSizeMb = CoastlineService._PicklePath.stat().st_size / 1_000_000
            logger.info("Pickle cache found at '%s' (%.1f MB). Loading...",CoastlineService._PicklePath, fileSizeMb)
            
            with open(CoastlineService._PicklePath, "rb") as f:
                data = pickle.load(f)
            
            logger.info("Coastal data loaded from cache: %d sections.", len(data))
            
            return data
        
        # ---- 2. Il file non esiste (cache miss): esegue i coastline services ----
        # Il file non esiste: viene riscaricato, diviso in sezioni e
        # queste ultime tutte normalizzate
        logger.info("Pickle not found at '%s'. Starting full build pipeline...", CoastlineService._PicklePath)
        
        logger.info("Step 1/3: Downloading coastline data (resolution=10m)...")
        coastlines = DownloadCoastline(resolution="10m", cacheDir=CoastlineService._CachePath)
        logger.info("Step 1/3 complete: %d coastline features loaded.", len(coastlines))

        logger.info("Step 2/3: Exploding coastlines into sections of %d km...", CoastlineService._SectionLength // 1000)
        sections = ExplodeToSections(coastlines, sectionLengthMetre=CoastlineService._SectionLength)
        logger.info("Step 2/3 complete: %d sections created.", len(sections))

        logger.info("Step 3/3: Normalizing all sections (%d points each)...", CoastlineService._NPoints)
        normalized = NormalizeAllSections(sections, nPoints=CoastlineService._NPoints)
        validCount = sum(1 for s in normalized if s["points"] is not None)
        logger.info("Step 3/3 complete: %d sections normalized (%d valid, %d degenerate).", len(normalized), validCount, len(normalized) - validCount)
        
        # ---- 2.2. Visualizza il risultato dei coastline services ----
        # VisualizeCoastline(coastlines, normalized)
        
        # ---- 3. Legge, carica e restitusce i dati del pickle file ----
        logger.info("Saving normalized coastal data to '%s'...", CoastlineService._PicklePath)
        
        CoastlineService._PicklePath.parent.mkdir(parents=True, exist_ok=True)
        with open(CoastlineService._PicklePath, "wb") as f:
            pickle.dump(normalized, f)
            
        savedSizeMb = CoastlineService._PicklePath.stat().st_size  / 1_000_000
        logger.info("Pickle saved successfully (%.1f MB). Returning %d sections.", savedSizeMb, len(normalized))
        
        return normalized

# CoastlineService.LoadOrBuild()