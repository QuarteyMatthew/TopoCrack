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
print("Image ratio:", img_ratio)
# Dynamic size for both vertical and horizontal images
max_display_length = 600
if img_ratio > 1:
    display_width, display_height = int(max_display_length), int(max_display_length/img_ratio)
else:
    display_width, display_height = int(max_display_length*img_ratio), int(max_display_length)
# Resizing image
img = cv2.resize(img, (display_width, display_height))

# Show original image
cv2.imshow('I. Crack 01 - B/W', img)

# ============= CLACHE Image =============
clahe1 = cv2.createCLAHE(clipLimit=3)

clahe_img_1 = np.clip(clahe1.apply(img), 0, 255).astype(np.uint8)
# cv2.imshow('II. Crack 01 - CLAHE1', clahe_img_1)

# ============= Bilateral Filtering Params =============
d = 9
sigmaColor = sigmaSpace = 120
# ============= Bilateral Filtering Params =============
darkestPixelPercentage = 25

uInput = ""
print("1=>d+=1; 2=>d-=1; 3=>sigmaColor+=5; 4=>sigmaColor-=5;\
5=>sigmaSpace+=5; 6=>sigmaSpace-=5; 7=>darkPerc+=1; 8=>darkPerc-=1;\
WASD=>move userStart; IJKL=>move userEnd; Q=>Exit;")

# Controllo dell'elaborazione dell'immagine (permette di spostare i punti dell'utente senza elaborare ogni cambio di pixel)
isImageProcessingPaused = False

# I punti indicati dall'utente.
# PER ORA SONO INDICATIVI
userStart, userEnd = [[int(display_width/5), int(display_height/2)], [int(4*display_width/5), int(display_height/2)]]

coords = []
graph = None

