# Analizzatore di Crepe — Guida di Riferimento Completa

---

## ARCHITETTURA GENERALE

- **Backend**: Python, esposto come REST API
- **Frontend**: Flutter (iOS, Android, Desktop, Web da un unico codebase)
- **Comunicazione**: HTTP POST — Flutter invia l'immagine → Python risponde con JSON (risultato + path immagine costa)
- **Deploy backend**: Server (es. Railway, Render, VPS con Ubuntu) — il processing NON va sul client
- **Framework API Python**: `FastAPI` + `uvicorn`

---

## PARTE 1 — BACKEND PYTHON

### FASE 1: Ricezione e pre-processing dell'immagine

1. **Ricezione immagine via API**
   - Libreria: `FastAPI`
   - Funzione: endpoint `POST /analyze` che riceve il file come `UploadFile`
   - Converti i bytes in array numpy con `numpy.frombuffer()` + `cv2.imdecode()`

2. **Conversione in scala di grigi**
   - Libreria: `OpenCV` (`cv2`)
   - Funzione: `cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)`

3. **Equalizzazione adattiva del contrasto (CLAHE)**
   - Libreria: `OpenCV`
   - Funzione: `cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8,8))` → `.apply(img_gray)`
   - Scopo: uniforma l'illuminazione non omogenea nelle foto di crepe

4. **Riduzione del rumore**
   - Libreria: `OpenCV`
   - Funzione: `cv2.GaussianBlur(img, (5,5), 0)` oppure `cv2.bilateralFilter()`
   - Il bilateralFilter è più lento ma preserva meglio i bordi netti

5. **Edge detection (rilevamento bordi)**
   - Libreria: `OpenCV`
   - Funzione: `cv2.Canny(img, threshold1=50, threshold2=150)`
   - I due valori di soglia vanno calibrati — inizia con 50/150, poi aggiusta
   - Alternativa più robusta: calcola le soglie automaticamente con la mediana del pixel: `lower = 0.66 * median`, `upper = 1.33 * median`

6. **Chiusura morfologica (closing)**
   - Libreria: `OpenCV`
   - Funzione: `cv2.morphologyEx(edges, cv2.MORPH_CLOSE, kernel)`
   - Scopo: chiude i piccoli gap nella linea della crepa
   - Kernel consigliato: `cv2.getStructuringElement(cv2.MORPH_RECT, (3,3))`

---

### FASE 2: Estrazione del profilo della crepa

7. **Skeletonization (assottigliamento a 1 pixel)**
   - Libreria: `scikit-image`
   - Funzione: `skimage.morphology.skeletonize(binary_img)`
   - Input: immagine binaria (0/255) → Output: linea da 1px
   - Converte in bool prima: `img.astype(bool)`

8. **Estrazione del ramo principale (path più lungo)**
   - Libreria: `scikit-image` + `networkx`
   - Procedura:
     - `skimage.morphology.skeletonize()` produce uno scheletro ramificato
     - Usa `sknw` (libreria per convertire skeleton in grafo) oppure implementa un BFS/DFS manuale sui pixel
     - Trova i due nodi terminali più distanti con `networkx.shortest_path()`
     - Tieni solo quel path, scarta i rami secondari

9. **Ricampionamento a N punti equidistanti**
   - Libreria: `numpy` + `scipy`
   - Procedura:
     - Calcola la lunghezza cumulativa del path con `numpy.cumsum(numpy.linalg.norm(diff, axis=1))`
     - Interpola con `scipy.interpolate.interp1d()` per ottenere N punti equispaziati lungo la curva
     - N consigliato: 100–256 punti (trovare il giusto trade-off velocità/precisione)

---

### FASE 3: Normalizzazione (standardizzazione della curva)

10. **Centratura della curva**
    - Sposta la curva in modo che il suo centroide sia nell'origine (0,0)
    - Calcola il centroide come media di tutti i punti: `centroid = points.mean(axis=0)`
    - Sottrai il centroide: `points -= centroid`
    - ⚠️ Non usare il primo punto come origine: per curve con concavità il centroide è più stabile e rappresentativo

