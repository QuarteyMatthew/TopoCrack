import geopandas
import numpy
import logging
import requests, zipfile, io

from pyproj import CRS, Geod, Transformer
from shapely.geometry import LineString
from matplotlib import pyplot as plt
from geopandas import GeoDataFrame
from shapely.ops import linemerge
from pathlib import Path

logger = logging.getLogger(__name__)

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
            logger.debug("Cache directory not found, creating it at '%s'...", cachePath)
            cachePath.mkdir(parents=True, exist_ok=True)
        
        logger.info("Coastal data not found in cache. Starting download (resolution=%s)...", resolution)
        downloadURL = f"https://naturalearth.s3.amazonaws.com/{resolution}_physical/{coastlineDir}.zip"
        logger.debug("Download URL: %s", downloadURL)
        
        req = requests.get(downloadURL)
        req.raise_for_status()
        logger.info("Download complete (%.1f MB). Extracting archive...", len(req.content) / 1_000_000)
        
        with zipfile.ZipFile(io.BytesIO(req.content)) as zipFile:
            zipFile.extractall(coastlinePath)
            
        # Rimozione dei file non necessari: logghiamo quanti ne eliminiamo
        # così è facile accorgersi se il formato del pacchetto cambia in futuro.
        removedCount = 0
        suffices = [".cpg", ".dbf", ".prj", ".html", ".txt"]
        for neFile in coastlinePath.iterdir():
            if not neFile.is_file():
                continue
            if neFile.suffix.lower() in suffices:
                neFile.unlink()
                removedCount += 1
        logger.debug("Removed %d unnecessary files from the archive.", removedCount)
    else:
        # I file sono già stati scaricati
        logger.info("Coastal data found in cache, skipping download.")
    
    shapeFile = next(coastlinePath.glob("*.shp"))
    logger.debug("Reading shapefile: '%s'", shapeFile)
    coastlines = geopandas.read_file(shapeFile)
    logger.info("Shapefile loaded: %d coastline features.", len(coastlines))
    
    return geopandas.read_file(shapeFile)

def BuildSlidingWindowDataset(coastlines: GeoDataFrame, pointSpacingKm: float, windowSize: int, stride: int, nNormalizedPoints: int) -> numpy.ndarray:
    pointSpacingM = pointSpacingKm * 1000
    
    logger.info(
        "Building sliding window dataset: pointSpacing=%.1fkm, windowSize=%d, "
        "stride=%d → window covers %.0fkm, new window every %.0fkm.",
        pointSpacingKm, windowSize, stride,
        windowSize * pointSpacingKm,
        stride * pointSpacingKm,
    )
    
    windows = []
    totalPoints = 0
    
    for featIndex, row in coastlines.iterrows():
        coastlinePoints = ResampleCoastlineToPoints(row.geometry, pointSpacingM)
        
        if len(coastlinePoints) < windowSize:
            logger.debug(
                "Feature %d: too short after resampling (%d points < windowSize %d). Skipping.",
                featIndex, len(coastlinePoints), windowSize,
            )
            continue
        
        totalPoints += len(coastlinePoints)
        logger.debug("Feature %d: %d points after resampling.", featIndex, len(coastlinePoints))
        
        GenWindows = GenerateSlidingWindows(
            featureIndex=featIndex,
            coastlinePoints=coastlinePoints,
            windowSize=windowSize,
            stride=stride,
            nNormalizedPoints=nNormalizedPoints,
        )
        windows.extend(GenWindows)
        
    validCount = sum(1 for w in windows if w["points"] is not None)
    logger.info(
        "Dataset built: %d total windows from %d coastline features "
        "(%d valid, %d degenerate). Total resampled points: %d.",
        len(windows), len(coastlines),
        validCount, len(windows) - validCount,
        totalPoints,
    )

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
        logger.debug(
            "Feature %d: only %d points available, need at least %d for one window. Skipping.",
            featureIndex, nTotal, windowSize,
        )
        return windows
    
    nWindows = 0
    nSkipped = 0
    for start in range(0, nTotal - windowSize + 1, stride):
        end = start + windowSize
        windowCoords = coastlinePoints[start:end]
        
        line = LineString(windowCoords.tolist())
        
        try:
            normalizedPoints = SectionToNormalizedPoints(line, nNormalizedPoints)
            windows.append({
                "featureIndex": featureIndex,
                # windowStart o sectionIndex è l'indice del primo punto nella sequenza ricampionata,
                # utile per il debug ma non necessario per il DTW.
                "sectionIndex" : start,
                # Le coordinate geografiche degli estremi sono quello che
                # restituiamo al frontend come risultato finale.
                "startCoord"  : tuple(windowCoords[0]),   # (lon, lat)
                "endCoord"    : tuple(windowCoords[-1]),   # (lon, lat)
                "points"      : normalizedPoints,
            })
            nWindows += 1
            
        except ValueError as e:
            nSkipped += 1
            logger.debug(
                "Feature %d, window [%d:%d] skipped: %s",
                featureIndex, start, end, e,
            )
        
    logger.debug(
        "Feature %d: %d windows generated, %d skipped (degenerate).",
        featureIndex, nWindows, nSkipped,
    )

    return numpy.array(windows)
    
