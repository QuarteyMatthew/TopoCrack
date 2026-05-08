import cv2
import numpy
import skimage
import networkx
import _SknwPatched as sknw

from ..Schemas.AnalysisSchemas import Point

from pydantic import BaseModel
class Point(BaseModel):
    X: int
    Y: int
    
    def ToTuple(self) -> tuple[int, int]:
        return (self.X, self.Y)

class ImageService:
    
    # Parametri della pipeline
    _MaxDisplayLength:                int   = 600
    _ClaheClipLimit:                  int   = 3
    _BilateralDiameter:               int   = 7
    _BilateralSigmaColor:             int   = 100
    _BilateralSigmaSpace:             int   = 120
    _DarkestPixelPercentageBilateral: int   = 25
    _DarkestPixelPercentageCanny:     int   = 5
    _MorphAnchor:                     int   = 3
    _SamplesNumber:                   int   = 30
    
    @staticmethod
    def ExtractCrackPoints(imageBytes: bytes, userStart: Point, userEnd: Point) -> numpy.ndarray:
        """
        Prende i byte dell'immagine e i due punti utente (x, y),
        restituisce i punti della crepa come array NumPy (N, 2) in formato [row, col].
        """
        
        # Decodifica l'immagine dai byte HTTP
        imageRawData = numpy.frombuffer(imageBytes, numpy.uint8)
        image = cv2.imdecode(imageRawData, cv2.IMREAD_GRAYSCALE)
        
        if image is None:
            raise ValueError("Unable to decode image. Format not supported")
        
        # Esegue la pipeline per processare l'immagine della crepa
        return ImageService._RunPipeline(image, userStart, userEnd)
    
    @staticmethod
    def _RunPipeline(image: numpy.ndarray, userStart: Point, userEnd: Point) -> numpy.ndarray:
        """
        Pipeline completa: dall'immagine grezza alle coordinate della crepa
        campionate e pronte per il DTW.

        Restituisce un array NumPy di forma (N, 2) in formato [row, col].
        """
        
        # -------------------- 1. Ridimensionamento --------------------
        # Mantiene le proporzioni originali, adattando il lato più lungo
        # a _MaxDisplayLength. Questo è necessario perché i parametri
        # della pipeline (Canny, Bilateral, ecc.) sono stati calibrati
        # su immagini di circa 600px.
        imageHeight, imageWidth = image.shape[:2]
        imageRatio = imageWidth / imageHeight
        
        maxLength = ImageService._MaxDisplayLength
        if imageRatio > 1:
            displayWidth, displayHeight = maxLength, int(maxLength / imageRatio)
        else:
            displayWidth, displayHeight = int(maxLength / imageRatio), maxLength
            
        image = cv2.resize(image, (displayWidth, displayHeight))
        
        # I punti utente arrivano in coordinate pixel dell'immagine originale,
        # quindi devono essere riscalati insieme all'immagine.
        scaleX = displayWidth / imageWidth
        scaleY = displayHeight / imageHeight
        userStart = Point(X=int(userStart.X * scaleX), Y=int(userStart.Y * scaleY))
        userEnd = Point(X=int(userEnd.X * scaleX), Y=int(userEnd.Y * scaleY))
        
        # ---- 2. CLAHE (Contrast Limited Adaptive Histogram Equalization) ----
        # Migliora il contrasto locale: le crepe sottili su sfondi
        # disomogenei diventano molto più visibili.
        clahe = cv2.createCLAHE(clipLimit=ImageService._ClaheClipLimit)
        claheImage = numpy.clip(clahe.apply(image), 0, 255).astype(numpy.uint8)
        
        # -------------------- 3. Bilateral filter --------------------
        # Riduce il rumore preservando i bordi netti — fondamentale qui
        # perché Canny (passo successivo) è molto sensibile al rumore.
        # Il bilateral è lento ma molto efficace su texture di cemento.
        filteredImage = cv2.bilateralFilter(
            claheImage,
            ImageService._BilateralDiameter,
            ImageService._BilateralSigmaColor,
            ImageService._BilateralSigmaSpace,
        )
        
        # ----- 4. Appiattimento della luminosità (25% più scuro) -----
        # L'idea è eliminare le variazioni di illuminazione dello sfondo:
        # teniamo solo i pixel più scuri (la crepa) e "schiacciamo" tutto
        # il resto allo stesso valore di grigio.
        threshold1 = numpy.percentile(filteredImage, ImageService._DarkestPixelPercentageBilateral)
        backgroundValue = filteredImage[filteredImage > threshold1].min()
        darkenedImage = filteredImage.copy()
        darkenedImage[filteredImage > threshold1] = backgroundValue
        
        # ----------------- 5. Canny (edge detection) -----------------
        # Gli edge vengono calcolate dinamicamente dalla mediana dell'immagine,
        # così la pipeline si adatta automaticamente al contrasto della foto.
        median = numpy.median(darkenedImage.flatten())
        lowerEdge = 0.66 * median
        upperEdge = 1.33 * median
        cannyImage = cv2.Canny(darkenedImage, int(lowerEdge), int(upperEdge))
        
        # ------------------ 6. Rinforzo 5% più scuro -----------------
        # I pixel che il filtro bilateral ha identificato come i più scuri
        # (quasi certamente la crepa) vengono aggiunti ai bordi del Canny.
        # Questo garantisce che la crepa non venga "persa" dal Canny nei
        # punti dove il gradiente è debole (crepa a basso contrasto).
        threshold2 = numpy.percentile(filteredImage, ImageService._DarkestPixelPercentageCanny)
        reinforcedImage = cannyImage.copy()
        reinforcedImage[filteredImage < threshold2] = 255
        
        # ---------------- 7. Chiusura della morfologia ----------------
        # Colma i piccoli buchi e discontinuità nel bordo rilevato,
        # producendo una linea più continua. Un kernel quadrato di
        # _MorphAnchor × _MorphAnchor è sufficiente per piccole lacune.
        kernel = cv2.getStructuringElement(
            cv2.MORPH_RECT,
            (ImageService._MorphAnchor, ImageService._MorphAnchor)
        )
        closedImage = cv2.morphologyEx(reinforcedImage, cv2.MORPH_CLOSE, kernel)
        
        # --------------------- 8. Binarizzazione ----------------------
        # L'immagine è già quasi binaria dopo Canny, ma questa sogliatura
        # garantisce valori esattamente 0 o 255 per la scheletonizzazione.
        _, binaryImage = cv2.threshold(closedImage, 127, 255, cv2.THRESH_BINARY)
        
        # ------------------- 9. Scheletonizzazione --------------------
        # Riduce ogni oggetto connesso a una linea di spessore 1px
        # preservando la topologia (ramificazioni incluse).
        # L'input richiede una maschera booleana (True = foreground).
        skeletonizedImage = skimage.morphology.skeletonize(binaryImage > 0)
        
        # ----------------- 10. Costruzione del grafo ------------------
        # sknw trasforma lo scheletro in un grafo dove:
        #   - i nodi sono giunzioni e terminali dello scheletro
        #   - gli archi sono i segmenti che li collegano
        #   - ogni arco ha 'pts' (pixel) e 'weight' (lunghezza)
        graph = sknw.build_sknw(skeletonizedImage)
        
        # ---- 11. Selezione del percorso più vicino ai punti utente ----
        # L'algoritmo cerca la coppia di nodi (StartNode, EndNode) tale
        # che la somma delle distanze da UserStart e UserEnd sia minima.
        # Questo viene fatto componente connessa per componente connessa,
        # così crepe isolate non interferiscono tra loro.
        startNodeIndex, endNodeIndex = ImageService._FindBestNodePair(graph, userStart, userEnd)
        
        # ----------- 12. Shortest path e raccolta coordinate -----------
        shortestPath = networkx.shortest_path(graph, startNodeIndex, endNodeIndex, weight="weight")
        coords = ImageService._ExtractCoordsFromPath(graph, shortestPath)
        
        # Visualizzazione
        ImageService._Visualize(
            graph,
            displayWidth, displayHeight,
            userStart, userEnd,
            coords,
            startNodeIndex, endNodeIndex
        )
        
        # --------------------- 13. Campionamento -----------------------
        # Il DTW scala quadraticamente con il numero di punti, quindi
        # campionare a un numero fisso (_SamplesNumber) è fondamentale
        # per mantenere i tempi di risposta accettabili.
        step = max(1, len(coords) // ImageService._SamplesNumber)
        sampledCoords = coords[::step]
        
        return sampledCoords
    
    @staticmethod
    def _FindBestNodePair(graph: object, userStart: Point, userEnd: Point) -> tuple[int, int]:
        """
        Trova la coppia di nodi del grafo (StartNode, EndNode) che minimizza
        la somma delle distanze euclidee da UserStart e UserEnd.

        I punti utente sono (x, y) = (col, row); i centroidi dei nodi
        sono in formato (row, col), quindi converte prima di confrontare.
        """
        
        userStartRc = numpy.array([userStart.Y, userStart.X])
        userEndRc = numpy.array([userEnd.Y, userEnd.X])
        
        minDistanceSum = numpy.inf
        startNodeIndex = None
        endNodeIndex   = None
        
        tempGraph = graph.copy()
        
        while tempGraph.number_of_nodes() > 0:
            anyNode = next(iter(tempGraph.nodes()))
            componentSet = networkx.node_connected_component(tempGraph, anyNode)
            componentNodes = list(componentSet)
            tempGraph.remove_nodes_from(componentSet)
            
            if len(componentNodes) < 2:
                continue
            
            for i in range(len(componentNodes) - 1):
                nodeI = componentNodes[i]
                centroidI = numpy.asarray(graph.nodes[nodeI]["o"], dtype=float)
                
                for j in range(i + 1, len(componentNodes)):
                    nodeJ = componentNodes[j]
                    centroidJ = numpy.asarray(graph.nodes[nodeJ]["o"], dtype=float)
                    
                    # Prova entrambi gli accoppiamenti (Ni→Start o Ni→End)
                    # e teniamo il migliore.
                    sum1 = numpy.linalg.norm(centroidI - userStartRc) + numpy.linalg.norm(centroidJ - userEndRc)
                    sum2 = numpy.linalg.norm(centroidI - userEndRc)   + numpy.linalg.norm(centroidJ - userStartRc)
                    
                    bestSum = min(sum1, sum2)
                    if bestSum < minDistanceSum:
                        minDistanceSum = bestSum
                        
                        if (sum1 <= sum2):
                            startNodeIndex, endNodeIndex = nodeI, nodeJ
                        else:
                            startNodeIndex, endNodeIndex = nodeJ, nodeI
                            
        if startNodeIndex is None:
            raise ValueError("No paths found in the graph. Verify that the image contains a visible crack")
        
        return startNodeIndex, endNodeIndex
    
    @staticmethod
    def _ExtractCoordsFromPath(graph: object, shortestPath: list) -> numpy.ndarray:
        """
        Percorre gli archi dello shortest path e raccoglie tutti i pixel
        che li compongono, nell'ordine corretto (da A verso B).

        sknw non garantisce che i pixel di un arco siano orientati da A
        verso B, quindi verifica quale estremità di 'pts' è più vicina
        al nodo A e invertiamo se necessario.
        """
        
        coords = []
        
        for i in range(len(shortestPath) - 1):
            nodeA = shortestPath[i]
            nodeB = shortestPath[i + 1]
            edge = graph[nodeA][nodeB]
            points = edge["pts"] # Shape (N, 2), formato [row, col]
            
            if len(points) == 0:
                continue
            
            positionA = numpy.array(graph.nodes[nodeA]["o"]) # [row, col]
            
            # Se il pixel iniziale di Pts è più lontano da A rispetto
            # all'ultimo, l'array è orientato al contrario: lo inverte.
            distanceToStart = numpy.linalg.norm(points[0] - positionA)
            distanceToEnd   = numpy.linalg.norm(points[-1] - positionA)
            
            if distanceToEnd < distanceToStart:
                points = points[::-1]
                
            coords.extend(points.tolist())
        
        return numpy.array(coords)

    @staticmethod
    def _Visualize(graph, displayWidth: int, displayHeight: int, userStart: Point,
        userEnd: Point, coords: numpy.ndarray, startNodeIndex: int, endNodeIndex: int
    ):
        # Crea una nuova immagine con sfondo nero per visualizzare 'coords'
        blackImage = numpy.zeros((displayHeight, displayWidth), dtype=numpy.uint8)
        
        # Disegna sui pixel dell'immagine (deve essere B&W) i nodi e gli archi del grafo.
        sknw.draw_graph(blackImage, graph)
        
        rgbImage = cv2.cvtColor(blackImage, cv2.COLOR_GRAY2BGR)
    
        # Drawing the idealPath
        for y, x in coords:
            if 0 <= y < rgbImage.shape[0] and 0 <= x < rgbImage.shape[1]:
                rgbImage[y, x] = (0, 255, 0)
        
        # Drawing the startNode
        for y, x in graph.nodes[startNodeIndex]["pts"]:
            if 0 <= y < rgbImage.shape[0] and 0 <= x < rgbImage.shape[1]:
                rgbImage[y, x] = (255, 0, 0) # Start node is colored RED
        
        # Drawing the endNode
        for y, x in graph.nodes[endNodeIndex]["pts"]:
            if 0 <= y < rgbImage.shape[0] and 0 <= x < rgbImage.shape[1]:
                rgbImage[y, x] = (0, 0, 255) # End node is colored BLUE
        
        # Drawing the userStart
        for i in range(-3, 4):
            # Giving a 2 px width to the line
            for j in range(-1, 2):
                pixelX = userStart.X + i + j # Applying the horizontal offset
                pixelY = userStart.Y + i + j # Applying the vertical offset
                if pixelX > 0 and pixelX < displayWidth:
                    rgbImage[userStart.Y, pixelX] = (255, 255, 0)
                if pixelY > 0 and pixelY < displayHeight:
                    rgbImage[pixelY, userStart.X] = (255, 255, 0)
        
        # Drawing the userEnd
        for i in range(-3, 4):
            # Giving a 2 px width to the line
            for j in range(-1, 2):
                pixelX = userEnd.X + i + j # Applying the horizontal offset
                pixelY = userEnd.Y + i + j # Applying the vertical offset
                if pixelX > 0 and pixelX < displayWidth:
                    rgbImage[userEnd.Y, pixelX] = (255, 0, 255)
                if pixelY > 0 and pixelY < displayHeight:
                    rgbImage[pixelY, userEnd.X] = (255, 0, 255)
        
        cv2.imshow("Graph with the shortest path", rgbImage)
        cv2.waitKey(0) & 0xFF

# from pathlib import Path

# imageBytes = Path("../Resources/crack10.jpg").read_bytes()
# userStart = Point(X=420, Y=400)
# userEnd = Point(X=480, Y=100)
# ImageService.ExtractCrackPoints(imageBytes, userStart, userEnd)