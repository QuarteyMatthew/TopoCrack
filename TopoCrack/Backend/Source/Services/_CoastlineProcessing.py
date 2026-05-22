import geopandas
import numpy
import requests, zipfile, io

from pyproj import CRS, Geod, Transformer
from shapely.geometry import LineString
from matplotlib import pyplot as plt
from geopandas import GeoDataFrame
from shapely.ops import linemerge
from pathlib import Path

# Inizializzazione del calcolatore geodetico con l'elissoide WGS84
geodCalc = Geod(ellps="WGS84")

def DownloadCoastline(resolution: str = "50m", cacheDir: str = "../Cache") -> GeoDataFrame:
    cachePath = Path(cacheDir)
    coastlineDir = f"ne_{resolution}_coastline"
    coastlinePath = cachePath / coastlineDir
    dotShapePath = coastlinePath / "ne_10m_coastline.shp"
    dotShapeXPath = coastlinePath / "ne_10m_coastline.shx"
    
    if not (coastlinePath.exists() and dotShapePath.exists() and dotShapeXPath.exists()):
        if not cachePath.exists():
            cachePath.mkdir(parents=True, exist_ok=True)
        
        downloadURL = f"https://naturalearth.s3.amazonaws.com/{resolution}_physical/{coastlineDir}.zip"
        req = requests.get(downloadURL)
        req.raise_for_status()
        
        with zipfile.ZipFile(io.BytesIO(req.content)) as zipFile:
            zipFile.extractall(coastlinePath)
            
        # Rimozione dei file non necessari: logghiamo quanti ne eliminiamo
        # così è facile accorgersi se il formato del pacchetto cambia in futuro.
        suffices = [".cpg", ".dbf", ".prj", ".html", ".txt"]
        for neFile in coastlinePath.iterdir():
            if not neFile.is_file():
                continue
            if neFile.suffix.lower() in suffices:
                neFile.unlink()
    else:
        # I file sono già stati scaricati
        pass
    
    shapeFile = next(coastlinePath.glob("*.shp"))
    
    return geopandas.read_file(shapeFile)

def BuildSlidingWindowDataset(coastlines: GeoDataFrame, pointSpacingKm: float, windowSize: int, stride: int, nNormalizedPoints: int) -> numpy.ndarray:
    pointSpacingM = pointSpacingKm * 1000
    windows = []
    totalPoints = 0
    
    for featIndex, row in coastlines.iterrows():
        coastlinePoints = ResampleCoastlineToPoints(row.geometry, pointSpacingM)
        
        if len(coastlinePoints) < windowSize:
            continue
        
        totalPoints += len(coastlinePoints)
        
        GenWindows = GenerateSlidingWindows(
            featureIndex=featIndex,
            coastlinePoints=coastlinePoints,
            windowSize=windowSize,
            stride=stride,
            nNormalizedPoints=nNormalizedPoints,
        )
        windows.extend(GenWindows)
        
    return numpy.array(windows)

def ResampleCoastlineToPoints(coastline: LineString, pointSpacingM: float) -> numpy.ndarray:
    if coastline is None or coastline.is_empty:
        return numpy.array([])
    
    if coastline.geom_type == "MultiLineString":
        coastline = linemerge(coastline)
        
        if coastline.geom_type == "MultiLineString":
            allPoints = []
            
            for part in coastline.geoms:
                partPoints = ResampleCoastlineToPoints(part, pointSpacingM)
                if len(partPoints) > 0:
                    allPoints.append(partPoints)
                    
            return numpy.vstack(allPoints) if allPoints else numpy.array([])
    
    totalLength = abs(geodCalc.geometry_length(coastline))
    coastlineCoords = list(coastline.coords)
    
    if totalLength < pointSpacingM:
        return numpy.array([])
    
    nPoints = int(totalLength / pointSpacingM) + 1
    distances = numpy.linspace(0, (nPoints - 1) * pointSpacingM, nPoints)
    
    sampledPoints = []
    for d in distances:
        pt = InterpolateGeodetic(coastlineCoords, d)
        sampledPoints.append(pt)
        
    return numpy.array(sampledPoints)

