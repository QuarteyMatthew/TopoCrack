# # ------------ Da Services/CoastlineService.py ------------
# logger = logging.getLogger(__name__)

# class CoastlineService:
    
#     _CachePath         = Path("Cache/NeturalEarthData")
#     _PicklePath        = Path("Cache/NormalizedSections.pkl")
#     _SectionLength     = 1_000_000 # 1000 km
#     _NPoints           = 50

#     @staticmethod
#     def LoadOrBuild() -> numpy.ndarray:
#         # ---- 1. Controlla che il pickle file esista nella cache ----
#         # Il file esiste: viene caricato dalla cache
#         if CoastlineService._PicklePath.exists():
#             fileSizeMb = CoastlineService._PicklePath.stat().st_size / 1_000_000
#             logger.info("Pickle cache found at '%s' (%.1f MB). Loading...",CoastlineService._PicklePath, fileSizeMb)
            
#             with open(CoastlineService._PicklePath, "rb") as f:
#                 data = pickle.load(f)
            
#             logger.info("Coastal data loaded from cache: %d sections.", len(data))
            
#             return data
        
#         # ---- 2. Il file non esiste (cache miss): esegue i coastline services ----
#         # Il file non esiste: viene riscaricato, diviso in sezioni e
#         # queste ultime tutte normalizzate
#         logger.info("Pickle not found at '%s'. Starting full build pipeline...", CoastlineService._PicklePath)
        
#         logger.info("Step 1/3: Downloading coastline data (resolution=10m)...")
#         coastlines = DownloadCoastline(resolution="10m", cacheDir=CoastlineService._CachePath)
#         logger.info("Step 1/3 complete: %d coastline features loaded.", len(coastlines))

#         logger.info("Step 2/3: Exploding coastlines into sections of %d km...", CoastlineService._SectionLength // 1000)
#         sections = ExplodeToSections(coastlines, sectionLengthMetre=CoastlineService._SectionLength)
#         logger.info("Step 2/3 complete: %d sections created.", len(sections))

#         logger.info("Step 3/3: Normalizing all sections (%d points each)...", CoastlineService._NPoints)
#         normalized = NormalizeAllSections(sections, nPoints=CoastlineService._NPoints)
#         validCount = sum(1 for s in normalized if s["points"] is not None)
#         logger.info("Step 3/3 complete: %d sections normalized (%d valid, %d degenerate).", len(normalized), validCount, len(normalized) - validCount)
        
#         # ---- 2.2. Visualizza il risultato dei coastline services ----
#         # VisualizeCoastline(coastlines, normalized)
        
#         # ---- 3. Legge, carica e restitusce i dati del pickle file ----
#         logger.info("Saving normalized coastal data to '%s'...", CoastlineService._PicklePath)
        
#         CoastlineService._PicklePath.parent.mkdir(parents=True, exist_ok=True)
#         with open(CoastlineService._PicklePath, "wb") as f:
#             pickle.dump(normalized, f)
            
#         savedSizeMb = CoastlineService._PicklePath.stat().st_size  / 1_000_000
#         logger.info("Pickle saved successfully (%.1f MB). Returning %d sections.", savedSizeMb, len(normalized))
        
#         return normalized

# # CoastlineService.LoadOrBuild()

# # ------------ Da Services/_CoastlineProcessing.py ------------
# def ExplodeToSections(coastlines: GeoDataFrame, sectionLengthMetre: int) -> GeoDataFrame:
#     logger.info("Exploding %d coastline features into sections of %d km each...", len(coastlines), sectionLengthMetre // 1000)
    
#     featureIndecies = []
#     skippedFeatures = 0
    
#     # Elaborazione di ogni coastline
#     for featIndex, coastline in coastlines.iterrows():
#         segments = ExplodeToGeodeticSegments(coastline.geometry, sectionLengthMetre)

#         if len(segments) == 0:
#             # Una coastline che non produce sezioni è anomala ma non fatale
#             skippedFeatures += 1
#             logger.debug("Feature %d produced no sections (geometry may be too short or empty).", featIndex)
#             continue

#         for segment in segments:
#             featureIndecies.append({"featureIndex": featIndex, **segment})

#         logger.debug("Feature %d, %d section(s).", featIndex, len(segments))

#     logger.info("Exploding complete: %d sections created, %d features skipped.", len(featureIndecies), skippedFeatures,)
    
#     return GeoDataFrame(featureIndecies, crs=coastlines.crs).reset_index(drop=True)

# def NormalizeAllSections(sections: GeoDataFrame, nPoints: int) -> numpy.ndarray:
#     total = len(sections)
#     logger.info("Normalizing %d sections to [0,1] × [-y,y] space (%d points each)...", total, nPoints)
    
