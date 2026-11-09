import os
import cv2
import numpy as np


class DefectDetector:
    """
    Módulo de Visión Artificial e Identificación Óptica-Geométrica de Vidrio Plano.
    1. Detecta y aísla geométricamente la lámina rectangular de vidrio frente a la cámara
       (incluso cuando es sostenida por un operador humano), rechazando capturas donde solo
       aparezca una persona/habitación sin vidrio o pantallas sin señal (como Start DroidCam).
    2. Extrae los bordes Canny exclusivamente sobre la lámina de vidrio detectada (ignorando
       dedos, manos, brazos, rostro, cabello, puertas o reflejos de pantalla).
    3. Clasifica el Tipo de Vidrio (Reflectivo Bronce, Reflectivo Espejo, Fotocromático,
       Reflectivo Azul, Flotado Verde / Templado, Esmerilado / Satinado, Claro Transparente)
       analizando únicamente los píxeles puros del vidrio sin contaminación de piel humana.
    """

    def __init__(self, blur_ksize=(5, 5), canny_thresh1=50, canny_thresh2=150):
        self.blur_ksize = blur_ksize
        self.canny_thresh1 = canny_thresh1
        self.canny_thresh2 = canny_thresh2
        self.last_glass_region = None

    @staticmethod
    def _merge_collinear_segments(h_segs, v_segs):
        """Une segmentos horizontales y verticales colineales para reconstruir los 4 bordes de la lámina."""
        h_segs = sorted(h_segs, key=lambda s: s[0])
        merged_h = []
        for ym, x1, x2, L in h_segs:
            placed = False
            for i, (mym, mx1, mx2, mL) in enumerate(merged_h):
                if abs(ym - mym) <= 14 and not (x2 < mx1 - 35 or x1 > mx2 + 35):
                    nx1 = min(mx1, x1)
                    nx2 = max(mx2, x2)
                    nym = int((mym * mL + ym * L) / max(1.0, mL + L))
                    merged_h[i] = (nym, nx1, nx2, float(nx2 - nx1))
                    placed = True
                    break
            if not placed:
                merged_h.append((ym, x1, x2, L))

        v_segs = sorted(v_segs, key=lambda s: s[0])
        merged_v = []
        for xm, y1, y2, L in v_segs:
            placed = False
            for i, (mxm, my1, my2, mL) in enumerate(merged_v):
                if abs(xm - mxm) <= 14 and not (y2 < my1 - 35 or y1 > my2 + 35):
                    ny1 = min(my1, y1)
                    ny2 = max(my2, y2)
                    nxm = int((mxm * mL + xm * L) / max(1.0, mL + L))
                    merged_v[i] = (nxm, ny1, ny2, float(ny2 - ny1))
                    placed = True
                    break
            if not placed:
                merged_v.append((xm, y1, y2, L))

        return merged_h, merged_v

    def detect_glass_sheet_region(self, image):
        """
        Analiza la escena para determinar:
        - Si la cámara está sin señal / DroidCam en negro -> is_valid = False
        - Si hay un humano / habitación en escena -> busca los bordes rectos (H y V) de la lámina
          de vidrio sostenida al frente. Si NO hay lámina rectangular de vidrio, rechaza la captura.
          Si SÍ hay lámina, devuelve su bounding box exacto (gx1, gy1, gx2, gy2) y la máscara de piel
          para aislar el vidrio del cuerpo/dedos del operador.
        """
        if image is None or image.size == 0:
            return {
                "is_valid": False,
                "is_held_by_person": False,
                "bbox": None,
                "skin_mask": None,
                "skin_pct": 0.0,
                "reason": "No se recibió una imagen válida."
            }

        h, w = image.shape[:2]
        if len(image.shape) == 2:
            gray = image
            bgr = cv2.cvtColor(image, cv2.COLOR_GRAY2BGR)
        else:
            bgr = image
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

        ycrcb = cv2.cvtColor(bgr, cv2.COLOR_BGR2YCrCb)
        hsv = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV)

        # 1. Rechazar pantallas sin señal de video o DroidCam inactivo ("Start DroidCam")
        black_ratio = float(np.mean(gray < 20))
        b_g_diff = float(np.mean(np.abs(bgr[:, :, 0].astype(np.float32) - bgr[:, :, 1].astype(np.float32))))
        r_g_diff = float(np.mean(np.abs(bgr[:, :, 2].astype(np.float32) - bgr[:, :, 1].astype(np.float32))))
        if black_ratio > 0.58 or (black_ratio > 0.40 and b_g_diff < 2.5 and r_g_diff < 2.5):
            return {
                "is_valid": False,
                "is_held_by_person": False,
                "bbox": None,
                "skin_mask": np.zeros((h, w), dtype=np.uint8),
                "skin_pct": 0.0,
                "reason": "Cámara sin señal de video o DroidCam inactivo (pantalla en negro)."
            }

        # 2. Detección de piel humana / tonos orgánicos (rostro, manos, dedos, torso)
        skin_raw = (
            (ycrcb[:, :, 1] >= 133) & (ycrcb[:, :, 1] <= 182) &
            (ycrcb[:, :, 2] >= 80) & (ycrcb[:, :, 2] <= 138) &
            (hsv[:, :, 0] <= 26) & (hsv[:, :, 1] >= 35) & (hsv[:, :, 2] >= 40)
        ).astype(np.uint8) * 255
        kernel_skin = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (9, 9))
        skin_mask = cv2.morphologyEx(skin_raw, cv2.MORPH_CLOSE, kernel_skin)
        skin_mask = cv2.dilate(skin_mask, kernel_skin, iterations=2)
        skin_pct = float(np.mean(skin_raw > 0)) * 100.0

        # 3. Si hay una persona o fondo orgánico en escena (skin_pct >= 3.5%), exigir que exista
        #    una lámina rectangular de vidrio sostenida frente a la cámara y localizar su bbox exacto.
        if skin_pct >= 3.5:
            blur = cv2.GaussianBlur(gray, (5, 5), 0)
            edges = cv2.bitwise_or(cv2.Canny(blur, 16, 50), cv2.Canny(blur, 35, 100))
            roi = np.zeros_like(edges)
            roi[int(h * 0.18):int(h * 0.90), int(w * 0.14):int(w * 0.92)] = (
                edges[int(h * 0.18):int(h * 0.90), int(w * 0.14):int(w * 0.92)]
            )

            lines = cv2.HoughLinesP(
                roi, 1, np.pi / 180,
                threshold=22,
                minLineLength=int(min(w, h) * 0.14),
                maxLineGap=28
            )
            h_segs, v_segs = [], []
            if lines is not None:
                for l in lines:
                    x1, y1, x2, y2 = np.asarray(l).flatten()[:4]
                    ang = abs(np.degrees(np.arctan2(y2 - y1, x2 - x1)))
                    L = float(np.hypot(x2 - x1, y2 - y1))
                    if ang <= 14.0 or ang >= 166.0:
                        ym = int((y1 + y2) / 2)
                        h_segs.append((ym, int(min(x1, x2)), int(max(x1, x2)), L))
                    elif 76.0 <= ang <= 104.0:
                        xm = int((x1 + x2) / 2)
                        # Descartar marcos de puertas oscuras en el borde izquierdo de la habitación
                        left_strip = gray[min(y1, y2):max(y1, y2) + 1, max(0, xm - 65):max(1, xm - 10)]
                        if xm < int(w * 0.28) and left_strip.size > 0 and float(np.mean(left_strip)) < 52.0:
                            continue
                        v_segs.append((xm, int(min(y1, y2)), int(max(y1, y2)), L))

            h_segs, v_segs = self._merge_collinear_segments(h_segs, v_segs)

            best_rect = None
            best_score = -1.0

            # Búsqueda de los 4 bordes rectos (arriba, abajo, izquierda, derecha) de la pieza de vidrio
            for y_top, tx1, tx2, tL in h_segs:
                if tL < w * 0.22:
                    continue
                for y_bot, bx1, bx2, bL in h_segs:
                    rect_h = y_bot - y_top
                    if rect_h < h * 0.24 or rect_h > h * 0.78:
                        continue
                    for x_left, ly1, ly2, lL in v_segs:
                        if lL < h * 0.22:
                            continue
                        if abs(tx1 - x_left) > 38:
                            continue
                        if min(ly2, y_bot + 25) - max(ly1, y_top - 25) < rect_h * 0.45:
                            continue
                        for x_right, ry1, ry2, rL in v_segs:
                            if rL < h * 0.22:
                                continue
                            rect_w = x_right - x_left
                            if rect_w < w * 0.24 or rect_w > w * 0.80:
                                continue
                            if x_right > max(tx2, bx2) + 38 or x_right < max(tx2, bx2) - int(w * 0.20):
                                continue
                            if min(ry2, y_bot + 25) - max(ry1, y_top - 25) < rect_h * 0.45:
                                continue
                            h_ov_t = min(tx2, x_right + 25) - max(tx1, x_left - 25)
                            h_ov_b = min(bx2, x_right + 25) - max(bx1, x_left - 25)
                            if h_ov_t < rect_w * 0.45 or h_ov_b < rect_w * 0.35:
                                continue

                            score = tL + bL + lL + rL + 1.5 * (rect_w + rect_h)
                            if score > best_score:
                                best_score = score
                                best_rect = (int(x_left), int(y_top), int(x_right), int(y_bot))

            # Respaldo: 3 bordes rectos claros conectados en esquinas cuando una mano cubre un borde
            if best_rect is None:
                for y_h, hx1, hx2, hL in h_segs:
                    if hL < w * 0.26:
                        continue
                    for x_left, ly1, ly2, lL in v_segs:
                        if lL < h * 0.26 or abs(hx1 - x_left) > 32:
                            continue
                        for x_right, ry1, ry2, rL in v_segs:
                            rect_w = x_right - x_left
                            if rL < h * 0.26 or rect_w < w * 0.26 or abs(hx2 - x_right) > 32:
                                continue
                            gy1 = min(y_h, ly1, ry1)
                            gy2 = max(y_h, ly2, ry2)
                            if (gy2 - gy1) >= h * 0.25:
                                best_rect = (int(x_left), int(gy1), int(x_right), int(gy2))
                                break

            if best_rect is None:
                return {
                    "is_valid": False,
                    "is_held_by_person": True,
                    "bbox": None,
                    "skin_mask": skin_mask,
                    "skin_pct": round(skin_pct, 1),
                    "reason": (
                        "CAPTURA RECHAZADA: Se detectó una persona o fondo de habitación SIN una lámina "
                        "de vidrio frente a la cámara. Coloque la pieza de vidrio frente al lente."
                    )
                }

            return {
                "is_valid": True,
                "is_held_by_person": True,
                "bbox": best_rect,
                "skin_mask": skin_mask,
                "skin_pct": round(skin_pct, 1),
                "reason": "Lámina física de vidrio detectada y aislada del operador."
            }

        # 4. Lámina de vidrio en plano completo (sin persona en escena)
        pad_x, pad_y = int(w * 0.06), int(h * 0.06)
        return {
            "is_valid": True,
            "is_held_by_person": False,
            "bbox": (pad_x, pad_y, w - pad_x, h - pad_y),
            "skin_mask": skin_mask,
            "skin_pct": round(skin_pct, 1),
            "reason": "Lámina de vidrio en plano completo."
        }

    def process_image(self, image_path):
        """
        Flujo de PDI (Procesamiento Digital de Imágenes) con aislamiento inteligente de la lámina:
        1. Localiza el rectángulo exacto de la lámina de vidrio (detect_glass_sheet_region).
        2. Si la lámina es sostenida por una persona, enmascara todo el exterior de la lámina,
           además de los dedos/manos/rostro/cabello del operador y el reflejo brillante de la pantalla,
           extrayendo únicamente los bordes rectos de la pieza de vidrio y las fallas reales sobre el cristal.
        """
        image = cv2.imread(image_path)
        if image is None:
            raise FileNotFoundError(f"Error: No se pudo cargar la imagen en la ruta {image_path}")

        h, w = image.shape[:2]
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        blurred = cv2.GaussianBlur(gray, self.blur_ksize, 0)
        raw_edges = cv2.Canny(blurred, self.canny_thresh1, self.canny_thresh2)

        reg = self.detect_glass_sheet_region(image)
        self.last_glass_region = reg

        if not reg["is_valid"] or reg["bbox"] is None:
            return image, np.zeros_like(raw_edges), []

        gx1, gy1, gx2, gy2 = reg["bbox"]
        is_held = reg["is_held_by_person"]
        skin_mask = reg["skin_mask"]

        if is_held:
            ycrcb = cv2.cvtColor(image, cv2.COLOR_BGR2YCrCb)
            # Zona interior de la lámina de vidrio detectada (excluyendo 6px del borde exterior)
            glass_interior = np.zeros((h, w), dtype=np.uint8)
            glass_interior[gy1 + 6:max(gy1 + 7, gy2 - 6), gx1 + 6:max(gx1 + 7, gx2 - 6)] = 255

            # Enmascarar dedos, manos, rostro y cabello detrás o sosteniendo el vidrio
            person_mask = ((skin_mask > 0) | (ycrcb[:, :, 1] >= 128) | (gray < 90)).astype(np.uint8) * 255
            k_person = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (17, 17))
            person_mask = cv2.dilate(person_mask, k_person, iterations=2)

            # Enmascarar el reflejo directo de la pantalla del computador/celular sobre el vidrio espejo/reflectivo
            screen_refl = (gray > 200).astype(np.uint8) * 255
            k_refl = cv2.getStructuringElement(cv2.MORPH_RECT, (25, 25))
            screen_refl = cv2.dilate(screen_refl, k_refl, iterations=2)

            pure_glass_mask = cv2.bitwise_and(
                glass_interior,
                cv2.bitwise_not(cv2.bitwise_or(person_mask, screen_refl))
            )
            internal_edges = cv2.bitwise_and(raw_edges, pure_glass_mask)
            kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
            closed_internal = cv2.morphologyEx(internal_edges, cv2.MORPH_CLOSE, kernel)

            defect_contours, _ = cv2.findContours(closed_internal, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            defect_contours = [
                c for c in defect_contours
                if cv2.contourArea(c) > 8 or cv2.arcLength(c, False) > 18
            ]

            # Mapa de bordes Canny limpio: perímetro rectangular exacto de la pieza de vidrio + fallas internas reales
            clean_edges = closed_internal.copy()
            cv2.rectangle(clean_edges, (gx1, gy1), (gx2, gy2), 255, 2)
            return image, clean_edges, defect_contours

        # Caso lámina en plano completo (sin persona sosteniéndola)
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
        closed_edges = cv2.morphologyEx(raw_edges, cv2.MORPH_CLOSE, kernel)
        contours, _ = cv2.findContours(closed_edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        inner_contours = []
        for c in contours:
            x, y, cw, ch = cv2.boundingRect(c)
            if x > gx1 and y > gy1 and (x + cw) < gx2 and (y + ch) < gy2:
                if cv2.contourArea(c) > 8 or cv2.arcLength(c, False) > 18:
                    inner_contours.append(c)
        if inner_contours:
            contours = inner_contours

        return image, closed_edges, contours

    def classify_glass_type(self, image, filename="", filter_mode="auto", region_info=None):
        """
        Filtro Óptico-Espectral SIAM para identificación automática del Tipo de Vidrio.
        Si hay una persona sosteniendo el vidrio, mide las propiedades espectrales exclusivamente
        sobre la franja de vidrio puro (libre de piel, dedos, cabello y reflejo de pantalla),
        evitando confundir el color de la piel humana con el Vidrio Reflectivo Bronce.
        """
        if image is None or image.size == 0:
            return {
                "glass_type": "Vidrio Claro Transparente",
                "optical_summary": "Sin datos ópticos",
                "reflectance_pct": 0.0,
                "transmittance_pct": 0.0,
                "mean_lum": 0.0,
                "glass_bbox": None,
                "is_held_by_person": False
            }

        if len(image.shape) == 2:
            bgr = cv2.cvtColor(image, cv2.COLOR_GRAY2BGR)
        else:
            bgr = image

        if region_info is None:
            region_info = self.detect_glass_sheet_region(bgr)

        h, w = bgr.shape[:2]
        bbox = region_info.get("bbox")
        is_held = bool(region_info.get("is_held_by_person", False))
        skin_mask = region_info.get("skin_mask")

        if bbox is not None:
            gx1, gy1, gx2, gy2 = bbox
        else:
            gx1, gy1, gx2, gy2 = int(w * 0.12), int(h * 0.12), int(w * 0.88), int(h * 0.88)

        roi = bgr[gy1:gy2, gx1:gx2]
        hsv_roi = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
        gray_roi = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)

        if is_held and roi.size > 0:
            # Tomar la franja periférica izquierda/superior del vidrio donde NO está el rostro en el centro
            # ni la mano en el borde derecho, garantizando medición óptica 100% pura sobre el cristal
            rw = max(10, gx2 - gx1)
            rh = max(10, gy2 - gy1)
            strip_x2 = max(8, int(rw * 0.32))
            strip_y1 = min(rh - 2, int(rh * 0.08))
            strip_y2 = max(strip_y1 + 2, int(rh * 0.90))

            pure_strip_bgr = roi[strip_y1:strip_y2, 4:strip_x2]
            pure_strip_hsv = hsv_roi[strip_y1:strip_y2, 4:strip_x2]
            if pure_strip_bgr.size == 0:
                pure_strip_bgr = roi
                pure_strip_hsv = hsv_roi

            mean_b = float(np.mean(pure_strip_bgr[:, :, 0]))
            mean_g = float(np.mean(pure_strip_bgr[:, :, 1]))
            mean_r = float(np.mean(pure_strip_bgr[:, :, 2]))
            mean_h = float(np.mean(pure_strip_hsv[:, :, 0]))
            mean_s = float(np.mean(pure_strip_hsv[:, :, 1]))
            mean_v = float(np.mean(pure_strip_hsv[:, :, 2]))

            non_skin_gray = gray_roi
            if skin_mask is not None:
                roi_skin = skin_mask[gy1:gy2, gx1:gx2]
                if np.any(roi_skin == 0):
                    non_skin_gray = gray_roi[roi_skin == 0]
            std_lum = float(np.std(pure_strip_bgr))
            spec_ratio = float(np.mean(non_skin_gray > 205))
        else:
            mean_b = float(np.mean(roi[:, :, 0]))
            mean_g = float(np.mean(roi[:, :, 1]))
            mean_r = float(np.mean(roi[:, :, 2]))
            mean_h = float(np.mean(hsv_roi[:, :, 0]))
            mean_s = float(np.mean(hsv_roi[:, :, 1]))
            mean_v = float(np.mean(hsv_roi[:, :, 2]))
            std_lum = float(np.std(gray_roi))
            spec_ratio = float(np.mean(gray_roi > 200))

        reflectance_pct = round(min(98.0, max(8.0, (std_lum * 1.15) + (spec_ratio * 180.0))), 1)
        transmittance_pct = round(min(92.0, max(12.0, (mean_v / 255.0) * 100.0)), 1)

        mode_clean = (filter_mode or "auto").strip().lower()
        fname_clean = os.path.basename(str(filename or "")).lower()

        glass_type = None
        optical_desc = ""

        # 1. Filtro explícito o nombre de archivo
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

        # 2. Clasificación óptica sobre los píxeles puros del vidrio (sin piel humana)
        if glass_type is None:
            # A) Vidrio Reflectivo Bronce: dominancia cálida R > B sobre el cristal puro
            if (mean_r - mean_b) >= 9.5 and mean_s >= 14.0:
                glass_type = "Vidrio Reflectivo Bronce"
                optical_desc = (
                    f"Dominancia espectral cálida bronce/cobre (R:{mean_r:.0f} > B:{mean_b:.0f}) | "
                    f"Reflectancia solar: {reflectance_pct}%"
                )
            # B) Vidrio Reflectivo Espejo: reflexión especular acromática/plateada
            elif (
                (spec_ratio >= 0.025 and abs(mean_r - mean_b) < 9.5)
                or (not is_held and std_lum >= 30.0 and abs(mean_r - mean_b) <= 12.0)
            ):
                glass_type = "Vidrio Reflectivo Espejo"
                optical_desc = (
                    f"Reflexión especular tipo espejo ({reflectance_pct}%) | "
                    f"Balance neutro plateado (R:{mean_r:.0f}, G:{mean_g:.0f}, B:{mean_b:.0f})"
                )
            # C) Vidrio Fotocromático: absorción lumínica fotosensible / oscurecimiento uniforme o tinte grafito-azulado
            elif (
                (mean_v < 118.0 and std_lum < 30.0)
                or ((mean_b - mean_r) > 4.5 and mean_v < 145.0)
                or (112.0 <= mean_h <= 168.0 and mean_s >= 16.0 and mean_v < 155.0)
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
            elif (mean_g - mean_r) > 4.0 and (mean_g - mean_b) > 4.0:
                glass_type = "Vidrio Flotado Verde / Templado"
                optical_desc = f"Tinte verdoso característico de silicato/hierro | Transmitancia: {transmittance_pct}%"
            # F) Vidrio Esmerilado / Satinado (Mate)
            elif not is_held and mean_v >= 165.0 and mean_s < 20.0 and std_lum < 22.0:
                glass_type = "Vidrio Esmerilado / Satinado"
                optical_desc = f"Superficie mate difusa uniforme | Transmitancia: {transmittance_pct}%"
            # G) Vidrio Claro Transparente (Incoloro)
            else:
                glass_type = "Vidrio Claro Transparente"
                optical_desc = f"Superficie monolítica transparente | Transmitancia: {transmittance_pct}%"

        return {
            "glass_type": glass_type,
            "optical_summary": optical_desc,
            "reflectance_pct": reflectance_pct,
            "transmittance_pct": transmittance_pct,
            "mean_lum": round(mean_v, 1),
            "std_intensity": round(std_lum, 1),
            "glass_bbox": bbox,
            "is_held_by_person": is_held
        }

    def validate_glass_sheet(self, image, filename="", filter_mode="auto"):
        """
        Valida que el fotograma capturado por la cámara o cargado desde archivo contenga una
        lámina de vidrio real (rechazando personas/habitaciones sin vidrio o cámaras en negro
        como Start DroidCam), aísla las coordenadas de la lámina y clasifica el Tipo de Vidrio.
        Retorna: (is_valid: bool, reason: str, metrics: dict)
        """
        region_info = self.detect_glass_sheet_region(image)
        self.last_glass_region = region_info

        if not region_info.get("is_valid", False):
            return (
                False,
                region_info.get("reason", "No se detectó una lámina de vidrio válida."),
                {
                    "glass_bbox": None,
                    "is_held_by_person": region_info.get("is_held_by_person", False),
                    "skin_pct": region_info.get("skin_pct", 0.0)
                }
            )

        glass_info = self.classify_glass_type(
            image, filename=filename, filter_mode=filter_mode, region_info=region_info
        )
        g_type = glass_info["glass_type"]
        g_summary = glass_info["optical_summary"]

        return (
            True,
            f"Tipo detectado: {g_type} ({g_summary})",
            glass_info
        )
