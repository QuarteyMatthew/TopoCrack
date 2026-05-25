# TopoCrack — Guida al Codice

## Struttura del Progetto

```
topocrack/
├── lib/
│   ├── main.dart                  # Entry point, gestione tema chiaro/scuro
│   ├── screens/
│   │   ├── home_screen.dart       # Schermata principale con sfondo e controlli
│   │   ├── crack_editor_screen.dart # Editor: selezione punti crepa sulla foto
│   │   └── result_screen.dart     # Risultato: costa corrispondente + link Maps
│   └── widgets/
│       ├── top_bar.dart           # Barra superiore (folder, profilo, -)
│       ├── bottom_bar.dart        # Barra inferiore (segnalibro, camera, galleria)
│       └── user_menu.dart         # Dropdown menu utente
├── assets/
│   └── images/
│       ├── bg.jpg                 # Sfondo principale dell'app
│       └── logo.png               # Logo TopoCrack
├── android/app/src/main/
│   └── AndroidManifest.xml        # Permessi Android (camera, storage, internet)
├── ios/Runner/
│   └── Info.plist                 # Permessi iOS (camera, galleria, posizione)
└── pubspec.yaml                   # Dipendenze Flutter
```

## Dipendenze Principali

`image_picker` gestisce sia la fotocamera che la galleria. `url_launcher` apre Google Maps con le coordinate ricevute dal server. `http` servirà per le chiamate API al server di analisi. `permission_handler` gestisce i permessi a runtime su Android e iOS.

## Flusso dell'App

L'utente arriva sulla home con lo sfondo paesaggistico e i controlli in stile glassmorphism. Può premere il tasto camera per scattare una foto o il tasto galleria per sceglierne una. Nella schermata editor tocca prima il punto di inizio della crepa (indicatore verde A) e poi il punto di fine (indicatore rosso B). Appare il bottone Analizza Crepa che invierà i dati al server. La schermata risultato mostra l'anteprima con la linea disegnata, il nome della costa e il pulsante per aprire Maps.


## API Keys

Per Google Maps su Android aggiungere in AndroidManifest.xml dentro `<application>`:
`<meta-data android:name="com.google.android.geo.API_KEY" android:value="LA_TUA_KEY"/>`

Per iOS aggiungere in `ios/Runner/AppDelegate.swift` prima di `super.application`:
`GMSServices.provideAPIKey("LA_TUA_KEY")`

## Tema

Il tema chiaro e scuro è gestito da `_TopoCrackAppState` in `main.dart`. Lo stato `themeMode` viene passato a ogni schermata. Tutti i widget leggono `isDark` e cambiano colori e opacità di conseguenza. Le transizioni tra tema chiaro e scuro sono animate con `AnimatedContainer`.

## CustomPainter

`_CrackLinePainter` in `crack_editor_screen.dart` disegna la linea tratteggiata tra i due punti con due passate: prima una linea bianca piena, poi una linea verde tratteggiata sovrapposta per l'effetto visivo. Le posizioni dei punti sono in coordinate relative (0-1) e vengono moltiplicate per le dimensioni reali del canvas al momento del disegno.






27/04/2026
1.
Integrazione Multipart: Ora la funzione _confirmAndSend crea una richiesta http.MultipartRequest, aggiunge l'immagine come file e le coordinate (x1, y1, x2, y2) come campi del form.
2.
Gestione Caricamento: Ho aggiunto uno stato _isLoading. Quando premi "OK", il bottone mostra una piccola rotella di caricamento (CircularProgressIndicator) e impedisce click multipli.
3.
Parsing Risposta: Una volta ricevuta la risposta JSON, estraggo lat_start, lon_start e coast_name per passarli alla schermata dei risultati.
4.
Sicurezza: Ho aggiunto un blocco try-catch per gestire eventuali errori di rete o del server, mostrando un messaggio all'utente se qualcosa va storto.