#     results = []
#     skippedCount = 0
    
#     for idx, (_, section) in enumerate(sections.iterrows()):
#         # Log di avanzamento ogni 10%: utile perché questa funzione
#         # può girare per diversi minuti sul dataset mondiale a 10m.
#         if total > 0 and idx % max(1, total // 10) == 0:
#             logger.info("  Normalization progress: %d/%d (%.0f%%)...", idx, total, 100 * idx / total)
        
#         try:
#             # Normalizza questa sezione allo spazio [0,1] × [-y,y]
#             points = SectionToNormalizedPoints(section.geometry, nPoints)
            
#         except ValueError as e:
#             # Skip delle sezioni degenere
#             skippedCount += 1
#             logger.warning("Skipped degenerate section (feature=%s, section=%s): %s", section.featureIndex, section.sectionIndex, e,)
#             points = None
        
#         results.append({
#             "featureIndex": section.featureIndex, # Original feature ID
#             "sectionIndex": section.sectionIndex, # Section number within feature
#             "startCoord"  : section.startCoord,   # Original WGS84 start (for visualization)
#             "endCoord"    : section.endCoord,     # Original WGS84 end (for visualization)
#             "points"      : points,               # Normalized points or None if failed
#         })
    
#     logger.info("Normalization complete: %d sections normalized, %d skipped.", total - skippedCount, skippedCount,)
    
#     return numpy.array(results)

# def ExplodeToGeodeticSegments(coastline: LineString, sectionLengthMetre: int) -> numpy.ndarray:
#     if coastline is None or coastline.is_empty:
#         return numpy.array([])
    
#     # Se le coastline sono dio tipi 'MultiLineString', vengono fuse tutte in una 'LineString'
#     if coastline.geom_type == "MultiLineString":    
#         # Se le coastline sono connesse le loro 'LineString' vengono fuse
#         logger.debug("Geometry is MultiLineString, attempting merge...")
#         coastline = linemerge(coastline)
        
#         # Invece, se sono disconnesse, tenta il fallback per fonderle tramite una chiamata ricorsiva
#         if coastline.geom_type == "MultiLineString":
#             subGeomCount = len(list(coastline.geoms))
#             logger.debug("Merge failed (disconnected sub-geometries). Falling back to recursive split on %d parts.", subGeomCount,)
            
#             sections = []
#             for sectionPart in coastline.geoms:
#                 sections.extend(ExplodeToGeodeticSegments(sectionPart, sectionLengthMetre))
            
#             return numpy.array(sections)
            
#     coastlineLength = abs(geodCalc.geometry_length(coastline))
#     coastlineCoords = list(coastline.coords)
    
#     # Discard delle sezioni più corte di 1/5 della lunghezza della sezione ('sectionLengthMetre')
#     minLengthMetre = sectionLengthMetre / 5
#     if coastlineLength < minLengthMetre:
#         logger.debug("Coastline too short (%.0f m < %.0f m minimum), discarding.", coastlineLength, minLengthMetre)
#         return numpy.array([])
    
#     # Pre-calcola la distanza cumulativa tra i vertici
#     vertexDistancies = [0.0]
#     for i in range(len(coastlineCoords) - 1):
#         _, _, segmentLength = geodCalc.inv(*coastlineCoords[i], *coastlineCoords[i + 1])
#         vertexDistancies.append(vertexDistancies[-1] + segmentLength)
        
#     # Le coastline di lunghezza inferiore ad 1/5 della lungezza della sezione ma superiore
#     # al minimo, vengono divise a metà e ricavate due sezioni distinte
#     if coastlineLength < sectionLengthMetre:
#         logger.debug("Short coastline (%.0f m): splitting into 2 half-sections.", coastlineLength)
        
#         midDistance = coastlineLength / 2
#         midPoint = InterpolateGeodetic(coastlineCoords, midDistance)

#         # Prima metà: dall'inizio al punto di metà
#         start = [coastlineCoords[0]]
#         for vtxDist, coord in zip(vertexDistancies, coastlineCoords):
#             if 0 < vtxDist < midDistance:
#                 start.append(coord)
        
#         start.append(midPoint)
        
#         # Seconda metà: dal punti di metà alla fine
#         end = [midPoint]
#         for vtxDist, coord in zip(vertexDistancies, coastlineCoords):
#             if midDistance < vtxDist < coastlineLength:
#                 end.append(coord)
        
#         end.append(coastlineCoords[-1])
        