def ExplodeToSections(coastlines: GeoDataFrame, sectionLengthMetre: int) -> GeoDataFrame:
    logger.info("Exploding %d coastline features into sections of %d km each...", len(coastlines), sectionLengthMetre // 1000)
    
    featureIndecies = []
    skippedFeatures = 0
    
    # Elaborazione di ogni coastline
    for featIndex, coastline in coastlines.iterrows():
        segments = ExplodeToGeodeticSegments(coastline.geometry, sectionLengthMetre)

        if len(segments) == 0:
            # Una coastline che non produce sezioni è anomala ma non fatale
            skippedFeatures += 1
            logger.debug("Feature %d produced no sections (geometry may be too short or empty).", featIndex)
            continue

        for segment in segments:
            featureIndecies.append({"featureIndex": featIndex, **segment})

        logger.debug("Feature %d, %d section(s).", featIndex, len(segments))

    logger.info("Exploding complete: %d sections created, %d features skipped.", len(featureIndecies), skippedFeatures,)
    
    return GeoDataFrame(featureIndecies, crs=coastlines.crs).reset_index(drop=True)

def NormalizeAllSections(sections: GeoDataFrame, nPoints: int) -> numpy.ndarray:
    total = len(sections)
    logger.info("Normalizing %d sections to [0,1] × [-y,y] space (%d points each)...", total, nPoints)
    
    results = []
    skippedCount = 0
    
    for idx, (_, section) in enumerate(sections.iterrows()):
        # Log di avanzamento ogni 10%: utile perché questa funzione
        # può girare per diversi minuti sul dataset mondiale a 10m.
        if total > 0 and idx % max(1, total // 10) == 0:
            logger.info("  Normalization progress: %d/%d (%.0f%%)...", idx, total, 100 * idx / total)
        
        try:
            # Normalizza questa sezione allo spazio [0,1] × [-y,y]
            points = SectionToNormalizedPoints(section.geometry, nPoints)
            
        except ValueError as e:
            # Skip delle sezioni degenere
            skippedCount += 1
            logger.warning("Skipped degenerate section (feature=%s, section=%s): %s", section.featureIndex, section.sectionIndex, e,)
            points = None
        
        results.append({
            "featureIndex": section.featureIndex, # Original feature ID
            "sectionIndex": section.sectionIndex, # Section number within feature
            "startCoord"  : section.startCoord,   # Original WGS84 start (for visualization)
            "endCoord"    : section.endCoord,     # Original WGS84 end (for visualization)
            "points"      : points,               # Normalized points or None if failed
        })
    
    logger.info("Normalization complete: %d sections normalized, %d skipped.", total - skippedCount, skippedCount,)
    
    return numpy.array(results)

def ExplodeToGeodeticSegments(coastline: LineString, sectionLengthMetre: int) -> numpy.ndarray:
    if coastline is None or coastline.is_empty:
        return numpy.array([])
    
    # Se le coastline sono dio tipi 'MultiLineString', vengono fuse tutte in una 'LineString'
    if coastline.geom_type == "MultiLineString":    
        # Se le coastline sono connesse le loro 'LineString' vengono fuse
        logger.debug("Geometry is MultiLineString, attempting merge...")
        coastline = linemerge(coastline)
        
        # Invece, se sono disconnesse, tenta il fallback per fonderle tramite una chiamata ricorsiva
        if coastline.geom_type == "MultiLineString":
            subGeomCount = len(list(coastline.geoms))
            logger.debug("Merge failed (disconnected sub-geometries). Falling back to recursive split on %d parts.", subGeomCount,)
            
            sections = []
            for sectionPart in coastline.geoms:
                sections.extend(ExplodeToGeodeticSegments(sectionPart, sectionLengthMetre))
            
            return numpy.array(sections)
            
    coastlineLength = abs(geodCalc.geometry_length(coastline))
    coastlineCoords = list(coastline.coords)
    
    # Discard delle sezioni più corte di 1/5 della lunghezza della sezione ('sectionLengthMetre')
    minLengthMetre = sectionLengthMetre / 5
    if coastlineLength < minLengthMetre:
        logger.debug("Coastline too short (%.0f m < %.0f m minimum), discarding.", coastlineLength, minLengthMetre)
        return numpy.array([])
    
    # Pre-calcola la distanza cumulativa tra i vertici
    vertexDistancies = [0.0]
    for i in range(len(coastlineCoords) - 1):
        _, _, segmentLength = geodCalc.inv(*coastlineCoords[i], *coastlineCoords[i + 1])
        vertexDistancies.append(vertexDistancies[-1] + segmentLength)
        
    # Le coastline di lunghezza inferiore ad 1/5 della lungezza della sezione ma superiore
    # al minimo, vengono divise a metà e ricavate due sezioni distinte
    if coastlineLength < sectionLengthMetre:
        logger.debug("Short coastline (%.0f m): splitting into 2 half-sections.", coastlineLength)
        
        midDistance = coastlineLength / 2
        midPoint = InterpolateGeodetic(coastlineCoords, midDistance)

        # Prima metà: dall'inizio al punto di metà
        start = [coastlineCoords[0]]
        for vtxDist, coord in zip(vertexDistancies, coastlineCoords):
            if 0 < vtxDist < midDistance:
                start.append(coord)
        
        start.append(midPoint)
        
        # Seconda metà: dal punti di metà alla fine
        end = [midPoint]
        for vtxDist, coord in zip(vertexDistancies, coastlineCoords):
            if midDistance < vtxDist < coastlineLength:
                end.append(coord)
        
        end.append(coastlineCoords[-1])
        
        return numpy.array([
            {
                "geometry"    : LineString(start),
                "sectionIndex": 0,
                "startCoord"  : coastlineCoords[0],
                "endCoord"    : midPoint,
                "lengthMetre" : midDistance,
            },
            {
                "geometry"    : LineString(end),
                "sectionIndex": 1,
                "startCoord"  : midPoint,
                "endCoord"    : coastlineCoords[-1],
                "lengthMetre" : coastlineLength - midDistance,
            },
        ])
        
    nSections = int(coastlineLength // sectionLengthMetre)
    remainderLength = coastlineLength - nSections * sectionLengthMetre
    logger.debug("Coastline %.0f m → %d full section(s) + remainder %.0f m.", coastlineLength, nSections, remainderLength)
    
    sections = []

    for i in range(nSections):
        startDistance = i * sectionLengthMetre
        endDistance = startDistance + sectionLengthMetre

        startPoint = InterpolateGeodetic(coastlineCoords, startDistance)
        endPoint = InterpolateGeodetic(coastlineCoords, endDistance)

        innerLine = [startPoint]
        for vtxDist, coord in zip(vertexDistancies, coastlineCoords):
            if startDistance < vtxDist < endDistance:
                innerLine.append(coord)
        innerLine.append(endPoint)

        sections.append({
            "geometry"    : LineString(innerLine),
            "sectionIndex": i,
            "startCoord"  : startPoint,
            "endCoord"    : endPoint,
            "lengthMetre" : sectionLengthMetre,
        })

    # Gestisce il resto dopo l'ultimo intervallo completo
    remainderStart = nSections * sectionLengthMetre
    remainderLength = coastlineLength - remainderStart

    if remainderLength >= minLengthMetre:
        startPoint = InterpolateGeodetic(coastlineCoords, remainderStart)
        endPoint = coastlineCoords[-1]

        innerLine = [startPoint]
        for vtxDist, coord in zip(vertexDistancies, coastlineCoords):
            if remainderStart < vtxDist < coastlineLength:
                innerLine.append(coord)
        innerLine.append(endPoint)

        sections.append({
            "geometry"    : LineString(innerLine),
            "sectionIndex": nSections,
            "startCoord"  : startPoint,
            "endCoord"    : endPoint,
            "lengthMetre" : remainderLength,
        })
    else:
        logger.debug("Remainder section discarded (%.0f m < %.0f m minimum).", remainderLength, minLengthMetre)

    return numpy.array(sections)

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

def SectionToNormalizedPoints(line: LineString, nPoints: int) -> numpy.ndarray:
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

def ColorForSection(featureIndex, sectionIndex, cmap: str = "hsv"):
    # Mix two indices using XOR and multiplication by large primes
    # This ensures nearby indices map to very different hash values
    # 2654435761 and 2246822519 are large primes commonly used in hashing
    h = (featureIndex * 2654435761 ^ sectionIndex * 2246822519) & 0xFFFFFFFF
    
    # Convert 32-bit hash to [0, 1] range for colormap
    value = h / 0xFFFFFFFF
    
    return plt.colormaps[cmap](value)

def VisualizeCoastline(coastlines: GeoDataFrame, normalized: list):
    # Step 3: Generate deterministic colors for each section
    colors = [ColorForSection(item['featureIndex'], item['sectionIndex']) for item in normalized]

    fig, axes = plt.subplots(1, 2, figsize=(16, 6))

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