import cv2
import numpy as np

class DefectDetector:
    """
    Módulo de Visión Artificial.
    Se encarga de preprocesar imágenes de vidrio plano y detectar anomalías 
    (fisuras, burbujas, etc.) utilizando el Operador de Bordes de Canny.
    """
    def __init__(self, blur_ksize=(5, 5), canny_thresh1=50, canny_thresh2=150):
        # El Kernel Gaussiano nos ayuda a "suavizar" la imagen y omitir ruido leve (como polvo)
        self.blur_ksize = blur_ksize
        # Umbrales para la histéresis del filtro Canny
        self.canny_thresh1 = canny_thresh1
        self.canny_thresh2 = canny_thresh2

    def process_image(self, image_path):
        """
        Flujo de PDI (Procesamiento Digital de Imágenes):
        1. Escala de grises -> 2. Desenfoque -> 3. Canny -> 4. Contornos
        """
        # 1. Cargar imagen en memoria
        image = cv2.imread(image_path)
        if image is None:
            raise FileNotFoundError(f"Error: No se pudo cargar la imagen en la ruta {image_path}")
            
        # 2. Convertir a escala de grises (simplifica el canal de color para el cálculo de gradientes)
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        
        # 3. Aplicar Desenfoque Gaussiano (Gaussian Blur)
        blurred = cv2.GaussianBlur(gray, self.blur_ksize, 0)
        
        # 4. Operador Canny (Calcula gradientes de intensidad para encontrar los bordes de la falla)
        edges = cv2.Canny(blurred, self.canny_thresh1, self.canny_thresh2)
        
        # 5. Encontrar contornos cerrados a partir de los bordes detectados
        # cv2.RETR_EXTERNAL: Solo tomamos los bordes externos de la falla
        # cv2.CHAIN_APPROX_SIMPLE: Comprime segmentos rectos para ahorrar memoria
        contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        return image, edges, contours
