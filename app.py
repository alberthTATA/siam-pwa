# -*- coding: utf-8 -*-
"""
SIAM - Servidor Web Flask & API para Progressive Web App (PWA)
Empresa: Aluminios Cristales Villegas
Proyecto de Tesis: Sistema Inteligente de Aprovechamiento de Material (SIAM)
"""

import os
import sys
import shutil
import json
import time
import logging

_BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if _BASE_DIR not in sys.path:
    sys.path.insert(0, _BASE_DIR)

from flask import Flask, render_template, request, jsonify, send_from_directory, make_response, session
from vision import process_glass_sheet
from src.database.db_manager import DatabaseManager
from src.optimization.bin_packing import GlassSheet

# Configuración de Logging
logging.basicConfig(level=logging.INFO, format='[%(asctime)s] %(levelname)s in %(module)s: %(message)s')
logger = logging.getLogger('SIAM_FLASK')

# Auto-sincronización: si el usuario sube index.html, base.html, app.js o sw.js a la raíz de GitHub,
# copiarlos automáticamente a sus subcarpetas correspondientes (templates/ y static/) al arrancar.
for _src_name, _dst_rel in [
    ('index.html', os.path.join('templates', 'index.html')),
    ('base.html', os.path.join('templates', 'base.html')),
    ('app.js', os.path.join('static', 'js', 'app.js')),
    ('sw.js', os.path.join('static', 'sw.js')),
]:
    _src_p = os.path.join(_BASE_DIR, _src_name)
    _dst_p = os.path.join(_BASE_DIR, _dst_rel)
    if os.path.exists(_src_p):
        try:
            os.makedirs(os.path.dirname(_dst_p), exist_ok=True)
            shutil.copyfile(_src_p, _dst_p)
            logger.info(f"Archivo sincronizado automáticamente desde raíz: {_src_name} -> {_dst_rel}")
        except Exception as _e:
            logger.warning(f"No se pudo sincronizar {_src_name}: {_e}")

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'siam_secret_villegas_2026')
app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 0
# Permitir fotos de cámaras móviles de hasta 32 MB sin ser rechazadas por Flask
app.config['MAX_CONTENT_LENGTH'] = 32 * 1024 * 1024

