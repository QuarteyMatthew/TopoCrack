# TopoCrack — Documentazione Backend

> _"Ogni crepa racconta una storia geologica. TopoCrack la confronta con le coste del mondo per capire dove si è formata."_

---

## Indice

1. [Panoramica del progetto](#panoramica-del-progetto)
2. [Come funziona — il flusso completo](#come-funziona--il-flusso-completo)
3. [Struttura del progetto](#struttura-del-progetto)
4. [Componenti principali](#componenti-principali)
    - [Server.py — Il punto di ingresso](#serverpy--il-punto-di-ingresso)
    - [CoastlineService — La memoria delle coste](#coastlineservice--la-memoria-delle-coste)
    - [\_CoastlineProcessing — Il motore geografico](#_coastlineprocessing--il-motore-geografico)
    - [DtwService — Il cuore del confronto](#dtwservice--il-cuore-del-confronto)
    - [DtwCore.c — La velocità della macchina](#dtwcorec--la-velocità-della-macchina)
    - [ImageService — Leggere la crepa](#imageservice--leggere-la-crepa)
    - [AnalysisRoutes — L'interfaccia HTTP](#analysisroutes--linterfaccia-http)
    - [AnalysisSchemas — I contratti dei dati](#analysisschemas--i-contratti-dei-dati)
5. [Pipeline di analisi — passo dopo passo](#pipeline-di-analisi--passo-dopo-passo)
6. [Dataset delle coste — costruzione multi-scala](#dataset-delle-coste--costruzione-multi-scala)
7. [L'algoritmo DTW 2D — spiegazione intuitiva](#lalgoritmo-dtw-2d--spiegazione-intuitiva)
8. [Cache e avvio del server](#cache-e-avvio-del-server)
9. [Script di supporto](#script-di-supporto)
10. [Avvio rapido (Quick Start)](#avvio-rapido-quick-start)

---

## Panoramica del progetto

TopoCrack è un backend FastAPI che riceve l'immagine di una **crepa su una superficie rocciosa**, individua il tracciato della frattura e lo confronta — tramite l'algoritmo **DTW (Dynamic Time Warping)** — con milioni di finestre estratte dalle coste mondiali (Natural Earth). L'output è la porzione di costa il cui profilo assomiglia di più alla crepa analizzata, con le sue coordinate geografiche.

L'intuizione di fondo è affascinante: la morfologia delle fratture geologiche può ricordare quella delle linee costiere, formate dagli stessi processi di erosione e tensione. TopoCrack sfrutta questa somiglianza in modo computazionale.

---

## Come funziona — il flusso completo

```
Immagine della crepa
        │
        ▼
  ImageService                  estrae i punti del tracciato
        │
        ▼
  DtwService._PreparePoints     trasla, ruota e scala i punti [0,1]
        │
        ├──► versione normale
        └──► versione specchiata + rovesciata  (gestisce l'ambiguità di orientamento)
        │
        ▼
  DtwService.FindBestMatch      confronta con TUTTI i milioni di finestre costiere
        │   (loop su coastalData, chiama DtwCore.c in C nativo)
        │
        ▼
  Finestra più simile           con featureIndex, windowIndex, startCoord, endCoord
        │
        ▼
  AnalysisRoutes                costruisce e restituisce AnalysisResponse (JSON)
```

---

## Struttura del progetto

```
Backend/
├── Dependencies.txt              # dipendenze pip
├── TopoCrack.toml                # configurazione del progetto
│
├── Scripts/
│   ├── BuildNative.py            # compila DtwCore.c → .dll/.so/.dylib
│   └── InstallDependencies.py    # installa le dipendenze
│
└── Source/
    ├── Server.py                 # entry point FastAPI + lifespan
    ├── RunLocal.py               # avvio in sviluppo locale
    │
    ├── Cache/
    │   ├── NormalizedSections.pkl         # dataset pre-calcolato delle finestre
    │   └── NeturalEarthData/
    │       └── ne_10m_coastline/
    │           ├── ne_10m_coastline.shp   # geometrie delle coste (Natural Earth)
    │           └── ne_10m_coastline.shx   # indice spaziale
    │
    ├── Resource/                 # immagini di crepe (input di test)
    │
    ├── Routes/
    │   └── AnalysisRoutes.py     # endpoint POST /api/analyze
    │
    ├── Schemas/
    │   └── AnalysisSchemas.py    # modelli Pydantic (request/response)
    │
    ├── Services/
    │   ├── CoastlineService.py   # caricamento e cache del dataset costiero
    │   ├── DtwService.py         # DTW + preparazione punti + visualizzazione
    │   ├── ImageService.py       # estrazione punti della crepa dall'immagine
    │   ├── _CoastlineProcessing.py  # download, ricampionamento, finestre costiere
    │   │
    │   └── Native/
    │       ├── DtwCore.c         # implementazione C del DTW 2D
    │       └── Build/
    │           ├── Binaries-Intermediates/
    │           │   └── DtwCore.obj
    │           └── Libraries/
    │               ├── DtwCore.dll    # Windows
    │               ├── DtwCore.exp
    │               └── DtwCore.lib
    │
    └── Utils/
        └── Timer.py              # utilità per misurare i tempi
```

---

## Componenti principali

### Server.py — Il punto di ingresso

`Server.py` è il file che istanzia l'applicazione FastAPI e ne gestisce il ciclo di vita tramite il context manager asincrono `Lifespan`. La scelta del **lifespan** (invece del classico `@app.on_event`) è moderna e preferibile: garantisce che il server si blocchi durante il caricamento dei dati, rifiutando richieste prima di essere pronto.

All'avvio, il server carica (o rigenera) il dataset delle coste normalizzate, salvandolo in `server.state.CoastalData`. Questo oggetto — un `numpy.ndarray` di milioni di finestre — vive in memoria per tutta la durata del processo, evitando il costo di ricaricarlo a ogni richiesta. Se il caricamento fallisce, il server logga un errore `CRITICAL` e si rifiuta di avviarsi: non avrebbe senso accettare richieste senza il dato fondamentale.

```python
# Il server non parte senza i dati costieri: fail-fast by design.
server.state.CoastalData = CoastlineService.LoadCoastalData()
```

---

### CoastlineService — La memoria delle coste

`CoastlineService` è il custode del dataset. La sua responsabilità principale è `LoadCoastalData()`, che segue questa logica semplice ma efficace:

- Se `Cache/NormalizedSections.pkl` esiste → lo carica e lo restituisce immediatamente (millisecondi).
- Se non esiste → scarica le coste da Natural Earth, costruisce tutte le finestre e salva il pickle per le esecuzioni future.

Il dataset viene costruito a **sei scale geografiche diverse**, raddoppiando ogni volta la spaziatura tra i punti. Questo è fondamentale: una crepa di 10 cm su roccia potrebbe corrispondere a una costa che a una certa scala appare come una curva dolce, e a un'altra come una sequenza di frastagliature. Il confronto multi-scala copre questa ambiguità.

| Build | Spaziatura punti | Lunghezza fisica finestra |
| ----- | ---------------- | ------------------------- |
| 1     | 5 km             | 250 km                    |
| 2     | 10 km            | 500 km                    |
| 3     | 20 km            | 1 000 km                  |
| 4     | 50 km            | 2 500 km                  |
| 5     | 100 km           | 5 000 km                  |
| 6     | 200 km           | 10 000 km                 |

> Tutte le finestre sono normalizzate a **50 punti** indipendentemente dalla scala: il confronto DTW è quindi sempre equo tra build diverse.

---

### \_CoastlineProcessing — Il motore geografico

Questo modulo privato (il prefisso `_` indica che non va importato direttamente) contiene tutta la matematica geografica del progetto. Vale la pena capire ogni funzione:

**`DownloadCoastline`** scarica lo shapefile Natural Earth dalla risoluzione richiesta (tipicamente `10m`, cioè alta precisione) e lo scompatta nella cache locale. Gestisce la cache in modo idempotente: se i file esistono già, non scarica nulla.

**`ResampleCoastlineToPoints`** converte una `LineString` geografica in un array di punti equispaziati usando il **calcolo geodetico WGS84** (non la geometria euclidea, che sarebbe imprecisa su scala globale). La libreria `pyproj` con `Geod(ellps="WGS84")` si occupa di misurare le distanze lungo l'ellissoide terrestre.

**`GenerateSlidingWindows`** scorre la sequenza di punti con una finestra scorrevole di dimensione fissa (`windowSize = 50`) e un passo (`stride = 3`), estraendo ogni sotto-sequenza come una finestra candidata.

**`WindowToNormalizedPoints`** è il cuore della normalizzazione: proietta la finestra in un sistema UTM locale (per avere coordinate in metri), poi applica tre trasformazioni — traslazione all'origine, rotazione per allineare il punto finale all'asse x positivo, e scala per portare x nell'intervallo `[0, 1]`. Il risultato è una curva "canonica" confrontabile con qualsiasi altra.

---

### DtwService — Il cuore del confronto

`DtwService` gestisce tutto il processo di confronto tra la crepa e il dataset. Il metodo principale `FindBestMatch` riceve i punti grezzi della crepa e l'intero dataset costiero, e restituisce la finestra con il costo DTW più basso.

**Preparazione della crepa (`_PreparePoints`):** applica la stessa normalizzazione usata per le coste — traslazione, rotazione, scala. Questo è essenziale: il confronto DTW ha senso solo se entrambe le sequenze vivono nello stesso spazio normalizzato `[0,1]`.

**Gestione dell'ambiguità di orientamento:** una crepa può essere letta da sinistra a destra o da destra a sinistra, e la costa corrispondente potrebbe avere l'orientamento opposto. Per gestirlo, `_MirrorAndReverseCrackPoints` genera una versione specchiata (y → −y) e rovesciata (l'ordine dei punti viene invertito) della crepa. Il confronto viene fatto con entrambe le versioni, tenendo il costo minore.

**Rilevamento della curvatura anomala:** se il rapporto tra la lunghezza del percorso e la lunghezza della corda supera 3.0, il servizio lancia un warning: significa che la crepa si arrotola su se stessa, e nessuna costa reale ha questa topologia. È un controllo di qualità intelligente che aiuta l'utente a riformulare la selezione.

```
curvatureRatio = pathLength / chordLength

Se > 3.0 → warning: la crepa è troppo "aggrovigliata" per un match affidabile
Se > 1.5 → warning leggero restituito nella risposta al frontend
```

---

### DtwCore.c — La velocità della macchina

Il DTW è un algoritmo O(n·m) in tempo e spazio, dove n e m sono le lunghezze delle due sequenze. Con milioni di finestre nel dataset, un'implementazione Python sarebbe troppo lenta. `DtwCore.c` implementa il DTW 2D in C puro, compilato come libreria condivisa (`.dll` su Windows, `.so` su Linux, `.dylib` su macOS) e caricato da Python via `ctypes`.

L'ottimizzazione più importante è l'**early exit con lower bound**: alla fine di ogni riga della matrice di costo, il codice calcola il minimo della riga. Se questo valore è già superiore al miglior costo trovato finora (`bestCost`), nessun percorso che attraversa quella riga potrà migliorare il risultato, e il calcolo si interrompe. Questo riduce drasticamente il numero di celle calcolate per le finestre "chiaramente peggiori".

```c
// Early exit: rowMin è un lower bound del costo finale.
// Se supera bestCost, questa finestra non può vincere.
if (rowMin >= bestCost) {
    free(costMatrix);
    return rowMin;
}
```

`DtwService` carica la libreria al momento dell'import del modulo (non a ogni richiesta), segnalando un errore `CRITICAL` se il file non esiste — in quel caso, il messaggio suggerisce di eseguire `BuildNative.py`.

---

### ImageService — Leggere la crepa

`ImageService.ExtractCrackPoints` riceve i byte grezzi dell'immagine e le coordinate dei due punti selezionati dall'utente (inizio e fine della crepa), e restituisce un `numpy.ndarray` di punti che tracciano il percorso della frattura. Il file sorgente non è incluso in questa documentazione, ma il suo output è il punto di ingresso per tutta la pipeline DTW.

---

### AnalysisRoutes — L'interfaccia HTTP

L'endpoint `POST /api/analyze` accetta un form multipart con:

- `image` — il file immagine della crepa
- `startX`, `startY` — coordinata pixel del punto iniziale selezionato dall'utente
- `endX`, `endY` — coordinata pixel del punto finale

e restituisce un JSON con le coordinate geografiche della costa più simile e il punteggio DTW. La gestione degli errori è strutturata in tre livelli distinti: errori di validazione (422), errori dell'image processing (422 o 500), errori del DTW (500). Ogni errore viene loggato al livello appropriato (`warning` vs `error`) per facilitare il debug in produzione.

---

### AnalysisSchemas — I contratti dei dati

I modelli Pydantic definiscono contratti chiari per request e response:

- **`AnalysisRequest`** — contiene i byte dell'immagine e i due punti pixel. Il validator `ImageMustNotBeEmpty` rifiuta immagini vuote prima ancora di entrare nel processing.
- **`AnalysisResponse`** — restituisce `StartCoord` e `EndCoord` (coordinate WGS84 lon/lat), il `DtwScore` (costo del match migliore, valori più bassi = match migliore), e un campo opzionale `Warning` per informare il frontend di anomalie nella crepa selezionata.

---

## Pipeline di analisi — passo dopo passo

Ecco cosa succede, nell'ordine, quando arriva una richiesta a `/api/analyze`:

**Passo 1 — Validazione:** Pydantic valida il form e i campi. Se l'immagine è vuota o i tipi sono sbagliati, risponde 422 immediatamente.

**Passo 2 — Estrazione punti:** `ImageService` analizza l'immagine e individua i pixel del tracciato della crepa tra i due punti indicati dall'utente.

**Passo 3 — Preparazione geometrica:** `DtwService._PreparePoints` normalizza i punti della crepa (traslazione → rotazione → scala). Viene anche generata la versione specchiata+rovesciata.

**Passo 4 — Controllo curvatura:** viene calcolato il `curvatureRatio`. Se è alto, viene preparato un messaggio di warning per il frontend.

**Passo 5 — Ricerca DTW:** il loop su `coastalData` confronta la crepa (nelle sue due versioni) con ogni finestra costiera usando `DtwCost2D` in C. La best cost viene aggiornata progressivamente, permettendo all'early exit di scartare le finestre peggiori sempre prima.

**Passo 6 — Restituzione:** le coordinate geografiche della finestra vincente vengono impacchettate in `AnalysisResponse` e restituite come JSON.

---

## Dataset delle coste — costruzione multi-scala

Il dataset viene costruito **una sola volta** e poi serializzato in `Cache/NormalizedSections.pkl`. La costruzione richiede tempo (download, ricampionamento geodetico, proiezione UTM, normalizzazione), ma una volta fatto, il server si avvia in pochi secondi caricando il pickle.

La struttura di ogni finestra è un dizionario Python con questi campi:

```python
{
    "featureIndex": int,          # indice della coastline in Natural Earth
    "windowIndex" : int,          # indice del primo punto nella sequenza
    "startCoord"  : (float, float),  # (lon, lat) del punto iniziale
    "endCoord"    : (float, float),  # (lon, lat) del punto finale
    "points"      : numpy.ndarray,   # array (50, 2) normalizzato in [0,1]
}
```

---

## L'algoritmo DTW 2D — spiegazione intuitiva

Il **Dynamic Time Warping** è un algoritmo per misurare la somiglianza tra due sequenze di punti che possono essere di lunghezza diversa o "sfasate" temporalmente. A differenza della distanza euclidea punto-per-punto, il DTW trova l'allineamento ottimale tra le sequenze, permettendo corrispondenze non lineari.

Pensa a due melodie della stessa canzone, una suonata più veloce dell'altra: la distanza euclidea direbbe che sono diverse, ma il DTW riconosce che sono la stessa melodia "stirata". Nel contesto di TopoCrack, la crepa e la costa possono avere la stessa forma generale ma con diversa "velocità" di curvatura — il DTW le abbina correttamente.

In 2D, ogni punto è un vettore `(x, y)`, e la distanza tra due punti è la distanza euclidea. La matrice di costo `(n+1) × (m+1)` si riempie con la programmazione dinamica, e il valore `costMatrix[n][m]` è il costo totale del percorso ottimale — cioè la "distanza DTW" tra le due sequenze.

Un costo basso significa alta somiglianza. Il match migliore è la finestra con il costo più basso tra tutte le milioni nel dataset.

---

## Cache e avvio del server

```
Prima esecuzione (cache assente):
    Server.py → CoastlineService.LoadCoastalData()
             → _CoastlineProcessing.DownloadCoastline()   [~30s, rete]
             → BuildSlidingWindowDataset() × 6 scale       [minuti, CPU]
             → pickle.dump() → Cache/NormalizedSections.pkl
             → server pronto

Esecuzioni successive (cache presente):
    Server.py → CoastlineService.LoadCoastalData()
             → pickle.load()                               [~2-5s, disco]
             → server pronto
```

Se si vuole rigenerare il dataset (ad esempio dopo aver cambiato i parametri di windowing), è sufficiente eliminare `Cache/NormalizedSections.pkl`.

---

## Script di supporto

**`Scripts/BuildNative.py`** compila `DtwCore.c` nella libreria condivisa appropriata per la piattaforma corrente. Va eseguito una volta prima di avviare il server per la prima volta, o dopo qualsiasi modifica a `DtwCore.c`.

```bash
# Dalla directory Backend/
python Scripts/BuildNative.py
```

**`Scripts/InstallDependencies.py`** legge `Dependencies.txt` e installa tutti i pacchetti Python necessari.

```bash
python Scripts/InstallDependencies.py
```

---

## Avvio rapido (Quick Start)

```bash
# 1. Installa le dipendenze
python Scripts/InstallDependencies.py

# 2. Compila la libreria nativa DTW
python Scripts/BuildNative.py

# 3. Avvia il server in sviluppo
#    (la prima volta costruirà il dataset delle coste — può richiedere alcuni minuti)
python Source/RunLocal.py
```

Il server sarà disponibile su `http://localhost:8000`. La documentazione interattiva dell'API è accessibile su `http://localhost:8000/docs` (Swagger UI generata automaticamente da FastAPI).

---

_Documentazione generata con il ❤️ per il progetto TopoCrack._
