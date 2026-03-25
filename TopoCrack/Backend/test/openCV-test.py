import cv2
import numpy as np
import skimage as sk
import networkx as nx
import sknw_patched as sknw

# ============= Original Image =============
img = cv2.imread('./img/crack01.jpg', cv2.IMREAD_GRAYSCALE)

# Image Settings
img_height, img_width = img.shape[:2]
print("Width:", img_width, "\nHeight:", img_height)
img_ratio = img_width/img_height
new_width = 600
img = cv2.resize(img, (int(new_width), int(new_width/img_ratio)))

# Show original image
cv2.imshow('I. Crack 01 - B/W', img)

# ============= CLACHE Image =============
clahe1 = cv2.createCLAHE(clipLimit=3)

clahe_img_1 = np.clip(clahe1.apply(img), 0, 255).astype(np.uint8)
cv2.imshow('II. Crack 01 - CLAHE1', clahe_img_1)

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
    cv2.imshow('III. Filtered 1 - Bilateral', filtered_img_1)

    # ============= Brightness Flattening =============
    threshold_percentile = np.percentile(filtered_img_1, darkestPixelPercentage)  # valore sotto cui cade il 20% più scuro

    # Il pixel più scuro tra l'80% più chiaro
    background_value = filtered_img_1[filtered_img_1 > threshold_percentile].min()

    result = filtered_img_1.copy()
    result[filtered_img_1 > threshold_percentile] = background_value

    cv2.imshow('Percentile filter', result)

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
    cv2.imshow('VI. Binary 1 - Otsu', binary_img_1)

    # ============= Skeletonization =============
    skele_img_1 = sk.morphology.skeletonize(binary_img_1 > 0)

    # Converti in uint8 per OpenCV: True→255, False→0
    skele_img_display = skele_img_1.astype(np.uint8) * 255
    cv2.imshow('VII. Skele 1 - skeletonize', skele_img_display)
    
    # ============= Find Main Path =============
    graph = sknw.build_sknw(skele_img_1)
    
    # Find the two endpoints that are farthest apart (longest path)
    # Get all nodes with degree 1 (endpoints/tips of the skeleton)
    endpoints = [n for n in graph.nodes() if graph.degree(n) == 1]

    # Find the longest shortest path between any two endpoints
    longest_path = []
    longest_length = 0

    for i, start in enumerate(endpoints):
        for end in endpoints[i+1:]:
            try:
                path = nx.shortest_path(graph, start, end, weight='weight')
                length = nx.shortest_path_length(graph, start, end, weight='weight')
                if length > longest_length:
                    longest_length = length
                    longest_path = path
            except nx.NetworkXNoPath:
                continue

    # Extract the actual pixel coordinates from the path
    coords = []
    for i in range(len(longest_path) - 1):
        edge = graph[longest_path[i]][longest_path[i+1]]
        coords.extend(edge['pts'].tolist())  # intermediate pixel coords

    coords = np.array(coords)  # shape (N, 2), each row is [row, col]
    black_image = np.zeros((int(new_width), int(new_width/img_ratio), 3), dtype=np.uint8)
    cv2.polylines(skele_img_display, [coords], isClosed=False, color=(0, 255, 0), thickness=3, lineType=cv2.LINE_AA)
    
    cv2.imshow('VIII. Graph', skele_img_display)
    
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