@app.after_request
def add_no_cache_headers(response):
    """Evita que el navegador o el Service Worker guarden versiones antiguas del HTML/JS."""
    response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    return response

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
        row_count = c.fetchone()
        if not row_count or row_count[0] == 0:
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
    html = render_template(
        'index.html',
        logged_user=session.get('username'),
        logged_role=session.get('role'),
        logged_user_id=session.get('user_id')
    )
    # Garantizar etiquetas visibles, placeholders claros y botones de ojito (👁️)
    # incluso si en GitHub no se reemplazó el archivo dentro de la subcarpeta templates/
    enhancer_patch = """
    <style>
        #authOverlay input.form-control {
            background-color: #161D2A !important;
            color: #FFFFFF !important;
            border: 1px solid #334155 !important;
        }
        #authOverlay input.form-control::placeholder {
            color: #94A3B8 !important;
            opacity: 1 !important;
        }
        .siam-auto-label {
            display: block;
            font-size: 12.5px;
            font-weight: 700;
            color: #38BDF8;
            margin-bottom: 3px;
            text-align: left;
        }
        .btn-eye-siam {
            background-color: #1E293B !important;
            border: 1px solid #334155 !important;
            color: #38BDF8 !important;
            font-size: 12px !important;
            font-weight: 700 !important;
            padding: 0 12px !important;
            cursor: pointer;
        }
        .btn-eye-siam:hover {
            background-color: #0284C7 !important;
            color: #FFFFFF !important;
        }
    </style>
    <script>
        window.togglePasswordVisibility = function(inputId, btn) {
            var input = document.getElementById(inputId);
            if (!input) return;
            if (input.type === 'password') {
                input.type = 'text';
                if (btn) btn.textContent = 'Ocultar';
            } else {
                input.type = 'password';
                if (btn) btn.textContent = 'Ver';
            }
        };
        document.addEventListener('DOMContentLoaded', function() {
            // Limpiar caches antiguas del Service Worker v1.0.0
            if ('caches' in window) {
                caches.keys().then(function(names) {
                    names.forEach(function(n) {
                        if (n.indexOf('v1.0.0') !== -1) caches.delete(n);
                    });
                });
            }
            // Asegurar etiquetas visibles encima de cada campo de Registro y Login (Sin Emojis - Punto 4)
            var fieldLabels = [
                { id: 'regUsername', label: 'Nombre de Usuario:', placeholder: 'Ej: juanperez (min. 3 caracteres)' },
                { id: 'regEmail', label: 'Correo Electronico:', placeholder: 'Ej: correo@gmail.com (con @ y dominio valido)' },
                { id: 'regPhone', label: 'Numero de Telefono:', placeholder: 'Ej: 04121234567 (solo numeros)' },
                { id: 'regPassword', label: 'Contrasena Segura:', placeholder: 'Min. 8 caract., Mayus, Num y Simbolo' },
                { id: 'regAdminKey', label: 'Clave Secreta de Administrador:', placeholder: 'Ingresa la clave especial SIAM2026' },
                { id: 'loginAdminKey', label: 'Clave Especial de Administrador:', placeholder: 'Ingresa la clave especial SIAM2026' }
            ];
            fieldLabels.forEach(function(item) {
                var el = document.getElementById(item.id);
                if (!el) return;
                if (item.placeholder) el.setAttribute('placeholder', item.placeholder);
                var container = el.closest('.mb-2, .mb-3, #loginAdminKeyWrapper, #regAdminKeyWrapper') || el.parentElement;
                if (container && !container.querySelector('label')) {
                    var lbl = document.createElement('label');
                    lbl.className = 'siam-auto-label';
                    lbl.setAttribute('for', item.id);
                    lbl.textContent = item.label;
                    container.insertBefore(lbl, container.firstChild);
                }
            });
            // Asegurar botón Ver/Ocultar (sin emojis) en todos los campos de contraseña y clave especial
            ['loginPassword', 'loginAdminKey', 'regPassword', 'regAdminKey'].forEach(function(pwdId) {
                var pwdEl = document.getElementById(pwdId);
                if (!pwdEl) return;
                if (pwdEl.parentElement && pwdEl.parentElement.classList.contains('input-group')) return;
                var wrapper = document.createElement('div');
                wrapper.className = 'input-group';
                pwdEl.parentNode.insertBefore(wrapper, pwdEl);
                wrapper.appendChild(pwdEl);
                var btn = document.createElement('button');
                btn.type = 'button';
                btn.className = 'btn btn-eye-siam';
                btn.title = 'Mostrar / Ocultar clave';
                btn.textContent = 'Ver';
                btn.onclick = function() { window.togglePasswordVisibility(pwdId, btn); };
                wrapper.appendChild(btn);
            });
            // Garantizar que el botón Completar Registro guarde directamente en la BD en 1 clic sin pedir correo de verificación
            var oldRegBtn = document.getElementById('btnDoRegister');
            if (oldRegBtn) {
                var newRegBtn = oldRegBtn.cloneNode(true);
                oldRegBtn.parentNode.replaceChild(newRegBtn, oldRegBtn);
                newRegBtn.addEventListener('click', async function() {
                    var username = (document.getElementById('regUsername')?.value || '').trim();
                    var email = (document.getElementById('regEmail')?.value || '').trim();
                    var phone = (document.getElementById('regPhone')?.value || '').trim();
                    var password = (document.getElementById('regPassword')?.value || '').trim();
                    var wants_admin = document.getElementById('regAdminCheck')?.checked || false;
                    var admin_key = (document.getElementById('regAdminKey')?.value || '').trim();
                    var authAlert = document.getElementById('authAlert');
                    function showMsg(msg, ok) {
                        if (!authAlert) return;
                        authAlert.textContent = msg;
                        authAlert.className = 'alert py-2 small ' + (ok ? 'alert-success' : 'alert-danger');
                    }
                    try {
                        var res = await fetch('/api/auth/register', {
                            method: 'POST',
                            headers: { 'Content-Type': 'application/json' },
                            body: JSON.stringify({ username: username, email: email, phone: phone, password: password, wants_admin: wants_admin, admin_key: admin_key })
                        });
                        var data = await res.json();
                        if (!res.ok || !data.success) {
                            showMsg(data.message || 'Error al registrar.', false);
                            return;
                        }
                        showMsg(data.message || '¡Cuenta creada con éxito! Ya puedes iniciar sesión.', true);
                        document.getElementById('registerBox')?.classList.add('d-none');
                        document.getElementById('loginBox')?.classList.remove('d-none');
                    } catch (e) {
                        showMsg('Error de conexión al registrar usuario.', false);
                    }
                });
            }
        });
    </script>
    """
    if "</body>" in html:
        html = html.replace("</body>", enhancer_patch + "\n</body>")
    else:
        html += enhancer_patch
    resp = make_response(html)
    resp.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
    return resp

