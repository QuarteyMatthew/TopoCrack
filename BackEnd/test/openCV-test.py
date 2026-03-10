import cv2
import numpy as np

img = cv2.imread('./img/crack02.jpg', cv2.IMREAD_GRAYSCALE)
img_width, img_height = img.shape[:2]
print("Width:", img_width, "\nHeight:", img_height)
img_ratio = img_width/img_height
new_width = 200
img = cv2.resize(img, (int(new_width), int(new_width/img_ratio)))

cv2.imshow('Crack 01 - B/W', img)

clahe1 = cv2.createCLAHE(clipLimit=3)
clahe2 = cv2.createCLAHE(clipLimit=6)

clahe_img_1 = np.clip(clahe1.apply(img), 0, 255).astype(np.uint8)
cv2.imshow('Crack 01 - CLAHE1', clahe_img_1)

clahe_img_2 = np.clip(clahe2.apply(img), 0, 255).astype(np.uint8)
cv2.imshow('Crack 01 - CLAHE2', clahe_img_2)

# GAUSSIAN BLUR - Bad looking, removed
# filtered_img_1 = cv2.GaussianBlur(clahe_img_1, (5, 5), 0)
# filtered_img_1_2 = cv2.GaussianBlur(clahe_img_1, (5, 5), 100)
# filtered_img_2 = cv2.GaussianBlur(clahe_img_2, (5, 5), 0)
# cv2.imshow('Filtered 1 - Guassian', filtered_img_1)
# cv2.imshow('Filtered 1_2 - Guassian', filtered_img_1_2)
# cv2.imshow('Filtered 2 - Guassian', filtered_img_2)

filtered_img_1 = cv2.bilateralFilter(clahe_img_1, 15, 75, 75)
filtered_img_2 = cv2.bilateralFilter(clahe_img_2, 15, 75, 75)

cv2.imshow('Filtered 1 - Bilateral', filtered_img_1)
cv2.imshow('Filtered 2 - Bilateral', filtered_img_2)

cv2.waitKey(0)

cv2.destroyAllWindows()