def GenerateSlidingWindows(featureIndex: int, coastlinePoints: numpy.ndarray, windowSize: int, stride: int, nNormalizedPoints: int) -> numpy.ndarray:
    windows = []
    nTotal = len(coastlinePoints)
    
    if nTotal < windowSize:
        return windows
    
    for start in range(0, nTotal - windowSize + 1, stride):
        end = start + windowSize
        windowCoords = coastlinePoints[start:end]
        
        line = LineString(windowCoords.tolist())
        
        normalizedPoints = WindowToNormalizedPoints(line, nNormalizedPoints)
        windows.append({
            "featureIndex": featureIndex,
            # windowIndex è l'indice del primo punto nella sequenza ricampionata,
            # utile per il debug ma non necessario per il DTW.
            "windowIndex" : start,
            # Le coordinate geografiche degli estremi sono quello che
            # restituiamo al frontend come risultato finale.
            "startCoord"  : tuple(windowCoords[0]),   # (lon, lat)
            "endCoord"    : tuple(windowCoords[-1]),   # (lon, lat)
            "points"      : normalizedPoints,
        })

    return numpy.array(windows)

def InterpolateGeodetic(coastlineCoords: list, midDistance: float) -> tuple:
    accumulatedDist = 0.0
    
    # Scorre tutti i segmenti della coastline
    for i in range(len(coastlineCoords) - 1):
        lon1, lat1 = coastlineCoords[i]
        lon2, lat2 = coastlineCoords[i + 1]
        
        # Calcola la distanza geodetica tra i punti in metri
        azimuth, _, segmentLength = geodCalc.inv(lon1, lat1, lon2, lat2)
        
        # Controlla se la distanza target rientra in questo segmento
        if accumulatedDist + segmentLength >= midDistance:
            # Calcola quanto lontano deve andare questo segmento
            ramaining = midDistance - accumulatedDist
            # Trova l'esatto punto a quella distanza
            newLon, newLat, _ = geodCalc.fwd(lon1, lat1, azimuth, ramaining)
            
            return (newLon, newLat)
        
        accumulatedDist += segmentLength
        
    # Se abbiamo esaurito i segmenti, restituisce l'endpoint
    return coastlineCoords [-1]

def WindowToNormalizedPoints(line: LineString, nPoints: int) -> numpy.ndarray:
    # Trova la longitudine centrale di questa sezione
    lonCenter = numpy.mean([c[0] for c in line.coords])
    
    # Project per UTM locale: gradi lon/lat → metri
    # Utilizza un GeoDataFrame temporaneo per sfruttare la proiezione di geopandas
    utmGeodeticFrame = geopandas.GeoDataFrame(geometry=[line], crs="EPSG:4326")
    utmGeodeticFrame = utmGeodeticFrame.to_crs(GetUtmCrsFormGivenLongitude(lonCenter))
    lineLengthMetre = utmGeodeticFrame.geometry.iloc[0]

    # Campiona in 'nPoints' uniformemente lungo la linea
    distances = numpy.linspace(0, lineLengthMetre.length, nPoints)
    points = numpy.array([[lineLengthMetre.interpolate(distance).x, lineLengthMetre.interpolate(distance).y] 
                          for distance in distances])

    # Step 1: Translate so start point is at origin
    points -= points[0]

    # Passaggio 2 e 3: ruotare in modo che il punto finale si trovi sull'asse x positivo
    # Calcola l'angolo di rotazione per allineare il punto finale all'asse x
    angle = numpy.arctan2(points[-1, 1], points[-1, 0])
    cos, sin = numpy.cos(-angle), numpy.sin(-angle)
    
    # Applica la matrice di rotazione: [[cos, -sin], [sin, cos]]
    rotationMatrix = numpy.array([[cos, -sin], [sin, cos]])
    points = (rotationMatrix @ points.T).T

    # Applica y=0 all'inizio e alla fine (numerical cleanup)
    points[0,  1] = 0.0
    points[-1, 1] = 0.0

    # Passaggio 4: ridimensiona in modo che x vari da 0 a 1
    startToEndDistanceX = points[-1, 0]  # Distanza dall'inizio alla fine lungo l'asse x
    if startToEndDistanceX < 1e-10:
        raise ValueError("Degenerate section: start and end coincide")

    return points / startToEndDistanceX

