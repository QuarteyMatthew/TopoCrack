import pickle
import time
import numpy
import logging
from pathlib import Path

from ._CoastlineProcessing import DownloadCoastline, BuildSlidingWindowDataset, VisualizeCoastline

logger = logging.getLogger(__name__)

class CoastlineService:
    
    _CachePath         = Path("Cache/NeturalEarthData")
    _PicklePath        = Path("Cache/NormalizedSections.pkl")
    _PointSpacingKm    = 5  # distanza tra punti consecutivi
    _WindowSize        = 50 # punti per finestra
    _Stride            = 3  # avanzamento
    _Normalized_Points = 50 # punti DTW per finestra (uguale a windowSize)

    @staticmethod
    def LoadCoastalData() -> numpy.ndarray:
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
        
        startTime = time.perf_counter()
        normalized = BuildSlidingWindowDataset(
            coastlines=coastlines,
            pointSpacingKm=CoastlineService._PointSpacingKm,
            windowSize=CoastlineService._WindowSize,
            stride=CoastlineService._Stride,
            nNormalizedPoints=CoastlineService._Normalized_Points,
        )
        elapsed = time.perf_counter() - startTime
        logger.info("Sliding windows Build 1: %.6f", elapsed)
        
        startTime = time.perf_counter()
        normalized = numpy.concatenate((normalized, BuildSlidingWindowDataset(
            coastlines=coastlines,
            pointSpacingKm=CoastlineService._PointSpacingKm * 2,
            windowSize=CoastlineService._WindowSize,
            stride=CoastlineService._Stride,
            nNormalizedPoints=CoastlineService._Normalized_Points,
        )))
        elapsed = time.perf_counter() - startTime
        logger.info("Sliding windows Build 2: %.6f", elapsed)
        
        startTime = time.perf_counter()
        normalized = numpy.concatenate((normalized, BuildSlidingWindowDataset(
            coastlines=coastlines,
            pointSpacingKm=CoastlineService._PointSpacingKm * 4,
            windowSize=CoastlineService._WindowSize,
            stride=CoastlineService._Stride,
            nNormalizedPoints=CoastlineService._Normalized_Points,
        )))
        elapsed = time.perf_counter() - startTime
        logger.info("Sliding windows Build 3: %.6f", elapsed)
        
        startTime = time.perf_counter()
        normalized = numpy.concatenate((normalized, BuildSlidingWindowDataset(
            coastlines=coastlines,
            pointSpacingKm=CoastlineService._PointSpacingKm * 10,
            windowSize=CoastlineService._WindowSize,
            stride=CoastlineService._Stride,
            nNormalizedPoints=CoastlineService._Normalized_Points,
        )))
        elapsed = time.perf_counter() - startTime
        logger.info("Sliding windows Build 4: %.6f", elapsed)
        
        startTime = time.perf_counter()
        normalized = numpy.concatenate((normalized, BuildSlidingWindowDataset(
            coastlines=coastlines,
            pointSpacingKm=CoastlineService._PointSpacingKm * 20,
            windowSize=CoastlineService._WindowSize * 2,
            stride=CoastlineService._Stride - 1,
            nNormalizedPoints=CoastlineService._Normalized_Points * 2,
        )))
        elapsed = time.perf_counter() - startTime
        logger.info("Sliding windows Build 5: %.6f", elapsed)
        
        startTime = time.perf_counter()
        normalized = numpy.concatenate((normalized, BuildSlidingWindowDataset(
            coastlines=coastlines,
            pointSpacingKm=CoastlineService._PointSpacingKm * 40,
            windowSize=CoastlineService._WindowSize * 4,
            stride=CoastlineService._Stride - 2,
            nNormalizedPoints=CoastlineService._Normalized_Points * 4,
        )))
        elapsed = time.perf_counter() - startTime
        logger.info("Sliding windows Build 6: %.6f", elapsed)
        
        logger.info("Step 2/2 complete: %d windows generated.", len(normalized))

        logger.info("Saving to '%s'...", CoastlineService._PicklePath)
        
        CoastlineService._PicklePath.parent.mkdir(parents=True, exist_ok=True)
        with open(CoastlineService._PicklePath, "wb") as f:
            pickle.dump(normalized, f)

        savedSizeMb = CoastlineService._PicklePath.stat().st_size / 1_000_000
        logger.info("Pickle saved (%.1f MB). Returning %d windows.", savedSizeMb, len(normalized))

        return normalized
    
# CoastlineService.LoadOrBuild()