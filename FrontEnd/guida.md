# TOPOCRACK FLUTTER APPLICATION

Flutter è un open-source framwork per la creazione di applicazioni multi-platform da un singolo codice. **Dart** è il linguaggio di programmazione di cui flutter si avvale per la programmazione della applicazione che offre molti vantaggi legati alla portabilità; compatibile con le piu notorie ISA (Instruction Set Architectures), ovvero il "linguaggio" fondamentale che permette al software di comunicare con l'hardware del processore, la velocita di compilazione con javascript e webAssembly per il web.
In oltre,  Dart è progettato per si di visualizzare istantaneamente le modifiche senz dover 
## 04/03/2026


## DART

    
Tutte le variabili si dichiarano definendo il tipo: 
String ..
int..
Variabilil "var", immagini , stringe, numero,
una variabile dichiarata con ? (ad esempio String? nome;) indica che la variabile è nullable, ovvero può contenere un valore del suo tipo oppure null.


variabili definibili indirettamente tramite il getter method inveced di una variabile, cioè utilizza l'interpolazione delle stringhe per stampare gli equivalenti delle stringhe delle variabili all'interno di stringhe letterali.


        Analizziamo pezzo per pezzo il costruttore                   
        Spacecraft.unlaunched(String name) : this(name, null);

    1. Spacecraft.unlaunched(String name)
    È un costruttore denominato (named constructor). 
    unlaunched è il nome del costruttore, diverso dal costruttore di default.
    Prende un solo parametro obbligatorio: String name. 
    2. : this(name, null)
    È un redirecting constructor (costruttore di reindirizzamento). 
    Usa : per chiamare un altro costruttore della stessa classe.
    this(name, null) chiama il costruttore principale della classe Spacecraft, passando:
    name: il valore ricevuto come parametro.
    null: indica che la data di lancio non è ancora impostata.