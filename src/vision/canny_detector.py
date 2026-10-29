import os
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

    def validate_glass_sheet(self, image):
        """
        Valida mediante parámetros ópticos, cromáticos y morfológicos si la imagen capturada
        o cargada corresponde realmente a una lámina de vidrio plano y NO a una persona, 
        rostro, fondo de habitación u objeto ajeno.
        Retorna: (is_valid: bool, reason: str, metrics: dict)
        """
        if image is None or image.size == 0:
            return False, "No se recibió una imagen válida.", {}

        h, w = image.shape[:2]
        total_pixels = float(h * w)

        # 1. Detección biométrica de rostros/personas frente a la cámara (Haar Cascade de OpenCV)
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        try:
            cascade_path = os.path.join(cv2.data.haarcascades, 'haarcascade_frontalface_default.xml')
            if os.path.exists(cascade_path):
                face_cascade = cv2.CascadeClassifier(cascade_path)
                faces = face_cascade.detectMultiScale(
                    gray, scaleFactor=1.1, minNeighbors=5, minSize=(int(min(w, h) * 0.12), int(min(w, h) * 0.12))
                )
                if len(faces) > 0:
                    return (
                        False,
                        "Se detectó una persona/rostro frente a la cámara. El sistema SIAM requiere enfocar exclusivamente una lámina de vidrio plano.",
                        {"faces": len(faces)}
                    )
        except Exception:
            pass

        # 2. Análisis de saturación y cromaticidad (espacio HSV y YCrCb)
        hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
        mean_sat = float(np.mean(hsv[:, :, 1]))
        high_sat_ratio = float(np.sum(hsv[:, :, 1] > 95)) / total_pixels

        ycrcb = cv2.cvtColor(image, cv2.COLOR_BGR2YCrCb)
        skin_mask = cv2.inRange(ycrcb, np.array([40, 135, 85], dtype=np.uint8), np.array([255, 180, 135], dtype=np.uint8))
        sat_mask = cv2.inRange(hsv[:, :, 1], 35, 255)
        warm_organic_mask = cv2.bitwise_and(skin_mask, sat_mask)
        warm_ratio = float(np.count_nonzero(warm_organic_mask)) / total_pixels

        if warm_ratio > 0.14:
            return (
                False,
                f"Parámetros ópticos fuera de rango (Tonos orgánicos/cálidos: {warm_ratio*100:.1f}% > 14% máx). La imagen contiene objetos, piel, madera o fondos de habitación que no corresponden a una lámina de vidrio.",
                {"warm_ratio": warm_ratio, "mean_sat": mean_sat}
            )

        if mean_sat > 68.0 or high_sat_ratio > 0.22:
            return (
                False,
                f"Saturación cromática excesiva para vidrio plano (Saturación media: {mean_sat:.1f}/255). Una lámina de vidrio debe presentar una superficie translúcida, neutra o de tono uniforme.",
                {"mean_sat": mean_sat, "high_sat_ratio": high_sat_ratio}
            )

        # 3. Homogeneidad de superficie y densidad de bordes (Canny)
        blurred = cv2.GaussianBlur(gray, self.blur_ksize, 0)
        edges = cv2.Canny(blurred, self.canny_thresh1, self.canny_thresh2)
        edge_density = float(np.count_nonzero(edges)) / total_pixels
        contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        significant_contours = [c for c in contours if cv2.contourArea(c) > 25]
        std_intensity = float(np.std(blurred))

        if edge_density > 0.12 or len(significant_contours) > 45:
            return (
                False,
                f"Complejidad estructural excesiva (Densidad de bordes: {edge_density*100:.1f}%, Objetos: {len(significant_contours)}). La escena muestra un entorno complejo en lugar de una lámina de vidrio.",
                {"edge_density": edge_density, "contours": len(significant_contours)}
            )

        if std_intensity > 62.0 and mean_sat > 25.0:
            return (
                False,
                f"Falta de homogeneidad óptica en la superficie (Dispersión lumínica: {std_intensity:.1f}). Enfoque directamente la lámina de vidrio sobre un fondo liso o mesa de corte.",
                {"std_intensity": std_intensity}
            )

        return True, "Superficie de lámina de vidrio verificada correctamente.", {
            "mean_sat": mean_sat,
            "edge_density": edge_density,
            "std_intensity": std_intensity
        }
