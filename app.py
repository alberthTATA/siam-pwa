# -*- coding: utf-8 -*-
"""
SIAM - Servidor Web Flask & API para Progressive Web App (PWA)
Empresa: Aluminios Cristales Villegas
Proyecto de Tesis: Sistema Inteligente de Aprovechamiento de Material (SIAM)
"""

import os
import json
import time
import logging
from flask import Flask, render_template, request, jsonify, send_from_directory, make_response, session, redirect, url_for
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
    with db_manager._get_connection() as conn:
        c = conn.cursor()
        c.execute("SELECT COUNT(*) FROM glass_batches")
        if c.fetchone()[0] == 0:
            db_manager.insert_batch("Proveedor Demo", 100, "Lote inicial de prueba")
    logger.info("Base de datos SQLite conectada correctamente para trazabilidad.")
except Exception as e:
    logger.warning(f"No se pudo inicializar DatabaseManager: {e}")
    db_manager = None

# ==============================================================================
# RUTAS CRITICAS PARA SOPORTE PWA (Progressive Web App)
# ==============================================================================

@app.route('/manifest.json')
def serve_manifest():
    """Sirve el manifiesto de la aplicación web con el tipo MIME estándar."""
    return send_from_directory('static', 'manifest.json', mimetype='application/manifest+json')

@app.route('/sw.js')
def serve_service_worker():
    """Sirve el Service Worker desde la raíz ('/sw.js') con Service-Worker-Allowed: /."""
    response = make_response(send_from_directory('static', 'sw.js'))
    response.headers['Content-Type'] = 'application/javascript'
    response.headers['Service-Worker-Allowed'] = '/'
    response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    return response

@app.route('/offline')
def offline():
    """Página de contingencia cuando el operario no tiene señal en el taller."""
    return render_template('offline.html')

# ==============================================================================
# VISTA PRINCIPAL Y AUTENTICACIÓN POR ROLES (USUARIO / ADMIN CON CLAVE ESPECIAL)
# ==============================================================================

@app.route('/')
def index():
    """Interfaz principal adaptada para móviles, tablets y estaciones de trabajo."""
    return render_template(
        'index.html',
        logged_user=session.get('username'),
        logged_role=session.get('role'),
        logged_user_id=session.get('user_id')
    )

@app.route('/api/auth/login', methods=['POST'])
def api_login():
    """Autentica al usuario y valida la Clave Especial de Administrador (SIAM2026) si fue solicitada."""
    if not db_manager:
        return jsonify({'success': False, 'message': 'Base de datos no disponible.'}), 500

    data = request.get_json(silent=True) or {}
    identifier = (data.get('identifier') or '').strip()
    password = (data.get('password') or '').strip()
    wants_admin = bool(data.get('wants_admin', False))
    admin_key = (data.get('admin_key') or '').strip()

    if not identifier or not password:
        return jsonify({'success': False, 'message': 'Por favor ingresa tu usuario/correo y contraseña.'}), 400

    if wants_admin or admin_key:
        if not admin_key:
            return jsonify({'success': False, 'message': 'Debes ingresar la Clave Especial de Administrador o desmarcar la casilla.'}), 400
        if admin_key != DatabaseManager.ADMIN_SECRET_KEY:
            return jsonify({'success': False, 'message': 'La Clave Especial de Administrador es incorrecta.'}), 403

    res = db_manager.authenticate_user(identifier, password)
    if res == 'account_locked':
        return jsonify({'success': False, 'message': 'Esta cuenta está bloqueada temporalmente por intentos fallidos.'}), 403
    if not res:
        return jsonify({'success': False, 'message': 'El usuario o la contraseña son incorrectos.'}), 401

    user_id, username, _ = res
    effective_role = 'admin' if (wants_admin or admin_key == DatabaseManager.ADMIN_SECRET_KEY) else 'usuario'

    session['user_id'] = user_id
    session['username'] = username
    session['role'] = effective_role
    db_manager.log_activity(user_id, "Inicio de Sesion Web", f"El usuario {username} ingreso a SIAM Online (Rol: {effective_role.upper()})")

    return jsonify({
        'success': True,
        'user_id': user_id,
        'username': username,
        'role': effective_role
    })

