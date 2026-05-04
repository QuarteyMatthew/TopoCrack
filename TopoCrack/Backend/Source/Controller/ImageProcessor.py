import cv2
import numpy as np

from PIL import Image
import io

from fastapi import UploadFile

class ImageProcessor:
    @staticmethod
    def LoadImage(uploadFile: UploadFile):
        return cv2.imdecode(np.frombuffer(uploadFile.read(), np.uint8), cv2.IMREAD_COLOR)
    
    @staticmethod
    def ValidateImage(image: Image):
        if image is None:
            raise ValueError("Invalid image")
        
        return image;

    def Preprocess(image):
        return cv2.resize(image, (256, 256))