@app.route('/api/auth/login', methods=['POST'])
def api_login():
    """
    Autentica al usuario en SIAM Online.
    - Punto 7: Si es el Superusuario Programador ('programador' / rol 'superadmin'), habilita el Módulo de Mantenimiento.
    - Punto 9: Si el usuario se registró sin la clave de admin SIAM2026 (su rol en BD es 'usuario') e intenta abrir
      el login administrativo, se le deniega el acceso con un mensaje indicando que no está registrado como Administrador
      sino como Usuario Normal.
    """
    if not db_manager:
        return jsonify({'success': False, 'message': 'Base de datos no disponible.'}), 500

    data = request.get_json(silent=True) or {}
    identifier = (data.get('identifier') or '').strip()
    password = (data.get('password') or '').strip()
    wants_admin = bool(data.get('wants_admin', False))
    admin_key = (data.get('admin_key') or '').strip()

    if not identifier or not password:
        return jsonify({'success': False, 'message': 'Por favor ingresa tu usuario/correo y contrasena.'}), 400

    res = db_manager.authenticate_user(identifier, password)
    if res == 'account_locked':
        return jsonify({'success': False, 'message': 'Esta cuenta esta bloqueada temporalmente por intentos fallidos.'}), 403
    if not res or not isinstance(res, tuple):
        return jsonify({'success': False, 'message': 'El usuario o la contrasena son incorrectos.'}), 401

    user_id, username, db_role = res
    db_role_clean = str(db_role or 'usuario').lower()

    # Punto 7: Superusuario exclusivo para el Programador
    if db_role_clean == 'superadmin' or str(username).lower() == DatabaseManager.SUPERUSER_USERNAME.lower():
        effective_role = 'superadmin'
    elif wants_admin or bool(admin_key):
        # Punto 9 (Exclusivo Versión Online): Verificar primero en la BD si el usuario realmente se registró como Administrador
        if db_role_clean != 'admin':
            return jsonify({
                'success': False,
                'message': 'No esta registrado como Administrador sino como Usuario Normal. Desmarque la casilla de Clave Especial para iniciar sesion.'
            }), 403
        if not admin_key:
            return jsonify({'success': False, 'message': 'Debes ingresar la Clave Especial de Administrador (SIAM2026) o desmarcar la casilla.'}), 400
        if admin_key != DatabaseManager.ADMIN_SECRET_KEY:
            return jsonify({'success': False, 'message': 'La Clave Especial de Administrador es incorrecta.'}), 403
        effective_role = 'admin'
    else:
        effective_role = 'usuario'

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
    """Registra un nuevo usuario en la base de datos desde la interfaz web con validación estricta de correo (Punto 6)."""
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

    # Punto 6: Validación estricta del correo electrónico
    valid_mail, mail_err = DatabaseManager.validate_strict_email(email)
    if not valid_mail:
        return jsonify({'success': False, 'message': mail_err}), 400

    if not phone.isdigit() or len(phone) < 7:
        return jsonify({'success': False, 'message': 'El telefono debe contener solo numeros (minimo 7 digitos).'}), 400
    if len(password) < 8:
        return jsonify({'success': False, 'message': 'La contrasena debe tener minimo 8 caracteres.'}), 400

    existing_err = db_manager.check_user_exists(username, email, phone)
    if existing_err:
        return jsonify({'success': False, 'message': existing_err}), 400

    role = 'usuario'
    if wants_admin:
        if admin_key != DatabaseManager.ADMIN_SECRET_KEY:
            return jsonify({'success': False, 'message': 'Clave secreta de Administrador incorrecta.'}), 403
        role = 'admin'

    if db_manager.register_user(username, email, phone, password, role):
        tipo_txt = 'Administrador' if role == 'admin' else 'Usuario Normal'
        return jsonify({'success': True, 'message': f'Cuenta de {tipo_txt} creada con exito para {username}. Ya puedes iniciar sesion.'})
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

    ok, msg = db_manager.complete_password_reset(int(str(user_id)), code, new_password)
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

    # Si el usuario tiene sesión de Administrador o Superusuario, incluir tablas del Panel Administrador
    if session.get('role') in ('admin', 'superadmin'):
        users = [
            {'id': u[0], 'username': u[1], 'email': u[2], 'phone': u[3], 'role': str(u[4]).upper()}
            for u in db_manager.get_all_users()
        ]
        activity = [
            {'id': a[0], 'username': a[1], 'action': a[2], 'details': a[3] or '', 'timestamp': a[4], 'role': (a[5] if len(a) > 5 else 'usuario').upper()}
            for a in db_manager.get_user_activity()[:50]
        ]
        metrics = [
            {'username': m[0], 'role': str(m[1]).upper(), 'action': m[2], 'total': m[3]}
            for m in db_manager.get_user_metrics()
        ]
        response_payload['admin_data'] = {
            'users': users,
            'activity': activity,
            'metrics': metrics
        }

    # Si es el Superusuario Programador, incluir información técnica del Módulo de Mantenimiento (Punto 7)
    if session.get('role') == 'superadmin':
        response_payload['maintenance_data'] = db_manager.run_maintenance_diagnostics()

    return jsonify(response_payload)