@app.route('/api/auth/register', methods=['POST'])
def api_register():
    """Registra un nuevo usuario en la base de datos desde la interfaz web."""
    if not db_manager:
        return jsonify({'success': False, 'message': 'Base de datos no disponible.'}), 500

    data = request.get_json(silent=True) or {}
    username = (data.get('username') or '').strip()
    email = (data.get('email') or '').strip()
    phone = (data.get('phone') or '').strip()
    password = (data.get('password') or '').strip()
    wants_admin = bool(data.get('wants_admin', False))
    admin_key = (data.get('admin_key') or '').strip()

    if not username or not email or not phone or not password:
        return jsonify({'success': False, 'message': 'Todos los campos son obligatorios.'}), 400
    if len(username) < 3:
        return jsonify({'success': False, 'message': 'El usuario debe tener al menos 3 caracteres.'}), 400
    if '@' not in email:
        return jsonify({'success': False, 'message': 'El correo electrónico debe incluir el signo @.'}), 400
    if not phone.isdigit() or len(phone) < 7:
        return jsonify({'success': False, 'message': 'El teléfono debe contener solo números (mínimo 7 dígitos).'}), 400
    if len(password) < 8:
        return jsonify({'success': False, 'message': 'La contraseña debe tener mínimo 8 caracteres.'}), 400

    existing_err = db_manager.check_user_exists(username, email, phone)
    if existing_err:
        return jsonify({'success': False, 'message': existing_err}), 400

    role = 'usuario'
    if wants_admin:
        if admin_key != DatabaseManager.ADMIN_SECRET_KEY:
            return jsonify({'success': False, 'message': 'Clave secreta de Administrador incorrecta.'}), 403
        role = 'admin'

    if db_manager.register_user(username, email, phone, password, role):
        return jsonify({'success': True, 'message': f'¡Correo verificado y cuenta creada con éxito para {username}! Ya puedes iniciar sesión.'})
    return jsonify({'success': False, 'message': 'No se pudo registrar el usuario.'}), 500

@app.route('/api/auth/forgot-send-code', methods=['POST'])
def api_forgot_send_code():
    """Genera un código de verificación de 6 dígitos para recuperar contraseña."""
    if not db_manager:
        return jsonify({'success': False, 'message': 'Base de datos no disponible.'}), 500

    data = request.get_json(silent=True) or {}
    identifier = (data.get('identifier') or '').strip()
    if not identifier:
        return jsonify({'success': False, 'message': 'Ingresa tu usuario o correo electrónico registrado.'}), 400

    user = db_manager.get_user_for_recovery(identifier)
    if not user:
        return jsonify({'success': False, 'message': 'No existe ninguna cuenta registrada con ese usuario o correo.'}), 404

    user_id, username, email = user
    code = db_manager.create_password_reset_code(user_id)
    return jsonify({
        'success': True,
        'user_id': user_id,
        'username': username,
        'email': email,
        'code': code
    })

@app.route('/api/auth/forgot-reset', methods=['POST'])
def api_forgot_reset():
    """Verifica el código de 6 dígitos y actualiza la contraseña del usuario."""
    if not db_manager:
        return jsonify({'success': False, 'message': 'Base de datos no disponible.'}), 500

    data = request.get_json(silent=True) or {}
    user_id = data.get('user_id')
    code = (data.get('code') or '').strip()
    new_password = (data.get('new_password') or '').strip()

    if not user_id or not code or not new_password:
        return jsonify({'success': False, 'message': 'Completa el código de 6 dígitos y la nueva contraseña.'}), 400
    if len(new_password) < 8:
        return jsonify({'success': False, 'message': 'La nueva contraseña debe tener mínimo 8 caracteres.'}), 400

    ok, msg = db_manager.verify_and_reset_password(int(user_id), code, new_password)
    if not ok:
        return jsonify({'success': False, 'message': msg}), 400
    return jsonify({'success': True, 'message': msg})

@app.route('/api/auth/logout', methods=['POST'])
def api_logout():
    session.clear()
    return jsonify({'success': True})

# ==============================================================================
# ENDPOINTS DE TRAZABILIDAD, DASHBOARD Y PANEL ADMINISTRADOR (PARIDAD CON LOCAL)
# ==============================================================================

