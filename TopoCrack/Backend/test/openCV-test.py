from pathlib import Path
import cv2
import numpy as np
import skimage as sk
import networkx as nx
import sknw_patched as sknw

# Ricava la cartella di esecuzione di questo script
script_dir = Path(__file__).resolve().parent
print(script_dir)
# ============= Original Image =============
img = cv2.imread(f'{script_dir}/img/crack01.jpg', cv2.IMREAD_GRAYSCALE)

# Image Settings
img_height, img_width = img.shape[:2]
print("Width:", img_width, "\nHeight:", img_height)
img_ratio = img_width/img_height
# Dynamic size for both vertical and horizontal images
if img_ratio > 1:
    display_width, display_height = int(800), int(800/img_ratio)
else:
    display_width, display_height = int(800/img_ratio), int(800)
# Resizing image
img = cv2.resize(img, (display_width, display_height))

# Show original image
# cv2.imshow('I. Crack 01 - B/W', img)

# ============= CLACHE Image =============
clahe1 = cv2.createCLAHE(clipLimit=3)

clahe_img_1 = np.clip(clahe1.apply(img), 0, 255).astype(np.uint8)
# cv2.imshow('II. Crack 01 - CLAHE1', clahe_img_1)

# ============= Bilateral Filtering Params =============
d = 10
sigmaColor = sigmaSpace = 100
# ============= Bilateral Filtering Params =============
darkestPixelPercentage = 20

uInput = ""
print("W=>d+=1; S=>d-=1; E=>sigmaColor+=5; D=>sigmaColor-=5;\
    R=>sigmaSpace+=5; F=>sigmaSpace-=5; T=>darkPerc+=1; G=>darkPerc-=1; Q=>Exit;")

