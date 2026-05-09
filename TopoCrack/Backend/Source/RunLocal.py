"""
Esecuzione locale della pipeline completa senza avviare il server FastAPI.
Utile per testare l'intero flusso end-to-end su un'immagine reale.

Eseguire con:
    python RunLocal.py
"""

import logging

from pathlib import Path
from Services.CoastlineService import CoastlineService
from Services.ImageService import ImageService
from Services.DtwService import DtwService
from Schemas.AnalysisSchemas import Point

logging.basicConfig(level=logging.INFO, format="[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s", datefmt="%H:%M:%S")

# --------------- 1. Carica (o rigenera) i dati costieri ---------------
# Questa è esattamente la stessa chiamata che fa il lifespan del server.
print("========= Phase 1: Loading of caostal data =========")
coastalData = CoastlineService.LoadOrBuild()
print(f"Loaded sections: {len(coastalData)}\n")

# --------------- 2. Carica l'immagine di test ---------------
# Leggiamo i byte dal disco — identico a come arrivano via HTTP.
print("========= Phase 2: image processing =========")
imagePath = Path("Resources/crack10.jpg")
imageBytes = imagePath.read_bytes()

# Modifica questi valori in base all'immagine che stai testando.
userStart = Point(X=320, Y=100)
userEnd   = Point(X=480, Y=400)

crackPoints = ImageService.ExtractCrackPoints(imageBytes, userStart, userEnd)
print(f"Points extracted from the crack: {len(crackPoints)}\n")

# --------------- 3. DTW e ricerca del best match ---------------
print("========= Phase 3: DTW =========")
bestMatch = DtwService.FindBestMatch(crackPoints, coastalData)

print("\n========= Risultato =========")
print(f"Feature index : {bestMatch["featureIndex"]}")
print(f"Section index : {bestMatch["sectionIndex"]}")
print(f"DTW score     : {bestMatch["cost"]:.6f}")
print(f"Start coord   : {bestMatch["startCoord"]}")
print(f"End coord     : {bestMatch["endCoord"]}")