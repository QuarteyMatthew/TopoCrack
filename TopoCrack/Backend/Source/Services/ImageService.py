import cv2
import logging
import numpy
import skimage
import networkx

from . import _SknwPatched as sknw
from Schemas.AnalysisSchemas import Point

logger = logging.getLogger(__name__)

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
    _SamplesNumber:                   int   = 200
    
    @staticmethod
    def ExtractCrackPoints(imageBytes: bytes, userStart: Point, userEnd: Point) -> numpy.ndarray:
        """
        Prende i byte dell'immagine e i due punti utente (x, y),
        restituisce i punti della crepa come array NumPy (N, 2) in formato [row, col].
        """
        
        logger.info(
            "ExtractCrackPoints called: image size: %d bytes, userStart: (%d, %d), userEnd: (%d, %d).",
            len(imageBytes), userStart.X, userStart.Y, userEnd.X, userEnd.Y
        )
        
        # Decodifica l'immagine dai byte HTTP
        imageRawData = numpy.frombuffer(imageBytes, numpy.uint8)
        image = cv2.imdecode(imageRawData, cv2.IMREAD_GRAYSCALE)
        
        if image is None:
            # ERROR perché questo è un guasto reale: i byte ricevuti non
            # rappresentano un'immagine valida. Il chiamante non può procedere.
            logger.error("Failed to decode image from bytes. The format may be unsupported or the data corrupt.")
            raise ValueError("Unable to decode image. Format not supported.")
        
        logger.debug("Image decoded successfully: %dx%d pixels.", image.shape[1], image.shape[0])
        
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
            displayWidth, displayHeight = int(maxLength * imageRatio), maxLength
            
        image = cv2.resize(image, (displayWidth, displayHeight))
        
        # I punti utente arrivano in coordinate pixel dell'immagine originale,
        # quindi devono essere riscalati insieme all'immagine.
        scaleX = displayWidth / imageWidth
        scaleY = displayHeight / imageHeight
        userStart = Point(X=int(userStart.X * scaleX), Y=int(userStart.Y * scaleY))
        userEnd = Point(X=int(userEnd.X * scaleX), Y=int(userEnd.Y * scaleY))
        
        logger.info(
            "Phase 1: Resize: %dx%d → %dx%d (ratio=%.2f). "
            "User points rescaled to start=(%d,%d), end=(%d,%d).",
            imageWidth, imageHeight, displayWidth, displayHeight, imageRatio,
            userStart.X, userStart.Y, userEnd.X, userEnd.Y,
        )
        
        # ---- 2. CLAHE (Contrast Limited Adaptive Histogram Equalization) ----
        # Migliora il contrasto locale: le crepe sottili su sfondi
        # disomogenei diventano molto più visibili.
        meanBefore = float(numpy.mean(image))
        clahe = cv2.createCLAHE(clipLimit=ImageService._ClaheClipLimit)
        claheImage = numpy.clip(clahe.apply(image), 0, 255).astype(numpy.uint8)
        meanAfter = float(numpy.mean(claheImage))
        
        logger.info(
            "Phase 2: CLAHE (clipLimit=%d): mean brightness %.1f → %.1f.",
            ImageService._ClaheClipLimit, meanBefore, meanAfter,
        )
        
        # -------------------- 3. Bilateral filter --------------------
        # Riduce il rumore preservando i bordi netti — fondamentale qui
        # perché Canny (passo successivo) è molto sensibile al rumore.
        # Il bilateral è lento ma molto efficace su texture di cemento.
        stdBefore = float(numpy.std(claheImage))
        filteredImage = cv2.bilateralFilter(
            claheImage,
            ImageService._BilateralDiameter,
            ImageService._BilateralSigmaColor,
            ImageService._BilateralSigmaSpace,
        )
        stdAfter = float(numpy.std(filteredImage))

        logger.info(
            "Phase 3: Bilateral filter (d=%d, sigmaColor=%d, sigmaSpace=%d): "
            "pixel std %.1f → %.1f.",
            ImageService._BilateralDiameter,
            ImageService._BilateralSigmaColor,
            ImageService._BilateralSigmaSpace,
            stdBefore, stdAfter,
        )
        
        # ----- 4. Appiattimento della luminosità (25% più scuro) -----
        # L'idea è eliminare le variazioni di illuminazione dello sfondo:
        # teniamo solo i pixel più scuri (la crepa) e "schiacciamo" tutto
        # il resto allo stesso valore di grigio.
        threshold1 = numpy.percentile(filteredImage, ImageService._DarkestPixelPercentageBilateral)
        backgroundValue = filteredImage[filteredImage > threshold1].min()
        darkenedImage = filteredImage.copy()
        darkenedImage[filteredImage > threshold1] = backgroundValue
        
        logger.info(
            "Phase 4: Brightness flattening (%d%% darkest pixels): "
            "threshold=%.1f, background flattened to %.1f.",
            ImageService._DarkestPixelPercentageBilateral, threshold1, float(backgroundValue),
        )
        
        # ----------------- 5. Canny (edge detection) -----------------
        # Gli edge vengono calcolate dinamicamente dalla mediana dell'immagine,
        # così la pipeline si adatta automaticamente al contrasto della foto.
        median = numpy.median(darkenedImage.flatten())
        lowerEdge = 0.66 * median
        upperEdge = 1.33 * median
        cannyImage = cv2.Canny(darkenedImage, int(lowerEdge), int(upperEdge))
        
        # Il numero di pixel bianchi dopo Canny indica quanti bordi sono stati
        # rilevati. Troppi (> 20% dell'immagine) suggerisce rumore eccessivo;
        # troppo pochi (< 0.1%) suggerisce che la crepa non è stata rilevata.
        cannyWhitePixels = int(numpy.sum(cannyImage > 0))
        cannyWhitePercent = 100.0 * cannyWhitePixels / (displayWidth * displayHeight)

        logger.info(
            "Phase 5: Canny edge detection: median=%.1f, thresholds=[%.1f, %.1f]. "
            "Edge pixels: %d (%.2f%% of image).",
            median, lowerEdge, upperEdge, cannyWhitePixels, cannyWhitePercent,
        )

        if cannyWhitePercent < 0.1:
            logger.warning(
                "Very few edge pixels detected (%.2f%%). "
                "The crack may not be visible enough for reliable extraction.",
                cannyWhitePercent,
            )
        elif cannyWhitePercent > 20.0:
            logger.warning(
                "Unusually high number of edge pixels (%.2f%%). "
                "The image may contain excessive noise or texture.",
                cannyWhitePercent,
            )
        
        # ------------------ 6. Rinforzo 5% più scuro -----------------
        # I pixel che il filtro bilateral ha identificato come i più scuri
        # (quasi certamente la crepa) vengono aggiunti ai bordi del Canny.
        # Questo garantisce che la crepa non venga "persa" dal Canny nei
        # punti dove il gradiente è debole (crepa a basso contrasto).
        threshold2 = numpy.percentile(filteredImage, ImageService._DarkestPixelPercentageCanny)
        reinforcedImage = cannyImage.copy()
        reinforcedImage[filteredImage < threshold2] = 255

        reinforcedWhitePixels = int(numpy.sum(reinforcedImage > 0))
        addedPixels = reinforcedWhitePixels - cannyWhitePixels

        logger.info(
            "Phase 6: Dark pixel reinforcement (%d%% darkest, threshold=%.1f): "
            "%d pixels added to edges (total edge pixels: %d).",
            ImageService._DarkestPixelPercentageCanny,
            float(threshold2), addedPixels, reinforcedWhitePixels,
        )
        
        # ---------------- 7. Chiusura della morfologia ----------------
        # Colma i piccoli buchi e discontinuità nel bordo rilevato,
        # producendo una linea più continua. Un kernel quadrato di
        # _MorphAnchor × _MorphAnchor è sufficiente per piccole lacune.
        kernel = cv2.getStructuringElement(
            cv2.MORPH_RECT,
            (ImageService._MorphAnchor, ImageService._MorphAnchor)
        )
        closedImage = cv2.morphologyEx(reinforcedImage, cv2.MORPH_CLOSE, kernel)
        
        closedWhitePixels = int(numpy.sum(closedImage > 0))

        logger.info(
            "Phase 7: Morphological closing (kernel=%dx%d): "
            "edge pixels %d → %d (filled %d gaps).",
            ImageService._MorphAnchor, ImageService._MorphAnchor,
            reinforcedWhitePixels, closedWhitePixels,
            closedWhitePixels - reinforcedWhitePixels,
        )
        
        # --------------------- 8. Binarizzazione ----------------------
        # L'immagine è già quasi binaria dopo Canny, ma questa sogliatura
        # garantisce valori esattamente 0 o 255 per la scheletonizzazione.
        _, binaryImage = cv2.threshold(closedImage, 127, 255, cv2.THRESH_BINARY)
        
        logger.debug("Phase 8: Binarization: complete.")
        
        # ------------------- 9. Scheletonizzazione --------------------
        # Riduce ogni oggetto connesso a una linea di spessore 1px
        # preservando la topologia (ramificazioni incluse).
        # L'input richiede una maschera booleana (True = foreground).
        skeletonizedImage = skimage.morphology.skeletonize(binaryImage > 0)
        
        skeletonPixels = int(numpy.sum(skeletonizedImage))

        logger.info(
            "Phase 9: Skeletonization: %d skeleton pixels (from %d edge pixels, reduction %.1fx).",
            skeletonPixels, closedWhitePixels,
            closedWhitePixels / max(1, skeletonPixels),
        )

        if skeletonPixels < 20:
            logger.warning(
                "Very few skeleton pixels (%d). "
                "The extracted crack path may be unreliable.",
                skeletonPixels,
            )
        
        # ----------------- 10. Costruzione del grafo ------------------
        # sknw trasforma lo scheletro in un grafo dove:
        #   - i nodi sono giunzioni e terminali dello scheletro
        #   - gli archi sono i segmenti che li collegano
        #   - ogni arco ha 'pts' (pixel) e 'weight' (lunghezza)
        graph = sknw.build_sknw(skeletonizedImage)
        nodeCount = graph.number_of_nodes()
        edgeCount = graph.number_of_edges()

        logger.info(
            "Phase 10: Graph construction: %d nodes, %d edges.", nodeCount, edgeCount)

        if nodeCount > 100:
            logger.warning(
                "Graph has a high node count (%d), suggesting a heavily branched skeleton. "
                "Consider increasing the morphological closing kernel or the bilateral filter strength.",
                nodeCount,
            )
        
        # ---- 11. Selezione del percorso più vicino ai punti utente ----
        # L'algoritmo cerca la coppia di nodi (StartNode, EndNode) tale
        # che la somma delle distanze da UserStart e UserEnd sia minima.
        # Questo viene fatto componente connessa per componente connessa,
        # così crepe isolate non interferiscono tra loro.
        logger.debug(
            "Phase 11: Finding best node pair closest to userStart=(%d,%d), userEnd=(%d,%d)...",
            userStart.X, userStart.Y, userEnd.X, userEnd.Y,
        )
        
        startNodeIndex, endNodeIndex = ImageService._FindBestNodePair(graph, userStart, userEnd)
        
        startCentroid = graph.nodes[startNodeIndex]["o"]
        endCentroid   = graph.nodes[endNodeIndex]["o"]

        logger.info(
            "Phase 11: Best node pair found: startNode=%d (centroid=[%.1f, %.1f]), "
            "endNode=%d (centroid=[%.1f, %.1f]).",
            startNodeIndex, startCentroid[0], startCentroid[1],
            endNodeIndex,   endCentroid[0],   endCentroid[1],
        )
        
        # ----------- 12. Shortest path e raccolta coordinate -----------
        shortestPath = networkx.shortest_path(graph, startNodeIndex, endNodeIndex, weight="weight")
        coords = ImageService._ExtractCoordsFromPath(graph, shortestPath)
        
        logger.info(
            "Phase 12: Shortest path: %d nodes traversed, %d raw coordinate points extracted.",
            len(shortestPath), len(coords),
        )
        
        # ---------------- Optional. Visualizzazione ----------------
        # ImageService._Visualize(
        #     graph,
        #     displayWidth, displayHeight,
        #     userStart, userEnd,
        #     coords,
        #     startNodeIndex, endNodeIndex
        # )
        
        # --------------------- 13. Campionamento -----------------------
        # Il DTW scala quadraticamente con il numero di punti, quindi
        # campionare a un numero fisso (_SamplesNumber) è fondamentale
        # per mantenere i tempi di risposta accettabili.
        step = max(1, len(coords) // ImageService._SamplesNumber)
        sampledCoords = coords[::step]
        
        logger.info(
            "Phase 13: Sampling: %d points → %d sampled points (step=%d). Pipeline complete.",
            len(coords), len(sampledCoords), step,
        )
        
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
        userEndRc   = numpy.array([userEnd.Y,   userEnd.X])

        minDistanceSum = numpy.inf
        startNodeIndex = None
        endNodeIndex   = None

        tempGraph = graph.copy()
        componentCount = 0
        skippedComponents = 0

        while tempGraph.number_of_nodes() > 0:
            anyNode = next(iter(tempGraph.nodes()))
            componentSet   = networkx.node_connected_component(tempGraph, anyNode)
            componentNodes = list(componentSet)
            tempGraph.remove_nodes_from(componentSet)
            componentCount += 1

            if len(componentNodes) < 2:
                skippedComponents += 1
                logger.debug("Component %d skipped: only %d node(s), need at least 2.", componentCount, len(componentNodes))
                continue

            for i in range(len(componentNodes) - 1):
                nodeI     = componentNodes[i]
                centroidI = numpy.asarray(graph.nodes[nodeI]["o"], dtype=float)

                for j in range(i + 1, len(componentNodes)):
                    nodeJ     = componentNodes[j]
                    centroidJ = numpy.asarray(graph.nodes[nodeJ]["o"], dtype=float)

                    sum1 = numpy.linalg.norm(centroidI - userStartRc) + numpy.linalg.norm(centroidJ - userEndRc)
                    sum2 = numpy.linalg.norm(centroidI - userEndRc)   + numpy.linalg.norm(centroidJ - userStartRc)

                    bestSum = min(sum1, sum2)
                    if bestSum < minDistanceSum:
                        minDistanceSum = bestSum
                        if sum1 <= sum2:
                            startNodeIndex, endNodeIndex = nodeI, nodeJ
                        else:
                            startNodeIndex, endNodeIndex = nodeJ, nodeI

        logger.debug(
            "_FindBestNodePair: examined %d component(s), skipped %d. "
            "Best distance sum: %.2f.",
            componentCount, skippedComponents, float(minDistanceSum),
        )

        if startNodeIndex is None:
            logger.error("No valid node pair found in the graph. The skeleton may be entirely disconnected or have no branches.")
            raise ValueError("No paths found in the graph. Verify that the image contains a visible crack.")

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
        flippedEdges = 0
        skippedEdges = 0

        for i in range(len(shortestPath) - 1):
            nodeA  = shortestPath[i]
            nodeB  = shortestPath[i + 1]
            edge   = graph[nodeA][nodeB]
            points = edge["pts"]

            if len(points) == 0:
                skippedEdges += 1
                logger.debug("Edge (%d → %d) has no pixel points, skipping.", nodeA, nodeB)
                continue

            positionA = numpy.array(graph.nodes[nodeA]["o"])

            distanceToStart = numpy.linalg.norm(points[0]  - positionA)
            distanceToEnd   = numpy.linalg.norm(points[-1] - positionA)

            if distanceToEnd < distanceToStart:
                points = points[::-1]
                flippedEdges += 1

            coords.extend(points.tolist())

        logger.debug(
            "_ExtractCoordsFromPath: %d edges processed, %d flipped for correct orientation, %d skipped (empty).",
            len(shortestPath) - 1, flippedEdges, skippedEdges,
        )

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

# imageBytes = Path("Resources/crack10.jpg").read_bytes()
# userStart = Point(X=420, Y=400)
# userEnd = Point(X=480, Y=100)
# crackPoints = ImageService.ExtractCrackPoints(imageBytes, userStart, userEnd)
# numpy.save("CrackPointsData.npy", crackPoints)