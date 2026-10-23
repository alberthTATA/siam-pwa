import cv2
import numpy as np

class FeatureExtractor:
    """
    Extrae propiedades geométricas y morfológicas de los contornos detectados por el detector Canny.
    Estos valores numéricos normalizados serán las verdaderas "Entradas" (Inputs) 
    de nuestra Red Neuronal Artificial para que pueda clasificar el defecto.
    """
    
    @staticmethod
    def extract_features(contour):
        """
        Analiza un contorno individual y extrae 5 características matemáticas clave.
        Retorna un array: [Área, Perímetro, Circularidad, Relación Aspecto, Extensión]
        """
        # 1. Área del defecto (cantidad de píxeles que abarca)
        area = cv2.contourArea(contour)
        
        # 2. Perímetro (longitud del borde)
        perimeter = cv2.arcLength(contour, True)
        
        # 3. Circularidad (Fórmula matemática que va de 0 a 1)
        # Si tiende a 1 es una burbuja. Si tiende a 0 puede ser una fisura alargada.
        circularity = 0
        if perimeter > 0:
            circularity = (4 * np.pi * area) / (perimeter ** 2)
            
        # Obtenemos las coordenadas de la "Caja Delimitadora" (Bounding Box)
        # x, y son las coordenadas de inicio; w, h son ancho y alto.
        x, y, w, h = cv2.boundingRect(contour)
        
        # 4. Relación de Aspecto (Ancho / Alto)
        # Ayuda a distinguir rayaduras (muy anchas o muy altas) de inclusiones (más simétricas)
        aspect_ratio = float(w) / h if h > 0 else 0
        
        # 5. Extensión (Proporción del área del contorno vs el área de su caja delimitadora)
        bounding_box_area = w * h
        extent = float(area) / bounding_box_area if bounding_box_area > 0 else 0
        
        # Empaquetamos todo en un arreglo NumPy listo para alimentar la Red Neuronal (Capa de entrada de 5 nodos)
        return np.array([area, perimeter, circularity, aspect_ratio, extent])
