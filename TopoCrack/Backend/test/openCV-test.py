import cv2
import numpy as np
import skimage as sk

img = cv2.imread('./img/crack01.jpg', cv2.IMREAD_GRAYSCALE)
img_width, img_height = img.shape[:2]
print("Width:", img_width, "\nHeight:", img_height)
img_ratio = img_width/img_height
new_width = 600
img = cv2.resize(img, (int(new_width), int(new_width/img_ratio)))

cv2.imshow('I. Crack 01 - B/W', img)

clahe1 = cv2.createCLAHE(clipLimit=3)
# clahe2 = cv2.createCLAHE(clipLimit=6)

clahe_img_1 = np.clip(clahe1.apply(img), 0, 255).astype(np.uint8)
cv2.imshow('II. Crack 01 - CLAHE1', clahe_img_1)

# clahe_img_2 = np.clip(clahe2.apply(img), 0, 255).astype(np.uint8)
# cv2.imshow('Crack 01 - CLAHE2', clahe_img_2)

# GAUSSIAN BLUR - Bad looking, removed
# filtered_img_1 = cv2.GaussianBlur(clahe_img_1, (5, 5), 0)
# filtered_img_1_2 = cv2.GaussianBlur(clahe_img_1, (5, 5), 100)
# filtered_img_2 = cv2.GaussianBlur(clahe_img_2, (5, 5), 0)
# cv2.imshow('Filtered 1 - Guassian', filtered_img_1)
# cv2.imshow('Filtered 1_2 - Guassian', filtered_img_1_2)
# cv2.imshow('Filtered 2 - Guassian', filtered_img_2)

d = 10
sigmaColor = sigmaSpace = 100

uInput = ""
print("W=>d+=1; S=>d-=1; E=>sigmaColor+=5; D=>sigmaColor-=5; R=>sigmaSpace+=5; F=>sigmaSpace-=5; quit=>Exit")

while uInput != "quit":  
  print(f"d={d}; sigmaColor={sigmaColor}; sigmaSpace{sigmaSpace}")
  
   # BILATERAL FILTERING - Good
  filtered_img_1 = cv2.bilateralFilter(clahe_img_1, d, sigmaColor, sigmaSpace)
  # filtered_img_2 = cv2.bilateralFilter(clahe_img_2, 15, 75, 75)

  cv2.imshow('III. Filtered 1 - Bilateral', filtered_img_1)
  # cv2.imshow('Filtered 2 - Bilateral', filtered_img_2)


  # Dopo il bilateral filter, Canny invece di threshold diretta
  median1 = np.median(filtered_img_1.flatten())
  lower1 = 0.66 * median1
  upper1 = 1.33 * median1
  thresholds1 = [lower1, upper1]
  canned_img_1 = cv2.Canny(filtered_img_1, int(thresholds1[0]), int(thresholds1[1]))

  cv2.imshow('IV. Edges 1 - Canny', canned_img_1)

  # Closing per chiudere i gap nei bordi
  kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (5, 5))
  closed_img_1 = cv2.morphologyEx(canned_img_1, cv2.MORPH_CLOSE, kernel)
  cv2.imshow('V. Closed 1 - morphologyEx', closed_img_1)

  # Ora binarizza (è già quasi binaria, ma per sicurezza)
  _, binary_img_1 = cv2.threshold(closed_img_1, 127, 255, cv2.THRESH_BINARY)
  cv2.imshow('VI. Binary 1 - Otsu', binary_img_1)

  # Skeletonize
  skele_img_1 = sk.morphology.skeletonize(binary_img_1 > 0)

  # Converti in uint8 per OpenCV: True→255, False→0
  skele_img_display = skele_img_1.astype(np.uint8) * 255
  cv2.imshow('VII. Skele 1 - skeletonize', skele_img_display)
  
  key = cv2.waitKey(0) & 0xFF  # aspetta tasto sulla finestra OpenCV
  
  # Input Polling
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

# Destroy all the windows
cv2.destroyAllWindows()