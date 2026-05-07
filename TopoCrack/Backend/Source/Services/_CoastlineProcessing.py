import geopandas
from geopandas import GeoDataFrame
from shapely.geometry import LineString
from shapely.ops import linemerge
from pyproj import CRS, Geod
from pathlib import Path
import requests, zipfile, io
import numpy

# Inizializzazione del calcolatore geodetico con l'elissoide WGS84
geodCalc = Geod(ellps="WGS84")

def DownloadCoastline(resolution: str = "50m", cacheDir: str = "../Cache") -> GeoDataFrame:
    cachePath = Path(cacheDir)
    
    if not cachePath.exists():
        cachePath.mkdir(exist_ok=True)
        
    fileName = f"ne_{resolution}_coastline"
    filePath = cachePath / fileName
    downloadURL = f"https://naturalearth.s3.amazonaws.com/{resolution}_physical/{fileName}.zip"
    
    req = requests.get(downloadURL)
    req.raise_for_status()
    
    with zipfile.ZipFile(io.BytesIO(req.content)) as zipFile:
        zipFile.extractall(filePath)
        
    shapeFile = next(filePath.glob("*.shp")) 
    
    return geopandas.read_file(shapeFile)

def ExplodeToSections(coastlines: GeoDataFrame, sectionLengthMetre: int) -> numpy.ndarray:
    featureIndecies = []
    
    # Elaborazione di ogni coastline
    for featIndex, coastline in  coastlines.iterrows():
        segments = ExplodeToGeodeticSegments(coastline.geometry, sectionLengthMetre)
        
        # Append delle nuove sezioni preservando il feature index
        for segment in segments:
            featureIndecies.append({"featureIndex": featIndex, **segment})
    
    return numpy.array(featureIndecies)

def NormalizeAllSections(sections: numpy.ndarray, nPoints: int) -> numpy.ndarray:
    results = []
    
    for _, section in sections.iterrows():
        try:
            # Normalizza questa sezione allo spazio [0,1] × [-y,y]
            points = SectionToNormalizedPoints(section.geometry, nPoints)
        except ValueError as e:
            # Skip delle sezioni degenere
            print(f"  Skipped section ({section.featureIndex}, {section.sectionIndex}): {e}")
            points = None
        
        results.append({
            "featureIndex": section.featureIndex, # Original feature ID
            "sectionindex": section.sectionIndex, # Section number within feature
            "startCoord"  : section.startCoord,   # Original WGS84 start (for visualization)
            "endCoord"    : section.endCoord,     # Original WGS84 end (for visualization)
            "points"      : points,               # Normalized points or None if failed
        })
    
    return numpy.array(results)

def ExplodeToGeodeticSegments(coastline: LineString, sectionLengthMetre: int) -> numpy.ndarray:
    if coastline is None or coastline.is_empty:
        return numpy.array([])
    
    # Se le coastline sono dio tipi 'MultiLineString', vengono fuse tutte in una 'LineString'
    if coastline.geom_type == "MultiLineString":
        # Se le coastline sono connesse le loro 'LineString' vengono fuse
        coastline = linemerge(coastline)
        
        # Invece, se sono disconnesse, tenta il fallback per fonderle tramite una chiamata ricorsiva
        if coastline.geom_type == "MultiLineString":
            sections = []
            for sectionPart in coastline.geoms:
                sections.extend(ExplodeToGeodeticSegments(sectionPart, sectionLengthMetre))
            
            return numpy.array(sections)
            
    coastlineLength = abs(geodCalc.geometry_length(coastline))
    coastlineCoords = list(coastline.coords)
    
    # Discard delle sezioni più corte di 1/5 della lunghezza della sezione ('sectionLengthMetre')
    minLengthMetre = sectionLengthMetre / 5
    if coastlineLength < minLengthMetre:
        return numpy.array([])
    
    # Pre-calcola la distanza cumulativa tra i vertici
    vertexDistancies = [0.0]
    for i in range(len(coastlineCoords) - 1):
        _, _, segmentLength = geodCalc.inv(*coastlineCoords[i], *coastlineCoords[i + 1])
        vertexDistancies.append(vertexDistancies[-1] + segmentLength)
        
    # Le coastline di lunghezza inferiore ad 1/5 della lungezza della sezione ma superiore
    # al minimo, vengono divise a metà e ricavate due sezioni distinte
    if coastlineLength < sectionLengthMetre:
        midDistance = coastlineLength / 2
        midPoint = InterpolateGeodetic(coastlineCoords, midDistance)

        # Prima metà: dall'inizio al punto di metà
        start = [coastlineCoords[0]]
        for vtxDist, coord in zip(vertexDistancies, coastlineCoords):
            if 0 < vtxDist < midDistance:
                start.append(coord)
        
        start.append(midPoint)
        
        # Seconda metà: dal punti di metà alla fine
        end = [coastlineCoords[midPoint]]
        for vtxDist, coord in zip(vertexDistancies, coastlineCoords):
            if midDistance < vtxDist < coastlineLength:
                end.append(coord)
        
        start.append(coastlineCoords[-1])
        
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
    remainder_start = nSections * sectionLengthMetre
    remainder_length = coastlineLength - remainder_start

    if remainder_length >= minLengthMetre:
        startPoint = InterpolateGeodetic(coastlineCoords, remainder_start)
        endPoint = coastlineCoords[-1]

        innerLine = [startPoint]
        for vtxDist, coord in zip(vertexDistancies, coastlineCoords):
            if remainder_start < vtxDist < coastlineLength:
                innerLine.append(coord)
        innerLine.append(endPoint)

        sections.append({
            "geometry"    : LineString(innerLine),
            "sectionIndex": nSections,
            "startCoord"  : startPoint,
            "endCoord"    : endPoint,
            "lengthMetre" : remainder_length,
        })

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