# ==============================================================================
# ENDPOINTS DE GESTIÓN DE USUARIOS DEL PANEL ADMINISTRATIVO (4 BOTONES - PUNTO 3)
# ==============================================================================

@app.route('/api/admin/users/add', methods=['POST'])
def api_admin_add_user():
    """1. Agregar Usuario desde el Panel Administrativo Online."""
    if not db_manager:
        return jsonify({'success': False, 'message': 'Base de datos no disponible.'}), 500
    if session.get('role') not in ('admin', 'superadmin'):
        return jsonify({'success': False, 'message': 'Acceso denegado. Se requiere rol Administrador.'}), 403

    data = request.get_json(silent=True) or {}
    username = (data.get('username') or '').strip()
    email = (data.get('email') or '').strip()
    phone = (data.get('phone') or '').strip()
    password = (data.get('password') or '').strip()
    role = (data.get('role') or 'usuario').strip().lower()

    ok, msg = db_manager.admin_add_user(username, email, phone, password, role)
    if ok and session.get('user_id'):
        db_manager.log_activity(session['user_id'], "Admin Agregar Usuario Web", f"Agrego a {username} ({role})")
    return jsonify({'success': ok, 'message': msg}), (200 if ok else 400)

@app.route('/api/admin/users/update', methods=['POST'])
def api_admin_update_user():
    """2. Modificar Usuario desde el Panel Administrativo Online."""
    if not db_manager:
        return jsonify({'success': False, 'message': 'Base de datos no disponible.'}), 500
    if session.get('role') not in ('admin', 'superadmin'):
        return jsonify({'success': False, 'message': 'Acceso denegado. Se requiere rol Administrador.'}), 403

    data = request.get_json(silent=True) or {}
    user_id = data.get('user_id')
    if not user_id:
        return jsonify({'success': False, 'message': 'Debe indicar el ID del usuario a modificar.'}), 400
    username = (data.get('username') or '').strip()
    email = (data.get('email') or '').strip()
    phone = (data.get('phone') or '').strip()
    role = (data.get('role') or 'usuario').strip().lower()
    new_password = (data.get('new_password') or '').strip()

    ok, msg = db_manager.admin_update_user(int(str(user_id)), username, email, phone, role, new_password)
    if ok and session.get('user_id'):
        db_manager.log_activity(session['user_id'], "Admin Modificar Usuario Web", f"Modifico ID #{user_id} ({username})")
    return jsonify({'success': ok, 'message': msg}), (200 if ok else 400)

