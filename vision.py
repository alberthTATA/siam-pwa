# -*- coding: utf-8 -*-
"""
SIAM - Módulo de Visión Artificial y Optimización 2D para Flask
Integración de OpenCV (Canny), Red Neuronal (Clasificación) y Heurística FFD (Bin Packing)
Empresa: Aluminios Cristales Villegas
"""

import os
import cv2
import base64
import numpy as np

from src.vision.canny_detector import DefectDetector
from src.vision.feature_extractor import FeatureExtractor
from src.optimization.bin_packing import GlassSheet
from src.optimization.obstacle_avoidance import BinPacker
from src.neural_network.network import NeuralNetwork
from src.neural_network.layer import Layer_Dense
from src.neural_network.activations import Activation_ReLU, Activation_Sigmoid

# Carga Singleton de la Red Neuronal para no recrearla en cada petición HTTP
_nn_model = None
_norm_max = None
_nn_loaded = False

def get_neural_network():
    """Inicializa la red neuronal y carga los pesos una sola vez en memoria."""
    global _nn_model, _norm_max, _nn_loaded
    if _nn_loaded:
        return _nn_model, _norm_max

    try:
        model = NeuralNetwork()
        model.add(Layer_Dense(5, 16))
        model.add(Activation_ReLU())
        model.add(Layer_Dense(16, 16))
        model.add(Activation_ReLU())
        model.add(Layer_Dense(16, 3))
        model.add(Activation_Sigmoid())

        weights_path = os.path.join(os.path.dirname(__file__), 'src', 'model_weights.pkl')
        norm_path = os.path.join(os.path.dirname(__file__), 'src', 'normalization_max.npy')

        if os.path.exists(weights_path) and os.path.exists(norm_path):
            model.load_weights(weights_path)
            _norm_max = np.load(norm_path)
            _nn_model = model
            _nn_loaded = True
            print("[SIAM] Red Neuronal cargada exitosamente en el servidor Flask.")
        else:
            print("[SIAM] Pesos de la Red Neuronal no encontrados. Se usará clasificación heurística.")
            _nn_model = None
    except Exception as e:
        print(f"[SIAM] Error al cargar la red neuronal: {e}")
        _nn_model = None

    return _nn_model, _norm_max

def evaluate_quality_control(defect_type, area, perimeter, circularity):
    """
    Evalúa el estado de control de calidad según parámetros de tolerancia industrial:
    - Rotura: siempre RECHAZADO (falla crítica estructural).
    - Rayón:
        - Si área < 120 mm²: APROBADO CON CONDICIÓN (Leve/Superficial, apto para corte secundario).
        - Si área >= 120 mm²: RECHAZADO (Rayón profundo/extenso).
    - Burbuja:
        - Si área < 80 mm²: APROBADO (Microburbuja dentro de norma de tolerancia).
        - Si área >= 80 mm²: RECHAZADO (Burbuja oclusiva).
    """
    defect_type_lower = defect_type.lower()
    
    if "rotura" in defect_type_lower:
        return (
            "RECHAZADO", 
            "CRÍTICA", 
            "Lámina con fractura estructural. Peligro inminente de quiebre en mesa de corte. Enviar a merma total."
        )
    elif "rayon" in defect_type_lower or "rayón" in defect_type_lower:
        if area < 120.0:
            return (
                "APROBADO CON CONDICIÓN", 
                "LEVE", 
                f"Rayón superficial dentro de tolerancia ({area:.1f} mm² < 120 mm² límite). Apto para piezas secundarias o pulido."
            )
        else:
            return (
                "RECHAZADO", 
                "GRAVE", 
                f"Rayón extenso o profundo ({area:.1f} mm² >= 120 mm² límite). No cumple con el estándar estético de entrega."
            )
    elif "burbuja" in defect_type_lower:
        if area < 80.0:
            return (
                "APROBADO", 
                "TOLERABLE", 
                f"Micro-burbuja dentro de norma óptica ({area:.1f} mm² < 80 mm² límite). Apto para producción directa."
            )
        else:
            return (
                "RECHAZADO", 
                "MODERADA", 
                f"Burbuja oclusiva visible ({area:.1f} mm² >= 80 mm² límite). Concentración de tensiones no admisible."
            )
    else:
        return (
            "APROBADO", 
            "NINGUNA", 
            "Lámina en óptimo estado. Sin defectos críticos detectados."
        )

