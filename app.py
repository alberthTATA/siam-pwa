# -*- coding: utf-8 -*-
"""
SIAM - Servidor Web Flask & API para Progressive Web App (PWA)
Empresa: Aluminios Cristales Villegas
Proyecto de Tesis: Sistema Inteligente de Aprovechamiento de Material (SIAM)
"""

import os
import json
import logging
from flask import Flask, render_template, request, jsonify, send_from_directory, make_response
from werkzeug.utils import secure_filename

from vision import process_glass_sheet
from src.database.db_manager import DatabaseManager

# Configuración de Logging
logging.basicConfig(level=logging.INFO, format='[%(asctime)s] %(levelname)s in %(module)s: %(message)s')
logger = logging.getLogger('SIAM_FLASK')

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'siam_secret_villegas_2026')
# Permitir fotos de cámaras móviles de hasta 32 MB sin ser rechazadas por Flask
app.config['MAX_CONTENT_LENGTH'] = 32 * 1024 * 1024

# Extensiones de imagen permitidas
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'webp', 'bmp'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# Instancia de Base de Datos para Trazabilidad
try:
    db_manager = DatabaseManager()
    logger.info("Base de datos SQLite conectada correctamente para trazabilidad.")
except Exception as e:
    logger.warning(f"No se pudo inicializar DatabaseManager: {e}")
    db_manager = None

# ==============================================================================
# RUTAS CRITICAS PARA SOPORTE PWA (Progressive Web App)
# ==============================================================================

@app.route('/manifest.json')
def serve_manifest():
    """
    Sirve el manifiesto de la aplicación web con el tipo MIME estándar.
    Permite a Android / iOS identificar a SIAM como una App instalable.
    """
    return send_from_directory('static', 'manifest.json', mimetype='application/manifest+json')

@app.route('/sw.js')
def serve_service_worker():
    """
    Sirve el Service Worker desde la raíz ('/sw.js') con la cabecera
    'Service-Worker-Allowed: /' para que tenga control sobre todo el dominio,
    cumpliendo estrictamente con la especificación oficial de PWA.
    """
    response = make_response(send_from_directory('static', 'sw.js'))
    response.headers['Content-Type'] = 'application/javascript'
    response.headers['Service-Worker-Allowed'] = '/'
    # Evitar que los navegadores guarden en cache fija el Service Worker para permitir actualizaciones
    response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    return response

@app.route('/offline')
def offline():
    """Página de contingencia cuando el operario no tiene señal en el taller."""
    return render_template('offline.html')

# ==============================================================================
# VISTA PRINCIPAL
# ==============================================================================

@app.route('/')
def index():
    """Interfaz principal adaptada para móviles, tablets y estaciones de trabajo."""
    return render_template('index.html')

# ==============================================================================
# ENDPOINT DE PROCESAMIENTO MÓVIL (OpenCV + Red Neuronal + Bin Packing)
# ==============================================================================

@app.route('/api/scan-and-optimize', methods=['POST'])
def scan_and_optimize():
    """
    Endpoint principal que recibe la foto tomada desde el celular del operario.
    Flujo:
    1. Recibe 'image' vía multipart/form-data.
    2. Procesa directamente en memoria (sin saturar disco ni memoria RAM).
    3. Ejecuta Canny (detección de defectos), RNA (clasificación) y Control de Calidad.
    4. Ejecuta Heurística 2D FFD (esquiva el defecto y genera el plano de corte).
    5. Guarda el registro de trazabilidad en SQLite si está disponible.
    6. Retorna respuesta JSON estructurada al cliente móvil.
    """
    try:
        # 1. Validar presencia del archivo de imagen
        if 'image' not in request.files:
            return jsonify({
                'success': False, 
                'message': 'No se encontró el archivo de imagen en la petición.'
            }), 400

        file = request.files['image']

        if file.filename == '':
            return jsonify({
                'success': False, 
                'message': 'No se seleccionó ningún archivo de imagen.'
            }), 400

        if not allowed_file(file.filename):
            return jsonify({
                'success': False, 
                'message': 'Formato no soportado. Use imágenes JPG, PNG o WEBP.'
            }), 400

        # 2. Leer buffer en memoria (Evita crear archivos huérfanos en disco)
        image_bytes = file.read()
        if len(image_bytes) == 0:
            return jsonify({
                'success': False, 
                'message': 'El archivo de imagen enviado está vacío.'
            }), 400

        # 3. Extraer dimensiones de la lámina madre
        try:
            sheet_width = int(request.form.get('sheet_width', 2000))
            sheet_height = int(request.form.get('sheet_height', 2000))
        except ValueError:
            sheet_width, sheet_height = 2000, 2000

        # 4. Extraer pedidos de corte configurados por el usuario
        orders_raw = request.form.get('orders')
        orders = []
        if orders_raw:
            try:
                orders = json.loads(orders_raw)
            except Exception as e:
                logger.warning(f"Error decodificando lista de pedidos JSON: {e}")

        if not orders:
            # Pedidos predeterminados de prueba si no se pasaron
            orders = [
                {'id': 'Corte-A1', 'w': 600, 'h': 500},
                {'id': 'Corte-A2', 'w': 500, 'h': 400},
                {'id': 'Corte-B1', 'w': 700, 'h': 450}
            ]

        # 5. Ejecutar Pipeline en vision.py
        result = process_glass_sheet(
            image_input=image_bytes,
            sheet_width=sheet_width,
            sheet_height=sheet_height,
            orders=orders
        )

        # 6. Registro de Trazabilidad en Base de Datos (Fase de Tesis)
        if db_manager and result.get('defect_detected'):
            try:
                def_coords = result.get('defect_coords', {})
                db_manager.insert_defect(
                    batch_id=1,
                    defect_type=result.get('defect_type', 'Desconocido'),
                    x_coord=float(def_coords.get('x', 0)),
                    y_coord=float(def_coords.get('y', 0)),
                    defect_area=float(result.get('defect_area', 0)),
                    qc_status=result.get('qc_status', 'PENDIENTE'),
                    severity=result.get('severity', 'LEVE')
                )
                logger.info(f"Defecto registrado en trazabilidad: {result.get('defect_type')} - QC: {result.get('qc_status')}")
            except Exception as dberr:
                logger.warning(f"No se pudo guardar inspección en BD: {dberr}")

        return jsonify(result), 200

    except Exception as err:
        logger.exception(f"Error interno durante el procesamiento de la lámina: {err}")
        return jsonify({
            'success': False,
            'message': f'Error en el motor de procesamiento: {str(err)}'
        }), 500

# ==============================================================================
# INICIO DEL SERVIDOR
# ==============================================================================

if __name__ == '__main__':
    # host='0.0.0.0' permite que otros dispositivos en la misma red Wi-Fi (celulares de planta) se conecten
    port = int(os.environ.get('PORT', 5000))
    logger.info(f"Iniciando SIAM PWA en http://0.0.0.0:{port}")
    app.run(host='0.0.0.0', port=port, debug=True)