@app.route('/api/admin/users/delete', methods=['POST'])
def api_admin_delete_user():
    """3. Eliminar Usuario desde el Panel Administrativo Online."""
    if not db_manager:
        return jsonify({'success': False, 'message': 'Base de datos no disponible.'}), 500
    if session.get('role') not in ('admin', 'superadmin'):
        return jsonify({'success': False, 'message': 'Acceso denegado. Se requiere rol Administrador.'}), 403

    data = request.get_json(silent=True) or {}
    user_id = data.get('user_id')
    if not user_id:
        return jsonify({'success': False, 'message': 'Debe indicar el ID del usuario a eliminar.'}), 400
    target_uid = int(str(user_id))
    if target_uid == int(session.get('user_id') or 0):
        return jsonify({'success': False, 'message': 'No puede eliminar su propia cuenta con la sesion activa.'}), 400

    ok, msg = db_manager.admin_delete_user(target_uid)
    if ok and session.get('user_id'):
        db_manager.log_activity(session['user_id'], "Admin Eliminar Usuario Web", f"Elimino ID #{user_id}")
    return jsonify({'success': ok, 'message': msg}), (200 if ok else 400)

@app.route('/api/admin/users/search', methods=['GET'])
def api_admin_search_users():
    """4. Consultar Usuario desde el Panel Administrativo Online."""
    if not db_manager:
        return jsonify({'success': False, 'message': 'Base de datos no disponible.'}), 500
    if session.get('role') not in ('admin', 'superadmin'):
        return jsonify({'success': False, 'message': 'Acceso denegado. Se requiere rol Administrador.'}), 403

    q = (request.args.get('q') or '').strip()
    rows = db_manager.admin_search_users(q)
    users = [
        {'id': u[0], 'username': u[1], 'email': u[2], 'phone': u[3], 'role': str(u[4]).upper()}
        for u in rows
    ]
    if session.get('user_id'):
        db_manager.log_activity(session['user_id'], "Admin Consultar Usuario Web", f"Busqueda: '{q or 'TODOS'}' ({len(users)} resultados)")
    return jsonify({'success': True, 'users': users, 'count': len(users)})

# ==============================================================================
# ENDPOINTS EXCLUSIVOS DE MANTENIMIENTO (SUPERUSUARIO PROGRAMADOR - PUNTO 7)
# ==============================================================================

@app.route('/api/maintenance/action', methods=['POST'])
def api_maintenance_action():
    """Ejecuta acciones técnicas del Módulo de Mantenimiento exclusivo para el Programador."""
    if not db_manager:
        return jsonify({'success': False, 'message': 'Base de datos no disponible.'}), 500
    if session.get('role') != 'superadmin':
        return jsonify({'success': False, 'message': 'Acceso exclusivo para el Superusuario del Programador.'}), 403

    data = request.get_json(silent=True) or {}
    action = (data.get('action') or 'diagnostics').strip()

    if action == 'backup':
        ok, path = db_manager.backup_database()
        if session.get('user_id'):
            db_manager.log_activity(session['user_id'], "Mantenimiento Backup Web", os.path.basename(path))
        return jsonify({'success': ok, 'message': f'Copia de seguridad creada en: {path}', 'diagnostics': db_manager.run_maintenance_diagnostics()})
    elif action == 'unlock_accounts':
        ok, msg = db_manager.unlock_all_accounts()
        if session.get('user_id'):
            db_manager.log_activity(session['user_id'], "Mantenimiento Desbloqueo Web", msg)
        return jsonify({'success': ok, 'message': msg, 'diagnostics': db_manager.run_maintenance_diagnostics()})
    elif action == 'clean_logs':
        ok, msg = db_manager.clear_old_activity_logs()
        if session.get('user_id'):
            db_manager.log_activity(session['user_id'], "Mantenimiento Auditoria Web", msg)
        return jsonify({'success': ok, 'message': msg, 'diagnostics': db_manager.run_maintenance_diagnostics()})
    elif action == 'verify_engine':
        ok_mod, mod_msg, _ = GlassSheet.validate_sheet_dimensions(20, 20)
        return jsonify({
            'success': ok_mod,
            'message': f'Verificacion Tecnica del Motor de Corte y Red Neuronal: {mod_msg} | Arquitectura IA Dense 5->16->16->3 Operativa.',
            'diagnostics': db_manager.run_maintenance_diagnostics()
        })
    else:
        diag = db_manager.run_maintenance_diagnostics()
        return jsonify({
            'success': True,
            'message': f"Diagnostico SQLite: {diag.get('integrity')} | Tamano BD: {diag.get('db_size_kb')} KB | Motor de Corte Activo.",
            'diagnostics': diag
        })