# Main Loop
while uInput != "quit":  
    print(f"d={d}; sigmaColor={sigmaColor}; sigmaSpace={sigmaSpace}; darkPerc={darkestPixelPercentage}")
    
    # ============= Bilateral Filtered Image =============
    filtered_img_1 = cv2.bilateralFilter(clahe_img_1, d, sigmaColor, sigmaSpace)
    # cv2.imshow('III. Filtered 1 - Bilateral', filtered_img_1)

    # ============= Brightness Flattening =============
    threshold_percentile = np.percentile(filtered_img_1, darkestPixelPercentage)  # valore sotto cui cade il 20% più scuro

    # Il pixel più scuro tra l'80% più chiaro
    background_value = filtered_img_1[filtered_img_1 > threshold_percentile].min()

    result = filtered_img_1.copy()
    result[filtered_img_1 > threshold_percentile] = background_value

    # cv2.imshow('Percentile filter', result)

    # ============= Edge Detection Image (Canny) =============
    # Dopo il bilateral filter, Canny invece di threshold diretta
    median1 = np.median(result.flatten())
    lower1 = 0.66 * median1
    upper1 = 1.33 * median1
    thresholds1 = [lower1, upper1]
    canned_img_1 = cv2.Canny(result, int(thresholds1[0]), int(thresholds1[1]))
    # cv2.imshow('IV. Edges 1 - Canny', canned_img_1)

    # ============= Closing Morphology Image =============
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (10, 10))
    closed_img_1 = cv2.morphologyEx(canned_img_1, cv2.MORPH_CLOSE, kernel)
    # cv2.imshow('V. Closed 1 - morphologyEx', closed_img_1)

    # ============= To Binary Image =============
    # Ora binarizza (è già quasi binaria, ma per sicurezza)
    _, binary_img_1 = cv2.threshold(closed_img_1, 127, 255, cv2.THRESH_BINARY)
    # cv2.imshow('VI. Binary 1 - Otsu', binary_img_1)

    # ============= Skeletonization =============
    # 'sk.morphology.skeletonize':
    # applica l'algoritmo di thinning, riducendo ogni oggetto connesso
    # ad una linea di spessore 1px preservando le ramificazioni
    #
    # 'binary_img_1 > 0':
    # produce una maschera booleana dove i pixel di foreground sono True
    #
    # Il risultato è un array booleano della stessa dimensione della maschera:
    # True sui pixel dello scheletro e False altrove
    skele_img_1 = sk.morphology.skeletonize(binary_img_1 > 0)

    # Converti in uint8 per OpenCV: True→255, False→0
    # 'astype(np.uint8)' converte i valori booleani della maschera in 0/1 interi
    # moltiplicando per 255 si ottiene un immagine in scala di grigi
    skele_img_display = skele_img_1.astype(np.uint8) * 255
    cv2.imshow('VII. Skele 1 - skeletonize', skele_img_display)
    
    # ============= Find Main Path =============
    # 'build_sknw' è la funzione che:
    # - aggiunge padding all'immagine data per evitare controlli sui bordi;
    # - marca i pixel dello scheletro distinguendoli in passaggi (con due
    #    connessioni - grado == 2) e nodi (con un numero di connessioni
    #     diverso da 2 - grado != 2);
    # - raggruppa i pixel di grado != 2 in componenti connesse (nodi);
    # - traccia gli archi seguendo i pixel di passaggio tra i nodi;
    # - costruisce un oggetto (network.Graph o MultiGraph) dove:
    #   - ogni nodo ha attributi come 'pts' (coord. dei pixel che compongono il
    #      nodo) e 'o' (il centroide del nodo);
    #   - ogni arco ha attributi come 'pts' (linea di pixel che compongono
    #      l'arco) e 'weight' (la lunghezza calcolata dalla somma delle
    #       distanze tra punti consecutivi)
    graph = sknw.build_sknw(skele_img_1)

    
    # Raccoglie i nodi (n) con grado 1, cioè le 'punte' terminali
    # (endpoints) dello scheletro, quelli che sono collegati a un solo
    # altro nodo. Questi nodi sono i candidati estremi del ramo principale.
    endpoints = [n for n in graph.nodes() if graph.degree(n) == 1]

    # Ricerca del percorso più lungo tra endpoints
    longest_path = [] # La lista dei nodi del path più lungo
    longest_length = 0

    # Cicla per tutte le coppie di endpoints trovando la sequenza di nodi che
    # minimizza la somma dei pesi (le distanze tra i nodi).
    # 'i' è l'index e 'start' è l'elemento della lista data dall'enumerate in
    # posizione i.
    # for i, start in enumerate(endpoints):
    #     for end in endpoints[i+1:]:
    #         try:
    #             # Trova tra tutti i percorsi tra il nodo 'start' e il nodo
    #             # 'end' quello più corto con Dijkstra [pronun. /ˈdɛikstra/]
    #             path = nx.longest_path(graph, start, end, weight='weight')
    #             # Calcola la lunghezza del percorso più corto
    #             length = nx.shortest_path_length(graph, start, end, weight='weight')
    #             if length > longest_length:
    #                 # Il percorso appena analizzato è più lungo di quelli precedenti
    #                 longest_length = length
    #                 longest_path = path
    #         except nx.NetworkXNoPath:
    #             # I due punti analizzati non sono connessi - vengono saltati
    #             continue
            
    endpoints = [n for n in graph.nodes() if graph.degree(n) == 1]

    longest_path = []
    longest_length = -1.0

    for i, start in enumerate(endpoints):
        # calcola distanze da start a tutti (Dijkstra once)
        lengths = nx.single_source_dijkstra_path_length(graph, start, weight='weight')
        for end in endpoints[i+1:]:
            if end in lengths:
                length = lengths[end]
                if length > longest_length:
                    longest_length = length
                    longest_path = nx.shortest_path(graph, start, end, weight='weight')


    # Vengono estratte le coordinate dei punti che compongono 'longest_path'
    coords = []
    # 'range' returns a range from start (def. 0) to stop (here the length of
    # longest_path - 1)
    for i in range(len(longest_path) - 1):
        # Estrae dal grafo un nodo e il nodo ad esso consecutivo
        edge = graph[longest_path[i]][longest_path[i+1]]
        # Estende le coordinate aggiungendo i punti tra un nodo e il suo consecutivo
        coords.extend(edge['pts'].tolist())

    # Conversione della lista in un array NumPy
    coords = np.array(coords)
    
    # Crea una nuova immagine con sfondo nero per visualizzare 'coords'
    black_image = np.zeros((display_height, display_width), dtype=np.uint8)
    
    # Disegna sui pixel dell'immagine (deve essere B&W) i nodi e gli archi del grafo.
    sknw.draw_graph(black_image, graph)
    
    rgb_image = cv2.cvtColor(black_image, cv2.COLOR_GRAY2BGR)
    
    for y, x in coords:
        if 0 <= y < rgb_image.shape[0] and 0 <= x < rgb_image.shape[1]:
            rgb_image[y, x] = (0, 255, 0)
    
    
    cv2.imshow('VIII. Graph', rgb_image)
    
    # ============= Wait for Keys =============
    key = cv2.waitKey(0) & 0xFF  # aspetta tasto sulla finestra OpenCV
    
    # ============= Input Polling =============
    if key == ord('q'):
        break
    elif key == ord('w'):
        d += 1
    elif key == ord('s'):
        if d > 1:
            d -= 1
    elif key == ord('e'):
        sigmaColor += 5
    elif key == ord('d'):
        sigmaColor -= 5
    elif key == ord('r'):
        sigmaSpace += 5
    elif key == ord('f'):
        sigmaSpace -= 5
    elif key == ord('t'):
        if darkestPixelPercentage < 99:
            darkestPixelPercentage += 1
    elif key == ord('g'):
        if darkestPixelPercentage > 1:
            darkestPixelPercentage -= 1

# ============= Destroy windows =============
cv2.destroyAllWindows()