11. **Rotazione (allineamento asse con PCA sull'intera nuvola di punti)**
    - Libreria: `numpy` (senza scikit-learn, è più diretto)
    - Procedura:
      - Calcola la matrice di covarianza: `cov = numpy.cov(points.T)`
      - Calcola autovettori: `eigenvalues, eigenvectors = numpy.linalg.eigh(cov)`
      - L'autovettore con autovalore maggiore è l'asse principale della curva
      - Ruota: `points_rotated = points @ eigenvectors[:, ::-1]`
    - Questo funziona correttamente anche per curve con golfi e concavità profonde, perché considera l'intera forma e non solo gli estremi
    - ⚠️ NON allineare usando solo il primo e l'ultimo punto: per curve non-funzione (golfi, S) quei due punti non rappresentano l'orientamento reale della curva

12. **Normalizzazione della scala**
    - Dividi tutti i punti per la lunghezza totale della curva → la curva ha lunghezza 1
    - Lunghezza totale: `numpy.sum(numpy.linalg.norm(numpy.diff(points, axis=0), axis=1))`

13. **Gestione dell'ambiguità inizio/fine**
    - La crepa potrebbe essere stata fotografata "al contrario"
    - Salva sempre anche la versione ribaltata: `points_flipped = points[::-1]`
    - Durante il confronto DTW, prova entrambe le versioni e prendi il punteggio minore

---

### FASE 4: Preparazione del database costiero

14. **Download dataset costiero**
    - Fonte consigliata per iniziare: **Natural Earth** → `naturalearthdata.com`
    - File da scaricare: `ne_10m_coastline.zip` (scala 1:10 milioni, formato Shapefile)
    - Alternativa più dettagliata: **GSHHG** → `ngdc.noaa.gov/mgg/shorelines/` (formato Shapefile)

15. **Lettura e parsing del dataset**
    - Libreria: `geopandas`
    - Funzione: `geopandas.read_file("ne_10m_coastline.shp")`
    - Restituisce un GeoDataFrame con geometrie `LineString` e `MultiLineString`

16. **Segmentazione della costa in tratti**
    - Libreria: `shapely`
    - Procedura:
      - Itera su ogni `LineString` del GeoDataFrame
      - Taglia ogni linea in segmenti di lunghezza fissa (es. 100 km) con `shapely.ops.substring(line, start, end, normalized=False)`
      - Scarta i tratti troppo corti (< 20 km) o troppo rettilinei (poco interessanti)

17. **Conversione tratti costieri in array di punti normalizzati**
    - Applica la stessa pipeline dei punti 9–13 a ogni tratto costiero
    - Salva ogni tratto pre-processato in un file `.npy` con `numpy.save()`
    - Organizza i file in cartelle per area geografica

18. **Costruzione dell'indice del database**
    - Salva un file `index.json` con: `{id, nome_zona, lat_min, lat_max, lon_min, lon_max, path_file_npy}`
    - Utile per il pre-filtering geografico

---

### FASE 5: Confronto e ricerca della costa simile

19. **Pre-filtering (eliminare candidati ovviamente diversi)**
    - Prima del DTW (costoso), filtra i tratti in modo rapido con la **curvatura totale**
    - Procedura:
      - Per ogni curva calcola gli angoli tra segmenti successivi: `angles = numpy.arctan2(numpy.diff(points[:,1]), numpy.diff(points[:,0]))`
      - Calcola la variazione angolare cumulativa: `total_curvature = numpy.sum(numpy.abs(numpy.diff(angles)))`
      - Questo valore è un numero solo, confrontabile in O(1)
    - Due curve con curvatura totale molto diversa (es. differenza > 30%) non si somiglieranno mai → scartale senza fare DTW
    - Tieni solo i top-K candidati per curvatura più simile (es. top 200)

20. **Dynamic Time Warping (DTW)**
    - Libreria: `dtaidistance` (veloce, implementazione C) oppure `tslearn`
    - Installazione: `pip install dtaidistance`
    - Funzione: `dtaidistance.dtw.distance(serie_a, serie_b)`
    - Applica DTW separatamente su coordinate X e Y, oppure su curva 2D
    - Per 2D: `dtaidistance.dtw_ndim.distance(points_a, points_b)`
    - Prova anche la versione ribaltata (punto 13) e tieni il minimo

21. **Restituzione dei risultati**
    - Ordina i candidati per distanza DTW crescente
    - Restituisce i **top 3** risultati come JSON:
      ```json
      [{"id": "...", "nome": "Costa Amalfitana", "score": 0.043, "immagine_url": "..."}]
      ```

---

### FASE 6: API Backend

22. **Struttura FastAPI**
    - Libreria: `fastapi` + `uvicorn` + `python-multipart`
    - Endpoint principale: `POST /analyze` — riceve immagine, restituisce JSON con top 3 coste
    - Endpoint accessorio: `GET /coast/{id}/image` — restituisce l'immagine del tratto costiero
    - Avvio: `uvicorn main:app --host 0.0.0.0 --port 8000`

23. **Gestione immagini delle coste (per la visualizzazione)**
    - Genera un'immagine PNG di ogni tratto costiero con `matplotlib.pyplot`
    - Salvale in una cartella `static/` servita da FastAPI con `StaticFiles`
    - Funzione: `app.mount("/static", StaticFiles(directory="static"), name="static")`

---

## PARTE 2 — FRONTEND FLUTTER

24. **Struttura progetto Flutter**
    - Comando: `flutter create crack_analyzer`
    - Supporto piattaforme: `flutter create --platforms=ios,android,macos,windows,linux,web .`
    - Linguaggio: Dart

25. **Selezione/scatto dell'immagine**
    - Package: `image_picker` (pub.dev)
    - Funzione: `ImagePicker().pickImage(source: ImageSource.camera)` oppure `ImageSource.gallery`

26. **Invio immagine al backend**
    - Package: `http` oppure `dio` (più completo)
    - Usa `MultipartRequest` per inviare il file:
      ```dart
      var request = http.MultipartRequest('POST', Uri.parse('$baseUrl/analyze'));
      request.files.add(await http.MultipartFile.fromPath('file', imagePath));
      var response = await request.send();
      ```

27. **Visualizzazione risultati affiancati**
    - Widget: `Row` con due `Expanded` → uno mostra la foto della crepa, l'altro la foto della costa
    - Per caricare immagini da URL: `Image.network(url)`
    - Per mostrare l'immagine locale scattata: `Image.file(File(path))`

28. **Gestione degli stati dell'app**
    - Package: `provider` oppure `riverpod` (più moderno)
    - Stati da gestire: `idle`, `loading`, `success`, `error`
    - Mostra `CircularProgressIndicator()` durante l'elaborazione

29. **UI — schermate principali**
    - `HomeScreen`: bottone per caricare/scattare foto
    - `ResultScreen`: visualizzazione crepa + costa affiancate, lista top 3 risultati
    - Navigazione: `Navigator.push()` oppure `GoRouter` per routing dichiarativo

---

## PARTE 3 — LIBRERIE RIEPILOGO

| Scopo | Libreria | Installazione |
|---|---|---|
| API REST | `fastapi` + `uvicorn` | `pip install fastapi uvicorn python-multipart` |
| Computer Vision | `opencv-python` | `pip install opencv-python` |
| Skeletonization | `scikit-image` | `pip install scikit-image` |
| Analisi grafo skeleton | `sknw` | `pip install sknw` |
| Dati geografici | `geopandas` | `pip install geopandas` |
| Geometrie | `shapely` | incluso in geopandas |
| DTW | `dtaidistance` | `pip install dtaidistance` |
| Array e math | `numpy` | `pip install numpy` |
| Interpolazione | `scipy` | `pip install scipy` |
| PCA/rotazione | `numpy` | già incluso |
| Grafici coste | `matplotlib` | `pip install matplotlib` |
| Selezione immagine (Flutter) | `image_picker` | `flutter pub add image_picker` |
| HTTP (Flutter) | `dio` | `flutter pub add dio` |
| State management (Flutter) | `riverpod` | `flutter pub add flutter_riverpod` |

---

## PARTE 4 — DATASET COSTIERI

| Nome | URL | Formato | Note |
|---|---|---|---|
| Natural Earth 1:10m | naturalearthdata.com | Shapefile / GeoJSON | Inizia da qui, facile |
| GSHHG | ngdc.noaa.gov/mgg/shorelines | Shapefile | Alta risoluzione, standard scientifico |
| OpenStreetMap | geofabrik.de | PBF / GeoJSON | Per aree specifiche |
| EUROSION | eea.europa.eu | Shapefile | Solo coste europee, molto dettagliato |

---

## PARTE 5 — ORDINE DI SVILUPPO CONSIGLIATO

**Mese 1**
- [ ] Installa Python, OpenCV, scikit-image
- [ ] Scrivi la pipeline CV in un Jupyter Notebook (passi 1–9)
- [ ] Testa su 5-10 foto di crepe diverse
- [ ] Scarica Natural Earth, segmenta le coste, costruisci il database (passi 14–18)

**Mese 2**
- [ ] Implementa normalizzazione completa (passi 10–13)
- [ ] Implementa pre-filtering e DTW (passi 19–20)
- [ ] Crea il backend FastAPI (passi 22–23)
- [ ] Testa il sistema end-to-end da Postman o curl

**Mese 3**
- [ ] Sviluppa l'app Flutter (passi 24–29)
- [ ] Collega Flutter al backend
- [ ] Deploy del backend su server
- [ ] Test su dispositivi reali, rifinitura UI