@app.route('/api/validate-sheet', methods=['POST'])
def api_validate_sheet():
    """Valida el tamaño de la Lámina Madre."""
    data = request.get_json(silent=True) or {}
    w = data.get('sheet_width')
    h = data.get('sheet_height')
    ok, msg, unit_lbl = GlassSheet.validate_sheet_dimensions(w, h)
    if not ok:
        return jsonify({'success': False, 'message': msg}), 400
    w_int, h_int = int(str(w or 0)), int(str(h or 0))
    if (w_int <= 20 and h_int >= 100) or (h_int <= 20 and w_int >= 100):
        return jsonify({
            'success': False,
            'message': 'El ancho y el alto de la lamina deben estar en la misma escala de medida.'
        }), 400
    return jsonify({'success': True, 'message': msg, 'sheet_width': w_int, 'sheet_height': h_int, 'unit': unit_lbl})

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
        filename = file.filename or ''
        if filename == '':
            return jsonify({
                'success': False, 
                'message': 'No se seleccionó ningún archivo de imagen.'
            }), 400

        if not allowed_file(filename):
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
            return jsonify({
                'success': False,
                'message': 'Error: Las dimensiones de la Lamina Madre deben ser valores numericos validos.'
            }), 400

        # Validar tamaño de la Lámina Madre
        valid_mod, mod_msg, unit_lbl = GlassSheet.validate_sheet_dimensions(sheet_width, sheet_height)
        if not valid_mod:
            return jsonify({'success': False, 'message': mod_msg}), 400

        orders_raw = request.form.get('orders')
        orders = []
        if orders_raw:
            try:
                orders = json.loads(orders_raw)
            except Exception as e:
                logger.warning(f"Error decodificando lista de pedidos JSON: {e}")

        if not orders:
            p1_w = max(1, int(sheet_width * 0.3))
            p1_h = max(1, int(sheet_height * 0.25))
            orders = [
                {'id': 'Corte-A1', 'w': p1_w, 'h': p1_h},
                {'id': 'Corte-A2', 'w': max(1, int(sheet_width * 0.25)), 'h': max(1, int(sheet_height * 0.2))},
            ]

        # Validar que ningún pedido de corte supere las dimensiones de la Lámina Madre configurada
        for ord_p in orders:
            pw = int(ord_p.get('w', 0))
            ph = int(ord_p.get('h', 0))
            pid = ord_p.get('id', 'Pieza')
            if pw <= 0 or ph <= 0:
                return jsonify({
                    'success': False,
                    'message': f'Error en {pid}: Las medidas del corte ({pw}x{ph}) deben ser mayores a cero.'
                }), 400
            if pw > sheet_width or ph > sheet_height:
                return jsonify({
                    'success': False,
                    'message': f'Error de Medida en {pid}: El corte ({pw}x{ph} {unit_lbl}) supera las dimensiones de la Lamina Madre configurada ({sheet_width}x{sheet_height} {unit_lbl}).'
                }), 400

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
                    def_coords = result.get('defect_coords')
                    x_val = float(def_coords['x']) if isinstance(def_coords, dict) and 'x' in def_coords else 0.0
                    y_val = float(def_coords['y']) if isinstance(def_coords, dict) and 'y' in def_coords else 0.0
                    db_manager.insert_defect(
                        batch_id=1,
                        defect_type=str(result.get('defect_type') or 'Desconocido'),
                        x_coord=x_val,
                        y_coord=y_val,
                        defect_area=float(result.get('defect_area') or 0.0),
                        qc_status=str(result.get('qc_status') or 'PENDIENTE'),
                        severity=str(result.get('severity') or 'LEVE')
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