def GetUtmCrsFormGivenLongitude(longitude: float) -> CRS:
    # UTM divide la Terra in 60 zone, ciascuna larga 6 gradi
    # La zona 1 è centrata su lon=-177, la zona 30 su lon=-3, la zona 31 su lon=3, ecc.
    zone = int((longitude + 180) / 6) + 1
    
    # Codice EPSG: 32600 + zona per l'emisfero settentrionale (32700 + zona per quello meridionale)
    return CRS.from_epsg(32600 + zone)

def ColorForSection(featureIndex, windowIndex, cmap: str = "hsv"):
    # Mix two indices using XOR and multiplication by large primes
    # This ensures nearby indices map to very different hash values
    # 2654435761 and 2246822519 are large primes commonly used in hashing
    h = (featureIndex * 2654435761 ^ windowIndex * 2246822519) & 0xFFFFFFFF
    
    # Convert 32-bit hash to [0, 1] range for colormap
    value = h / 0xFFFFFFFF
    
    return plt.colormaps[cmap](value)

def VisualizeCoastline(coastlines: GeoDataFrame, normalized: list):
    # Step 3: Generate deterministic colors for each section
    colors = [ColorForSection(item['featureIndex'], item['windowIndex']) for item in normalized]

    _, axes = plt.subplots(1, 2, figsize=(16, 6))

    # --- Plot 1: Original coastlines (WGS84 coordinates) ---
    coastlines.plot(ax=axes[0], color='steelblue', lw=0.5)
    axes[0].set_title("Costa originale (WGS84)")
    axes[0].set_aspect('equal')

    # --- Plot 2: Sections reprojected back to WGS84 ---
    # Fix: invert the normalization in UTM space (meters), then convert to WGS84.
    # Doing it in lon/lat space (as before) causes severe distortion near the poles
    # because degrees of longitude shrink dramatically at high latitudes.
    coastlines.plot(ax=axes[1], color='lightgray', lw=0.4, zorder=1)

    for item, color in zip(normalized, colors):
        if item['points'] is None:
            continue

        start_lonlat = item['startCoord']
        end_lonlat   = item['endCoord']

        # Use the same UTM zone that was used during normalization
        lon_center = (start_lonlat[0] + end_lonlat[0]) / 2
        utm_crs = GetUtmCrsFormGivenLongitude(lon_center)

        to_utm  = Transformer.from_crs("EPSG:4326", utm_crs, always_xy=True)
        to_wgs  = Transformer.from_crs(utm_crs, "EPSG:4326", always_xy=True)

        # Convert start and end to UTM (meters) — same space the normalization used
        start_utm = numpy.array(to_utm.transform(start_lonlat[0], start_lonlat[1]))
        end_utm   = numpy.array(to_utm.transform(end_lonlat[0],   end_lonlat[1]))

        chord_vec = end_utm - start_utm
        chord_len = numpy.linalg.norm(chord_vec)
        angle     = numpy.arctan2(chord_vec[1], chord_vec[0])

        c, s  = numpy.cos(angle), numpy.sin(angle)
        R_inv = numpy.array([[c, -s], [s, c]])

        # 1. Scale by UTM chord length  2. Rotate back  3. Translate to UTM start
        pts_utm = (R_inv @ (item["points"] * chord_len).T).T + start_utm

        # Convert UTM coordinates back to WGS84 lon/lat
        lons, lats = to_wgs.transform(pts_utm[:, 0], pts_utm[:, 1])

        axes[1].plot(lons, lats, lw=1.0, alpha=0.6, color=color, rasterized=True)

    axes[1].set_title("Sezioni riposizionate (WGS84)")
    axes[1].set_aspect("equal")
    axes[1].set_xlabel("Longitudine")
    axes[1].set_ylabel("Latitudine")

    plt.tight_layout()
    plt.show()
    