# Main Loop
while uInput != "quit":
    if not isImageProcessingPaused:
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
        cv2.imshow('IV. Edges 1 - Canny', canned_img_1)

        # ============= Closing Morphology Image =============
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (10, 10))
        closed_img_1 = cv2.morphologyEx(canned_img_1, cv2.MORPH_CLOSE, kernel)
        cv2.imshow('V. Closed 1 - morphologyEx', closed_img_1)

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
        ideal_path = [] # La lista dei nodi del path più lungo

        # copia del grafo
        tempGraph = graph.copy()

        minimumDistancesSum = np.inf
        startNodeIdx = None
        endNodeIdx = None

        # finché ci sono nodi in 'tempGraph'
        while tempGraph.number_of_nodes() > 0:
            # prendi un nodo qualsiasi presente in 'tempGraph'
            any_node = next(iter(tempGraph.nodes()))
            # ottieni l'insieme dei nodi della componente connessa che contiene il nodo 'any_node'
            comp_set = nx.node_connected_component(tempGraph, any_node)
            # trasformalo in lista per indicizzazione ordinata
            comp_nodes = list(comp_set)

            # rimuovi la componente dal grafo temporaneo
            tempGraph.remove_nodes_from(comp_set)

            # se la componente ha meno di 2 nodi non ha senso cercare coppie
            if len(comp_nodes) < 2:
                continue

            # calcola la somma minima delle distanze tra due nodi della componente e i due punti utente
            # userStart/userEnd sono [x, y] (col, row) -> convertiamo in [row, col] per confrontare con data['o']
            userStart_rc = np.array([userStart[1], userStart[0]])
            userEnd_rc   = np.array([userEnd[1],   userEnd[0]])

            for i in range(len(comp_nodes) - 1):
                # Il nodo del componente in 'i'
                ni = comp_nodes[i]
                # Il centroide del nodo 'ni'
                oi = np.asarray(graph.nodes[ni]['o'], dtype=float)

                # Compara il nodo 'ni' con tutti gli altri nodi del componente
                for j in range(i + 1, len(comp_nodes)):
                    # Il nodo del componente in 'j'
                    nj = comp_nodes[j]
                    # Il centroide del nodo 'nj'
                    oj = np.asarray(graph.nodes[nj]['o'], dtype=float)

                    # due possibili accoppiamenti: (ni->userStart, nj->userEnd) o scambiati
                    sum1 = np.linalg.norm(oi - userStart_rc) + np.linalg.norm(oj - userEnd_rc)
                    sum2 = np.linalg.norm(oi - userEnd_rc)   + np.linalg.norm(oj - userStart_rc)
                    tempDistancesSum = min(sum1, sum2)

                    if tempDistancesSum < minimumDistancesSum:
                        minimumDistancesSum = tempDistancesSum
                        # scegli quale nodo corrisponde a start/end in base al min scelto
                        if sum1 <= sum2:
                            startNodeIdx = ni
                            endNodeIdx = nj
                        else:
                            startNodeIdx = nj
                            endNodeIdx = ni
        
        ideal_path = nx.shortest_path(graph, startNodeIdx, endNodeIdx, weight='weight')
        
        # # Ottiene la lista delle distanze tra i nodi del grafo e il punto indicato dall'utente
        # startCandidatesNorms = []
        # for n in graph.nodes():
        #     startCandidatesNorms.append(np.linalg.norm(graph.nodes[n]['o'] - [userStart[1], userStart[0]]))
        # # Finds the index corresponding to the closest node to the userStart
        # startNodeIdx = startCandidatesNorms.index(min(startCandidatesNorms))
        # endNodeIdx = None

        # # Trova la componente connessa di startNodeIdx
        # component = nx.node_connected_component(graph, startNodeIdx)

        # # filtra solo i nodi della stessa componente
        # valid_targets = [n for n in component]
        
        # if startNodeIdx in valid_targets:
        #     # Toglie il nodo di partenza dai nodi candidati per non avere lo stesso nodo per start e end
        #     valid_targets.remove(startNodeIdx)

        # # Trova il nodo collegato allo start con la distanza (la norma) minima dal punto indicato dall'utente
        # endNodeIdx = min(valid_targets, key=lambda n: np.linalg.norm(graph.nodes[n]['o'] - [userEnd[1], userEnd[0]]))

        # # Il percorso più corto tra i due nodi collegati trovati
        # # (il nodo start è il piu vicino al punto indicato dall'utente, mentre il nodo end è
        # # il più vicino al punto indicato dall'utente che è collegato al nodo di start).
        # ideal_path = nx.shortest_path(graph, startNodeIdx, endNodeIdx, weight='weight') 

        # Resets 'coords'
        coords = []

        # Vengono estratte le coordinate dei punti che compongono il percorso trovato:
        # 'range' returns a range from start (def. 0) to stop (here the length of
        # longest_path - 1)
        for i in range(len(ideal_path) - 1):
            # Estrae dal grafo un nodo e il nodo ad esso consecutivo
            edge = graph[ideal_path[i]][ideal_path[i+1]]
            # Estende le coordinate aggiungendo i punti tra un nodo e il suo consecutivo
            coords.extend(edge['pts'].tolist())

        # Conversione della lista in un array NumPy
        coords = np.array(coords)
        
    # Crea una nuova immagine con sfondo nero per visualizzare 'coords'
    black_image = np.zeros((display_height, display_width), dtype=np.uint8)
        
    # Disegna sui pixel dell'immagine (deve essere B&W) i nodi e gli archi del grafo.
    sknw.draw_graph(black_image, graph)
    
    rgb_image = cv2.cvtColor(black_image, cv2.COLOR_GRAY2BGR)
    
    # Drawing the idealPath
    for y, x in coords:
        if 0 <= y < rgb_image.shape[0] and 0 <= x < rgb_image.shape[1]:
            rgb_image[y, x] = (0, 255, 0)
    
    # Drawing the startNode
    for y, x in graph.nodes[startNodeIdx]['pts']:
        if 0 <= y < rgb_image.shape[0] and 0 <= x < rgb_image.shape[1]:
            rgb_image[y, x] = (255, 0, 0) # Start node is colored RED
    
    # Drawing the endNode
    for y, x in graph.nodes[endNodeIdx]['pts']:
        if 0 <= y < rgb_image.shape[0] and 0 <= x < rgb_image.shape[1]:
            rgb_image[y, x] = (0, 0, 255) # End node is colored BLUE
    
    # Drawing the userStart
    for i in range(-3, 4):
        # Giving a 2 px width to the line
        for j in range(-1, 2):
            pixelX = userStart[0] + i + j # Applying the horizontal offset
            pixelY = userStart[1] + i + j # Applying the vertical offset
            if pixelX > 0 and pixelX < display_width:
                rgb_image[userStart[1], pixelX] = (255, 255, 0)
            if pixelY > 0 and pixelY < display_height:
                rgb_image[pixelY, userStart[0]] = (255, 255, 0)
    
    # Drawing the userEnd
    for i in range(-3, 4):
        # Giving a 2 px width to the line
        for j in range(-1, 2):
            pixelX = userEnd[0] + i + j # Applying the horizontal offset
            pixelY = userEnd[1] + i + j # Applying the vertical offset
            if pixelX > 0 and pixelX < display_width:
                rgb_image[userEnd[1], pixelX] = (255, 0, 255)
            if pixelY > 0 and pixelY < display_height:
                rgb_image[pixelY, userEnd[0]] = (255, 0, 255)
    
    cv2.imshow('VIII. Graph', rgb_image)
    
    # ============= Wait for Keys =============
    key = cv2.waitKey(0) & 0xFF  # aspetta tasto sulla finestra OpenCV
    
    # ============= Input Polling =============
    if key == ord('q'):
        break
    elif key == ord('p'):
        if isImageProcessingPaused:
            isImageProcessingPaused = False
        else:
            isImageProcessingPaused = True
    elif key == ord('1'):
        d += 1
    elif key == ord('2'):
        if d > 1:
            d -= 1
    elif key == ord('3'):
        sigmaColor += 5
    elif key == ord('4'):
        sigmaColor -= 5
    elif key == ord('5'):
        sigmaSpace += 5
    elif key == ord('6'):
        sigmaSpace -= 5
    elif key == ord('7'):
        if darkestPixelPercentage < 99:
            darkestPixelPercentage += 1
    elif key == ord('8'):
        if darkestPixelPercentage > 1:
            darkestPixelPercentage -= 1
    elif key == ord('w'):
        # Goes up if it would stay inside the image
        if userStart[1]>1:
            userStart[1] -= 2
    elif key == ord('a'):
        if userStart[0]>1:
            userStart[0] -= 2
    elif key == ord('s'):
        if userStart[1]<display_height-2:
            userStart[1] += 2
    elif key == ord('d'):
        if userStart[0]<display_width-2:
            userStart[0] += 2
    elif key == ord('i'):
        # Goes up if it would stay inside the image
        if userEnd[1]>1:
            userEnd[1] -= 2
    elif key == ord('j'):
        if userEnd[0]>1:
            userEnd[0] -= 2
    elif key == ord('k'):
        if userEnd[1]<display_height-2:
            userEnd[1] += 2
    elif key == ord('l'):
        if userEnd[0]<display_width-2:
            userEnd[0] += 2
            

# ============= Destroy windows =============
cv2.destroyAllWindows()