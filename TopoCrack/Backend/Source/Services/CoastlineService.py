import pickle
import numpy
from pathlib import Path

from ._CoastlineProcessing import DownloadCoastline, BuildSlidingWindowDataset

class CoastlineService:
    
    _CachePath         = Path("Cache/NeturalEarthData")
    _PicklePath        = Path("Cache/NormalizedSections.pkl")
    _PointSpacingKm    = 5  # distanza tra punti consecutivi
    _WindowSize        = 50 # punti per finestra
    _Stride            = 3  # avanzamento
    _Normalized_Points = 50 # punti DTW per finestra (deve essere uguale a windowSize)

    @staticmethod
    def LoadCoastalData() -> numpy.ndarray:
        # ---- 1. Controlla che il pickle file esista nella cache ----
        # Il file esiste: viene caricato dalla cache
        if CoastlineService._PicklePath.exists():
            with open(CoastlineService._PicklePath, "rb") as f:
                data = pickle.load(f)
            return data

        coastlines = DownloadCoastline(resolution="10m", cacheDir=CoastlineService._CachePath)

        # Ogni build cattura la stessa coastline a scale geografiche diverse.
        # pointSpacingKm × windowSize = lunghezza fisica della finestra:
        #   Build 1:   5km × 50  =   250km per finestra
        #   Build 2:  10km × 50  =   500km per finestra
        #   Build 3:  20km × 50  =  1000km per finestra
        #   Build 4:  50km × 50  =  2500km per finestra
        #   Build 5: 100km × 50  =  5000km per finestra
        #   Build 6: 200km × 50  = 10000km per finestra
        # nNormalizedPoints = 50 è UGUALE per tutti: il confronto è equo.
        nPoints = CoastlineService._Normalized_Points
        wSize   = CoastlineService._WindowSize
        stride  = CoastlineService._Stride

        buildConfigs = [
            { "pointSpacingKm": CoastlineService._PointSpacingKm,     },
            { "pointSpacingKm": CoastlineService._PointSpacingKm * 2  },
            { "pointSpacingKm": CoastlineService._PointSpacingKm * 4  },
            { "pointSpacingKm": CoastlineService._PointSpacingKm * 10 },
            { "pointSpacingKm": CoastlineService._PointSpacingKm * 20 },
            { "pointSpacingKm": CoastlineService._PointSpacingKm * 40 }
        ]

        allWindows = []
        for config in buildConfigs:
            pSpacingKm = config["pointSpacingKm"]
            windows = BuildSlidingWindowDataset(
                coastlines=coastlines,
                pointSpacingKm=pSpacingKm,
                windowSize=wSize,
                stride=stride,
                nNormalizedPoints=nPoints,  # sempre 50, per tutti i build
            )
            allWindows.extend(windows)
        
        normalized = numpy.array(allWindows)

        CoastlineService._PicklePath.parent.mkdir(parents=True, exist_ok=True)
        with open(CoastlineService._PicklePath, "wb") as f:
            pickle.dump(normalized, f)

        return normalized