#         return numpy.array([
#             {
#                 "geometry"    : LineString(start),
#                 "sectionIndex": 0,
#                 "startCoord"  : coastlineCoords[0],
#                 "endCoord"    : midPoint,
#                 "lengthMetre" : midDistance,
#             },
#             {
#                 "geometry"    : LineString(end),
#                 "sectionIndex": 1,
#                 "startCoord"  : midPoint,
#                 "endCoord"    : coastlineCoords[-1],
#                 "lengthMetre" : coastlineLength - midDistance,
#             },
#         ])
        
#     nSections = int(coastlineLength // sectionLengthMetre)
#     remainderLength = coastlineLength - nSections * sectionLengthMetre
#     logger.debug("Coastline %.0f m → %d full section(s) + remainder %.0f m.", coastlineLength, nSections, remainderLength)
    
#     sections = []

#     for i in range(nSections):
#         startDistance = i * sectionLengthMetre
#         endDistance = startDistance + sectionLengthMetre

#         startPoint = InterpolateGeodetic(coastlineCoords, startDistance)
#         endPoint = InterpolateGeodetic(coastlineCoords, endDistance)

#         innerLine = [startPoint]
#         for vtxDist, coord in zip(vertexDistancies, coastlineCoords):
#             if startDistance < vtxDist < endDistance:
#                 innerLine.append(coord)
#         innerLine.append(endPoint)

#         sections.append({
#             "geometry"    : LineString(innerLine),
#             "sectionIndex": i,
#             "startCoord"  : startPoint,
#             "endCoord"    : endPoint,
#             "lengthMetre" : sectionLengthMetre,
#         })

#     # Gestisce il resto dopo l'ultimo intervallo completo
#     remainderStart = nSections * sectionLengthMetre
#     remainderLength = coastlineLength - remainderStart

#     if remainderLength >= minLengthMetre:
#         startPoint = InterpolateGeodetic(coastlineCoords, remainderStart)
#         endPoint = coastlineCoords[-1]

#         innerLine = [startPoint]
#         for vtxDist, coord in zip(vertexDistancies, coastlineCoords):
#             if remainderStart < vtxDist < coastlineLength:
#                 innerLine.append(coord)
#         innerLine.append(endPoint)

#         sections.append({
#             "geometry"    : LineString(innerLine),
#             "sectionIndex": nSections,
#             "startCoord"  : startPoint,
#             "endCoord"    : endPoint,
#             "lengthMetre" : remainderLength,
#         })
#     else:
#         logger.debug("Remainder section discarded (%.0f m < %.0f m minimum).", remainderLength, minLengthMetre)

#     return numpy.array(sections)

# def SectionToNormalizedPoints(line: LineString, nPoints: int) -> numpy.ndarray:
#     # Trova la longitudine centrale di questa sezione
#     lonCenter = numpy.mean([c[0] for c in line.coords])
    
#     # Project per UTM locale: gradi lon/lat → metri
#     # Utilizza un GeoDataFrame temporaneo per sfruttare la proiezione di geopandas
#     utmGeodeticFrame = geopandas.GeoDataFrame(geometry=[line], crs="EPSG:4326")
#     utmGeodeticFrame = utmGeodeticFrame.to_crs(GetUtmCrsFormGivenLongitude(lonCenter))
#     lineLengthMetre = utmGeodeticFrame.geometry.iloc[0]

#     # Campiona in 'nPoints' uniformemente lungo la linea
#     distances = numpy.linspace(0, lineLengthMetre.length, nPoints)
#     points = numpy.array([[lineLengthMetre.interpolate(distance).x, lineLengthMetre.interpolate(distance).y] 
#                           for distance in distances])

#     # Step 1: Translate so start point is at origin
#     points -= points[0]

#     # Passaggio 2 e 3: ruotare in modo che il punto finale si trovi sull'asse x positivo
#     # Calcola l'angolo di rotazione per allineare il punto finale all'asse x
#     angle = numpy.arctan2(points[-1, 1], points[-1, 0])
#     cos, sin = numpy.cos(-angle), numpy.sin(-angle)
    
#     # Applica la matrice di rotazione: [[cos, -sin], [sin, cos]]
#     rotationMatrix = numpy.array([[cos, -sin], [sin, cos]])
#     points = (rotationMatrix @ points.T).T

#     # Applica y=0 all'inizio e alla fine (numerical cleanup)
#     points[0,  1] = 0.0
#     points[-1, 1] = 0.0

#     # Passaggio 4: ridimensiona in modo che x vari da 0 a 1
#     startToEndDistanceX = points[-1, 0]  # Distanza dall'inizio alla fine lungo l'asse x
#     if startToEndDistanceX < 1e-10:
#         raise ValueError("Degenerate section: start and end coincide")

#     return points / startToEndDistanceX