def optimize_image_memory(image, max_dim=1600):
    """
    Optimización de memoria para fotos tomadas con móviles (12MP a 48MP):
    Reduce proporcionalmente la imagen si excede max_dim píxeles.
    Ahorra hasta un 85% de memoria RAM y acelera el cálculo del filtro Canny.
    """
    h, w = image.shape[:2]
    if max(h, w) > max_dim:
        scale = max_dim / float(max(h, w))
        new_w = int(w * scale)
        new_h = int(h * scale)
        image = cv2.resize(image, (new_w, new_h), interpolation=cv2.INTER_AREA)
    return image

def process_glass_sheet(image_input, sheet_width=2000, sheet_height=2000, orders=None):
    """
    Pipeline unificado de procesamiento para el servidor Flask:
    1. Carga u optimización de imagen en memoria.
    2. Detección de contornos y fallas con filtro Canny.
    3. Clasificación de defecto con Red Neuronal o reglas morfológicas.
    4. Evaluación de Control de Calidad (QC).
    5. Heurística 2D Bin Packing evitando la zona defectuosa.
    6. Generación de métricas de merma y codificación de imagen anotada en Base64.
    """
    if orders is None or len(orders) == 0:
        orders = [
            {'id': 'Pieza-1', 'w': 600, 'h': 500},
            {'id': 'Pieza-2', 'w': 500, 'h': 400},
            {'id': 'Pieza-3', 'w': 700, 'h': 450}
        ]

    # 1. Cargar imagen (desde ruta en disco o desde buffer en memoria)
    if isinstance(image_input, str):
        image = cv2.imread(image_input)
        if image is None:
            raise FileNotFoundError(f"No se pudo cargar la imagen desde la ruta: {image_input}")
    elif isinstance(image_input, (bytes, bytearray)):
        nparr = np.frombuffer(image_input, np.uint8)
        image = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        if image is None:
            raise ValueError("No se pudo decodificar el buffer de imagen enviado.")
    else:
        image = image_input

    # Optimizar resolución para no saturar memoria RAM del servidor
    image = optimize_image_memory(image, max_dim=1600)
    img_h, img_w = image.shape[:2]

    # 2. Detección de fallas con Canny
    detector = DefectDetector(blur_ksize=(5, 5), canny_thresh1=50, canny_thresh2=150)
    
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    blurred = cv2.GaussianBlur(gray, detector.blur_ksize, 0)
    edges = cv2.Canny(blurred, detector.canny_thresh1, detector.canny_thresh2)
    contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    # 3. Análisis de anomalías y Clasificación
    annotated_image = image.copy()
    defect_info = {
        'detected': False,
        'type': 'Ninguno',
        'confidence': 100.0,
        'area': 0.0,
        'perimeter': 0.0,
        'circularity': 0.0,
        'bbox': None,
        'qc_status': 'APROBADO',
        'severity': 'NINGUNA',
        'recommendation': 'Lámina sin imperfecciones detectadas. Apta para corte completo.'
    }

    defect_coords_mm = {'x': 0, 'y': 0, 'w': 0, 'h': 0}

    if contours and len(contours) > 0:
        # Filtrar contornos muy pequeños que sean polvo o ruido menor (< 15 px²)
        valid_contours = [c for c in contours if cv2.contourArea(c) > 15]

        if valid_contours:
            # Tomar el defecto principal (mayor área)
            main_contour = max(valid_contours, key=cv2.contourArea)
            features = FeatureExtractor.extract_features(main_contour)
            area, perimeter, circularity, aspect_ratio, extent = features

            x, y, w, h = cv2.boundingRect(main_contour)
            defect_info['detected'] = True
            defect_info['area'] = float(area)
            defect_info['perimeter'] = float(perimeter)
            defect_info['circularity'] = float(circularity)
            defect_info['bbox'] = {'x': int(x), 'y': int(y), 'w': int(w), 'h': int(h)}

            # Clasificación mediante Red Neuronal o Heurística Morfológica
            nn_model, norm_max = get_neural_network()
            classes = ["Burbuja", "Rayón", "Rotura"]

            if nn_model is not None and norm_max is not None:
                features_norm = features / norm_max
                output = nn_model.forward(np.array([features_norm]))
                class_idx = int(np.argmax(output[0]))
                confidence = float(output[0][class_idx] * 100.0)
                diagnostico = classes[class_idx]
            else:
                # Regla morfológica experta de respaldo si la red no está cargada
                if circularity > 0.65:
                    diagnostico = "Burbuja"
                    confidence = 88.5
                elif aspect_ratio > 3.0 or aspect_ratio < 0.33:
                    diagnostico = "Rayón"
                    confidence = 84.0
                else:
                    diagnostico = "Rotura"
                    confidence = 79.0

            defect_info['type'] = diagnostico
            defect_info['confidence'] = confidence

            # Control de Calidad
            qc_status, severity, recommendation = evaluate_quality_control(
                diagnostico, area, perimeter, circularity
            )
            defect_info['qc_status'] = qc_status
            defect_info['severity'] = severity
            defect_info['recommendation'] = recommendation

            # Dibujar contornos y caja delimitadora sobre la imagen
            cv2.drawContours(annotated_image, [main_contour], -1, (0, 255, 0), 2)
            color_box = (0, 0, 255) if qc_status == "RECHAZADO" else (0, 165, 255)
            cv2.rectangle(annotated_image, (x, y), (x + w, y + h), color_box, 2)
            cv2.putText(
                annotated_image, 
                f"{diagnostico} ({confidence:.0f}%)", 
                (x, max(20, y - 10)), 
                cv2.FONT_HERSHEY_SIMPLEX, 
                0.6, 
                color_box, 
                2
            )

            # Mapear coordenadas de la imagen (píxeles) a coordenadas de la lámina física (milímetros)
            scale_x_mm = float(sheet_width) / float(img_w)
            scale_y_mm = float(sheet_height) / float(img_h)

            defect_coords_mm = {
                'x': int(x * scale_x_mm),
                'y': int(y * scale_y_mm),
                'w': max(80, int(w * scale_x_mm)),  # Margen de seguridad mínimo de 80mm
                'h': max(80, int(h * scale_y_mm))
            }

    # 4. Codificar imagen anotada a Base64 para entrega directa en JSON
    _, buffer = cv2.imencode('.jpg', annotated_image, [int(cv2.IMWRITE_JPEG_QUALITY), 80])
    image_base64 = base64.b64encode(buffer).decode('utf-8')
    image_data_url = f"data:image/jpeg;base64,{image_base64}"

    # 5. Optimización de Corte 2D (Bin Packing FFD con evitación de obstáculos)
    sheet = GlassSheet(width=sheet_width, height=sheet_height, resolution=10)

    if defect_info['detected']:
        sheet.add_defect(
            x=defect_coords_mm['x'],
            y=defect_coords_mm['y'],
            w=defect_coords_mm['w'],
            h=defect_coords_mm['h']
        )

    packer = BinPacker(sheet)
    placed_pieces = packer.pack(orders)

    # 6. Cálculo de Métricas de Aprovechamiento y Merma
    total_area_sheet = float(sheet_width * sheet_height)
    total_area_used = sum(float(p['w'] * p['h']) for p in placed_pieces)
    waste_area = max(0.0, total_area_sheet - total_area_used)
    efficiency_score = (total_area_used / total_area_sheet) * 100.0 if total_area_sheet > 0 else 0.0
    waste_percentage = 100.0 - efficiency_score

    return {
        'success': True,
        'sheet_width': sheet_width,
        'sheet_height': sheet_height,
        'defect_detected': defect_info['detected'],
        'defect_type': defect_info['type'],
        'confidence': defect_info['confidence'],
        'defect_area': defect_info['area'],
        'severity': defect_info['severity'],
        'qc_status': defect_info['qc_status'],
        'recommendation': defect_info['recommendation'],
        'defect_coords': defect_coords_mm,
        'annotated_image_url': image_data_url,
        'placed_pieces': placed_pieces,
        'placed_count': len(placed_pieces),
        'requested_count': len(orders),
        'total_area_used': total_area_used,
        'waste_area': waste_area,
        'efficiency_score': round(efficiency_score, 2),
        'waste_percentage': round(waste_percentage, 2)
    }