@app.route('/api/traceability-data', methods=['GET'])
def get_traceability_data():
    """Retorna inspecciones de calidad, estadísticas del dashboard y datos de administrador."""
    if not db_manager:
        return jsonify({'success': False, 'message': 'Base de datos no disponible.'}), 500

    inspections_raw = db_manager.get_quality_inspections()
    inspections = [
        {
            'id': r[0],
            'batch_id': r[1],
            'defect_type': r[2],
            'x': round(float(r[3] or 0), 1),
            'y': round(float(r[4] or 0), 1),
            'area': round(float(r[5] or 0), 2),
            'qc_status': r[6] or 'PENDIENTE',
            'severity': r[7] or 'LEVE'
        }
        for r in inspections_raw
    ]

    stats = db_manager.get_defect_statistics()
    gen = stats.get('general_stats') or (0, 0, 0, 0, 0)

    response_payload = {
        'success': True,
        'inspections': inspections,
        'summary': {
            'total_defects': gen[0] or 0,
            'avg_area': round(float(gen[1] or 0), 2),
            'max_area': round(float(gen[2] or 0), 2),
            'defect_by_type': [{'type': d[0], 'count': d[1], 'avg_area': round(float(d[2] or 0), 1)} for d in (stats.get('defect_stats') or [])],
            'severity_breakdown': [{'severity': s[0], 'count': s[1]} for s in (stats.get('severity_stats') or [])],
            'qc_breakdown': [{'status': q[0], 'count': q[1]} for q in (stats.get('qc_stats') or [])]
        }
    }

    # Si el usuario tiene sesión de Administrador, incluir tablas del Panel Administrador
    if session.get('role') == 'admin':
        users = [
            {'id': u[0], 'username': u[1], 'email': u[2], 'phone': u[3], 'role': u[4].upper()}
            for u in db_manager.get_all_users()
        ]
        activity = [
            {'id': a[0], 'username': a[1], 'action': a[2], 'details': a[3] or '', 'timestamp': a[4], 'role': (a[5] if len(a) > 5 else 'usuario').upper()}
            for a in db_manager.get_user_activity()[:50]
        ]
        metrics = [
            {'username': m[0], 'role': m[1].upper(), 'action': m[2], 'total': m[3]}
            for m in db_manager.get_user_metrics()
        ]
        response_payload['admin_data'] = {
            'users': users,
            'activity': activity,
            'metrics': metrics
        }

    return jsonify(response_payload)

# ==============================================================================
# ENDPOINT DE PROCESAMIENTO MÓVIL (OpenCV + Red Neuronal + Bin Packing)
# ==============================================================================

@app.route('/api/scan-and-optimize', methods=['POST'])
def scan_and_optimize():
    """
    Endpoint principal que recibe la foto tomada desde el celular o estación de trabajo.
    """
    try:
        t0 = time.perf_counter()
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

        image_bytes = file.read()
        if len(image_bytes) == 0:
            return jsonify({
                'success': False, 
                'message': 'El archivo de imagen enviado está vacío.'
            }), 400

        try:
            sheet_width = int(request.form.get('sheet_width', 2000))
            sheet_height = int(request.form.get('sheet_height', 2000))
        except ValueError:
            sheet_width, sheet_height = 2000, 2000

        orders_raw = request.form.get('orders')
        orders = []
        if orders_raw:
            try:
                orders = json.loads(orders_raw)
            except Exception as e:
                logger.warning(f"Error decodificando lista de pedidos JSON: {e}")

        if not orders:
            orders = [
                {'id': 'Corte-A1', 'w': 600, 'h': 500},
                {'id': 'Corte-A2', 'w': 500, 'h': 400},
                {'id': 'Corte-B1', 'w': 700, 'h': 450}
            ]

        # Ejecutar Pipeline en vision.py (incluye validación óptica de lámina de vidrio)
        result = process_glass_sheet(
            image_input=image_bytes,
            sheet_width=sheet_width,
            sheet_height=sheet_height,
            orders=orders
        )

        if not result.get('success'):
            if db_manager and session.get('user_id'):
                db_manager.log_activity(session['user_id'], "Captura Rechazada Web", "Objeto no válido (no es lámina de vidrio)")
            return jsonify(result), 422

        elapsed_sec = round(time.perf_counter() - t0, 3)
        result['processing_time_sec'] = elapsed_sec

        # Registro de Trazabilidad en Base de Datos (Inspección, Pedidos y Plan de Corte)
        if db_manager:
            try:
                for ord_item in orders:
                    db_manager.insert_cutting_order(ord_item.get('id', 'Pieza'), ord_item.get('w', 500), ord_item.get('h', 400), 'PROCESADO')
                if result.get('defect_detected'):
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
                db_manager.insert_cutting_plan(
                    batch_id=1,
                    total_area_used=float(result.get('total_area_used', 0)),
                    waste_area=float(result.get('waste_area', 0)),
                    efficiency_score=float(result.get('efficiency_score', 0))
                )
                if session.get('user_id'):
                    db_manager.log_activity(
                        session['user_id'],
                        "Optimizacion Web",
                        f"QC: {result.get('qc_status')} | Eficiencia: {result.get('efficiency_score')}% | Tiempo: {elapsed_sec}s"
                    )
            except Exception as dberr:
                logger.warning(f"No se pudo guardar trazabilidad en BD: {dberr}")

        return jsonify(result), 200

    except Exception as err:
        logger.exception(f"Error interno durante el procesamiento de la lámina: {err}")
        return jsonify({
            'success': False,
            'message': f'Error en el motor de procesamiento: {str(err)}'
        }), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    logger.info(f"Iniciando SIAM PWA en http://0.0.0.0:{port}")
    app.run(host='0.0.0.0', port=port, debug=True)
