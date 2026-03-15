import cv2
import numpy as np
import skimage as sk

img = cv2.imread('./img/crack01.jpg', cv2.IMREAD_GRAYSCALE)
img_width, img_height = img.shape[:2]
print("Width:", img_width, "\nHeight:", img_height)
img_ratio = img_width/img_height
new_width = 600
img = cv2.resize(img, (int(new_width), int(new_width/img_ratio)))

cv2.imshow('Crack 01 - B/W', img)

clahe1 = cv2.createCLAHE(clipLimit=3)
# clahe2 = cv2.createCLAHE(clipLimit=6)

clahe_img_1 = np.clip(clahe1.apply(img), 0, 255).astype(np.uint8)
cv2.imshow('Crack 01 - CLAHE1', clahe_img_1)

# clahe_img_2 = np.clip(clahe2.apply(img), 0, 255).astype(np.uint8)
# cv2.imshow('Crack 01 - CLAHE2', clahe_img_2)

# GAUSSIAN BLUR - Bad looking, removed
# filtered_img_1 = cv2.GaussianBlur(clahe_img_1, (5, 5), 0)
# filtered_img_1_2 = cv2.GaussianBlur(clahe_img_1, (5, 5), 100)
# filtered_img_2 = cv2.GaussianBlur(clahe_img_2, (5, 5), 0)
# cv2.imshow('Filtered 1 - Guassian', filtered_img_1)
# cv2.imshow('Filtered 1_2 - Guassian', filtered_img_1_2)
# cv2.imshow('Filtered 2 - Guassian', filtered_img_2)

# BILATERAL FILTERING - Good
filtered_img_1 = cv2.bilateralFilter(clahe_img_1, 15, 75, 75)
# filtered_img_2 = cv2.bilateralFilter(clahe_img_2, 15, 75, 75)

cv2.imshow('Filtered 1 - Bilateral', filtered_img_1)
# cv2.imshow('Filtered 2 - Bilateral', filtered_img_2)

# EDGE DETECTION - Why use this? Anyway, it doesn't work well with this configuration
# median1 = np.median(filtered_img_1.flatten())
# lower1 = 0.66 * median1
# upper1 = 1.33 * median1
# thresholds1 = [lower1, upper1]
# median2 = np.median(filtered_img_2.flatten())
# lower2 = 0.66 * median2
# upper2 = 1.33 * median2
# thresholds2 = [lower2, upper2]
# print(lower1, upper1, "\n", lower2, upper2)
# canned_img_1 = cv2.Canny(filtered_img_1, int(thresholds1[0]), int(thresholds1[1]))
# canned_img_2 = cv2.Canny(filtered_img_2, int(thresholds2[0]), int(thresholds2[1]))
# cv2.imshow('Canned 1 - Canny', canned_img_1)
# cv2.imshow('Canned 2 - Canny', canned_img_2)

# Morphological closing
kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3,3))
closed_img_1 = cv2.morphologyEx(filtered_img_1, cv2.MORPH_CLOSE, kernel)
cv2.imshow('Closed 1 - morphologyEx', closed_img_1)

# Skeletonize
skele_img_1 = sk.morphology.skeletonize(closed_img_1)

# Converts the boolean array returned by skeletonize to an array of uin8 so that it is OpenCV compatible
skele_opencv = (skele_img_1 * 255).astype(np.uint8)
cv2.imshow('Skele 1 - skeletonize', skele_opencv)

cv2.waitKey(0)

cv2.destroyAllWindows()
