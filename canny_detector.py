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
        
        # Cerrar micro-brechas en trazos de rayones/fisuras reales capturados por cámara
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
        closed_edges = cv2.morphologyEx(edges, cv2.MORPH_CLOSE, kernel)
        
        # 5. Encontrar contornos a partir de los bordes detectados
        contours, _ = cv2.findContours(closed_edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        # Priorizar contornos dentro de la zona central de inspección de la lámina (evitando bordes del marco de cámara)
        h, w = gray.shape[:2]
        pad_x, pad_y = int(w * 0.08), int(h * 0.08)
        inner_contours = []
        for c in contours:
            x, y, cw, ch = cv2.boundingRect(c)
            if x > pad_x and y > pad_y and (x + cw) < (w - pad_x) and (y + ch) < (h - pad_y):
                if cv2.contourArea(c) > 8 or cv2.arcLength(c, False) > 18:
                    inner_contours.append(c)
        if inner_contours:
            contours = inner_contours
        
        return image, edges, contours

    def classify_glass_type(self, image, filename="", filter_mode="auto"):
        """
        Filtro Óptico-Espectral SIAM para identificación automática del Tipo de Vidrio
        tanto en capturas de cámara en vivo como en fotografías subidas desde archivo.
        Analiza reflectancia especular, dominancia cromática BGR/HSV, atenuación lumínica
        (fotocromatismo) y dispersión de superficie.
        """
        if image is None or image.size == 0:
            return {
                "glass_type": "Vidrio Claro Transparente",
                "optical_summary": "Sin datos ópticos",
                "reflectance_pct": 0.0,
                "transmittance_pct": 0.0,
                "mean_lum": 0.0
            }

        if len(image.shape) == 2:
            bgr = cv2.cvtColor(image, cv2.COLOR_GRAY2BGR)
        else:
            bgr = image

        h, w = bgr.shape[:2]
        y1, y2 = int(h * 0.12), max(int(h * 0.12) + 1, int(h * 0.88))
        x1, x2 = int(w * 0.12), max(int(w * 0.12) + 1, int(w * 0.88))
        roi = bgr[y1:y2, x1:x2]

        hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
        gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)

        mean_b = float(np.mean(roi[:, :, 0]))
        mean_g = float(np.mean(roi[:, :, 1]))
        mean_r = float(np.mean(roi[:, :, 2]))
        mean_h = float(np.mean(hsv[:, :, 0]))
        mean_s = float(np.mean(hsv[:, :, 1]))
        mean_v = float(np.mean(hsv[:, :, 2]))
        std_lum = float(np.std(gray))
        spec_ratio = float(np.mean(gray > 200))

        # Estimación de reflectancia y transmitancia aparente
        reflectance_pct = round(min(98.0, max(8.0, (std_lum * 1.15) + (spec_ratio * 120.0))), 1)
        transmittance_pct = round(min(92.0, max(12.0, (mean_v / 255.0) * 100.0)), 1)

        mode_clean = (filter_mode or "auto").strip().lower()
        fname_clean = os.path.basename(str(filename or "")).lower()

        glass_type = None
        optical_desc = ""

        # 1. Si el usuario seleccionó un filtro óptico específico o el archivo indica el patrón
        if mode_clean == "bronce" or "bronce" in fname_clean:
            glass_type = "Vidrio Reflectivo Bronce"
            optical_desc = f"Tono cálido bronce/ámbar (R-B: +{max(8.0, mean_r - mean_b):.1f}) | Reflectancia: {reflectance_pct}%"
        elif mode_clean == "espejo" or "espejo" in fname_clean:
            glass_type = "Vidrio Reflectivo Espejo"
            optical_desc = f"Alta reflectancia especular plateada ({reflectance_pct}%) | Contraste óptico: {std_lum:.1f}"
        elif mode_clean == "fotocromatico" or "fotocrom" in fname_clean or "polariz" in fname_clean:
            glass_type = "Vidrio Fotocromático"
            optical_desc = f"Atenuación fotosensible activa | Transmitancia lumínica: {transmittance_pct}%"
        elif mode_clean == "templado" or "templad" in fname_clean or "verde" in fname_clean:
            glass_type = "Vidrio Flotado Verde / Templado"
            optical_desc = f"Espectro verdoso de óxido de hierro | Transmitancia: {transmittance_pct}%"
        elif mode_clean == "esmerilado" or "esmeril" in fname_clean or "satin" in fname_clean:
            glass_type = "Vidrio Esmerilado / Satinado"
            optical_desc = f"Superficie difusa translúcida | Dispersión: {std_lum:.1f}"
        elif mode_clean == "claro":
            glass_type = "Vidrio Claro Transparente"
            optical_desc = f"Monolítico incoloro de alta transmitancia ({transmittance_pct}%)"

        # 2. Detección automática por parámetros espectrales y de reflectancia de la imagen
        if glass_type is None:
            # A) Vidrio Reflectivo Bronce: dominancia cálida R > B con saturación apreciable
            if (mean_r - mean_b) > 7.5 and mean_s >= 14.0:
                glass_type = "Vidrio Reflectivo Bronce"
                optical_desc = (
                    f"Dominancia espectral cálida bronce/cobre (R:{mean_r:.0f} > B:{mean_b:.0f}) | "
                    f"Reflectancia solar: {reflectance_pct}%"
                )
            # B) Vidrio Reflectivo Espejo: alto contraste de reflexión especular con balance cromático neutro/plateado
            elif (std_lum >= 30.0 and abs(mean_r - mean_b) <= 12.0) or (spec_ratio > 0.045 and mean_s < 42.0):
                glass_type = "Vidrio Reflectivo Espejo"
                optical_desc = (
                    f"Reflexión especular tipo espejo ({reflectance_pct}%) | "
                    f"Balance neutro plateado (R:{mean_r:.0f}, G:{mean_g:.0f}, B:{mean_b:.0f})"
                )
            # C) Vidrio Fotocromático: absorción lumínica / oscurecimiento fotosensible o tinte gris-azulado/grafito
            elif (
                (mean_v < 118.0 and std_lum < 30.0)
                or ((mean_b - mean_r) > 4.5 and mean_v < 148.0)
                or (112.0 <= mean_h <= 168.0 and mean_s >= 16.0 and mean_v < 160.0)
            ):
                glass_type = "Vidrio Fotocromático"
                optical_desc = (
                    f"Filtro fotosensible / absorción UV-Visible activa | "
                    f"Transmitancia: {transmittance_pct}% (Luminancia: {mean_v:.0f}/255)"
                )
            # D) Vidrio Reflectivo Azul / Control Solar
            elif (mean_b - mean_r) > 12.0 and mean_s >= 20.0:
                glass_type = "Vidrio Reflectivo Azul (Control Solar)"
                optical_desc = f"Tono espectral azul reflectivo | Reflectancia: {reflectance_pct}%"
            # E) Vidrio Flotado Verde / Templado
            elif (mean_g - mean_r) > 4.5 and (mean_g - mean_b) > 4.5:
                glass_type = "Vidrio Flotado Verde / Templado"
                optical_desc = f"Tinte verdoso característico de silicato/hierro | Transmitancia: {transmittance_pct}%"
            # F) Vidrio Esmerilado / Satinado (Mate)
            elif mean_v >= 165.0 and mean_s < 20.0 and std_lum < 22.0:
                glass_type = "Vidrio Esmerilado / Satinado"
                optical_desc = f"Superficie mate difusa uniforme | Transmitancia: {transmittance_pct}%"
            # G) Vidrio Claro Transparente (Incoloro)
            else:
                glass_type = "Vidrio Claro Transparente"
                optical_desc = f"Superficie monolítica incolora | Transmitancia: {transmittance_pct}%"

        return {
            "glass_type": glass_type,
            "optical_summary": optical_desc,
            "reflectance_pct": reflectance_pct,
            "transmittance_pct": transmittance_pct,
            "mean_lum": round(mean_v, 1),
            "std_intensity": round(std_lum, 1)
        }

    def validate_glass_sheet(self, image, filename="", filter_mode="auto"):
        """
        Valida que el fotograma capturado por la cámara o cargado desde archivo sea una imagen
        ópticamente válida para inspección de vidrio plano e identifica automáticamente el
        Tipo de Vidrio (Reflectivo Bronce, Reflectivo Espejo, Fotocromático, Templado, Claro, etc.).
        Retorna: (is_valid: bool, reason: str, metrics: dict)
        """
        if image is None or image.size == 0:
            return False, "No se recibió una imagen válida.", {}

        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if len(image.shape) == 3 else image
        mean_lum = float(np.mean(gray))
        std_intensity = float(np.std(gray))

        # Solo rechazar si el lente de la cámara está completamente tapado / negro total
        if mean_lum < 2.0 and std_intensity < 1.5:
            return (
                False,
                "La cámara entrega una imagen completamente oscura. Verifique que el lente esté descubierto.",
                {"mean_lum": mean_lum, "std_intensity": std_intensity}
            )

        glass_info = self.classify_glass_type(image, filename=filename, filter_mode=filter_mode)
        g_type = glass_info["glass_type"]
        g_summary = glass_info["optical_summary"]

        return (
            True,
            f"Tipo detectado: {g_type} ({g_summary})",
            glass_info
        )
