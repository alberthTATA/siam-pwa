import sqlite3
import os

class DatabaseManager:
    """
    Gestor de base de datos usando SQLite (Temporalmente para el prototipo local).
    Se encarga de la trazabilidad de los cortes, defectos y mermas (Fase 4).
    Para la versión final, solo haría falta cambiar 'sqlite3' por 'psycopg2' y la cadena de conexión.
    """
    
    # Clave maestra secreta para registrarse como Administrador
    ADMIN_SECRET_KEY = "SIAM2026"
    
    def __init__(self, db_name="siam_traceability.db"):
        self.db_name = db_name
        self._initialize_db()
        
    def _get_connection(self):
        """Retorna una conexión activa a la base de datos local."""
        return sqlite3.connect(self.db_name)
        
    def _initialize_db(self):
        """Crea las tablas relacionales necesarias si no existen (Patrón de migración inicial)."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            # Tabla 1: Registro de lotes de vidrio y proveedores
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS glass_batches (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    provider_name TEXT NOT NULL,
                    date_received TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    total_sheets INTEGER,
                    observations TEXT
                )
            ''')
            
            # Tabla 2: Trazabilidad de inspecciones de calidad (Output de la Red Neuronal y Control de Calidad)
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS quality_inspections (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    batch_id INTEGER,
                    defect_type TEXT, -- Ejemplo: 'Fisura', 'Burbuja'
                    x_coord REAL,
                    y_coord REAL,
                    defect_area REAL,
                    qc_status TEXT DEFAULT 'PENDIENTE',
                    severity TEXT DEFAULT 'LEVE',
                    FOREIGN KEY (batch_id) REFERENCES glass_batches(id)
                )
            ''')
            # Migración suave de columnas de Control de Calidad
            try:
                cursor.execute("ALTER TABLE quality_inspections ADD COLUMN qc_status TEXT DEFAULT 'PENDIENTE'")
            except sqlite3.OperationalError:
                pass
            try:
                cursor.execute("ALTER TABLE quality_inspections ADD COLUMN severity TEXT DEFAULT 'LEVE'")
            except sqlite3.OperationalError:
                pass
            
            # Tabla 3: Histórico de Optimización y Mermas (Output del Bin Packing)
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS cutting_plans (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    batch_id INTEGER,
                    total_area_used REAL,
                    waste_area REAL, -- Cantidad de vidrio desperdiciado (merma)
                    efficiency_score REAL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (batch_id) REFERENCES glass_batches(id)
                )
            ''')
            
            # Tabla 4: Usuarios del Sistema con Rol (admin / usuario)
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT UNIQUE NOT NULL,
                    email TEXT UNIQUE NOT NULL,
                    phone TEXT UNIQUE NOT NULL,
                    password_hash TEXT NOT NULL,
                    role TEXT NOT NULL DEFAULT 'usuario',
                    failed_login_attempts INTEGER DEFAULT 0,
                    account_locked_until TIMESTAMP,
                    password_changed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            # Migraciones suaves para la tabla users
            for col_sql in [
                "ALTER TABLE users ADD COLUMN failed_login_attempts INTEGER DEFAULT 0",
                "ALTER TABLE users ADD COLUMN account_locked_until TIMESTAMP",
                "ALTER TABLE users ADD COLUMN password_changed_at TIMESTAMP",
                "ALTER TABLE users ADD COLUMN created_at TIMESTAMP"
            ]:
                try:
                    cursor.execute(col_sql)
                except sqlite3.OperationalError:
                    pass
            
            # Tabla 5: Registro de Actividad de Usuarios (Para métricas del Admin)
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS activity_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    action TEXT NOT NULL,
                    details TEXT,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users(id)
                )
            ''')

            # Tabla 6: Historial de Contraseñas (Seguridad)
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS password_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    password_hash TEXT NOT NULL,
                    changed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users(id)
                )
            ''')

            # Tabla 7: Códigos de Verificación de Recuperación de Contraseña
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS password_resets (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    code TEXT NOT NULL,
                    expires_at TIMESTAMP NOT NULL,
                    used INTEGER DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users(id)
                )
            ''')
            conn.commit()

    # --- Operaciones CRUD y Autenticación ---
    
    def check_user_exists(self, username, email, phone):
        """Verifica si ya existe un usuario con el mismo username, email o teléfono."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT username, email, phone FROM users WHERE username = ? OR email = ? OR phone = ?",
                (username, email, phone)
            )
            row = cursor.fetchone()
            if row:
                if row[0].lower() == username.lower():
                    return "El Nombre de Usuario ya está registrado."
                if row[1].lower() == email.lower():
                    return "El Correo Electrónico ya está registrado."
                if row[2] == phone:
                    return "El Número de Teléfono ya está registrado."
                return "Uno de los identificadores ya se encuentra registrado."
            return None

    def register_user(self, username, email, phone, password, role='usuario'):
        """Registra un nuevo usuario con múltiples identificadores y un rol."""
        import bcrypt
        # Generar salt y hash usando bcrypt
        salt = bcrypt.gensalt()
        password_hash = bcrypt.hashpw(password.encode(), salt).decode('utf-8')
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "INSERT INTO users (username, email, phone, password_hash, role) VALUES (?, ?, ?, ?, ?)",
                    (username, email, phone, password_hash, role)
                )
            return True
        except sqlite3.IntegrityError:
            return False

    def authenticate_user(self, identifier, password):
        """Verifica las credenciales y retorna (user_id, username, role) o None."""
        import bcrypt
        from datetime import datetime
        
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            # Primero verificar si la cuenta está bloqueada
            cursor.execute(
                """
                SELECT id, username, role, password_hash, failed_login_attempts, account_locked_until
                FROM users 
                WHERE username = ? OR email = ? OR phone = ?
                """,
                (identifier, identifier, identifier)
            )
            result = cursor.fetchone()
            if not result:
                return None
            
            user_id, username, role, stored_hash, failed_attempts, locked_until = result
            
            # Verificar si la cuenta está bloqueada
            if locked_until:
                locked_time = datetime.strptime(locked_until, '%Y-%m-%d %H:%M:%S')
                if locked_time > datetime.now():
                    # Cuenta bloqueada
                    self.log_activity(user_id, "LOGIN_BLOCKED", f"Cuenta bloqueada hasta {locked_until}")
                    return "account_locked"
            
            # Verificar contraseña con bcrypt
            if bcrypt.checkpw(password.encode(), stored_hash.encode('utf-8')):
                # Login exitoso - resetear intentos fallidos
                cursor.execute(
                    "UPDATE users SET failed_login_attempts = 0, account_locked_until = NULL WHERE id = ?",
                    (user_id,)
                )
                self.log_activity(user_id, "LOGIN_SUCCESS", "Autenticación exitosa")
                conn.commit()
                return (user_id, username, role)
            else:
                # Login fallido - incrementar contador
                cursor.execute(
                    "UPDATE users SET failed_login_attempts = failed_login_attempts + 1 WHERE id = ?",
                    (user_id,)
                )
                self.log_activity(user_id, "LOGIN_FAILED", f"Intento fallido #{failed_attempts + 1}")
                conn.commit()
                return None

    def log_activity(self, user_id, action, details=""):
        """Registra una acción del usuario en el historial de actividad."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO activity_log (user_id, action, details) VALUES (?, ?, ?)",
                (user_id, action, details)
            )

    def change_password(self, user_id, old_password, new_password):
        """Cambia la contraseña de un usuario verificando la antigua."""
        import bcrypt
        
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            # Obtener hash actual
            cursor.execute("SELECT password_hash FROM users WHERE id = ?", (user_id,))
            result = cursor.fetchone()
            if not result:
                return False
            
            stored_hash = result[0]
            
            # Verificar contraseña antigua
            if not bcrypt.checkpw(old_password.encode(), stored_hash.encode('utf-8')):
                return False
            
            # Verificar que no sea una contraseña reciente (últimas 5)
            cursor.execute(
                """
                SELECT COUNT(*) FROM password_history 
                WHERE user_id = ? AND password_hash = ?
                ORDER BY changed_at DESC LIMIT 5
                """,
                (user_id, bcrypt.hashpw(new_password.encode(), bcrypt.gensalt()).decode('utf-8'))
            )
            if cursor.fetchone()[0] > 0:
                return "password_reused"
            
            # Generar nuevo hash
            new_hash = bcrypt.hashpw(new_password.encode(), bcrypt.gensalt()).decode('utf-8')
            
            # Actualizar contraseña
            cursor.execute(
                "UPDATE users SET password_hash = ? WHERE id = ?",
                (new_hash, user_id)
            )
            
            # Resetear intentos fallidos
            cursor.execute(
                "UPDATE users SET failed_login_attempts = 0, account_locked_until = NULL WHERE id = ?",
                (user_id,)
            )
            
            self.log_activity(user_id, "PASSWORD_CHANGE", "Contraseña cambiada exitosamente")
            conn.commit()
            return True

    def get_user_for_recovery(self, identifier):
        """Busca un usuario por su nombre de usuario o correo electrónico para recuperación."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT id, username, email FROM users WHERE LOWER(username) = LOWER(?) OR LOWER(email) = LOWER(?)",
                (identifier.strip(), identifier.strip())
            )
            return cursor.fetchone()

    def create_password_reset_code(self, user_id):
        """Genera un código numérico aleatorio de 6 dígitos con vigencia de 15 minutos."""
        import random
        from datetime import datetime, timedelta
        
        code = f"{random.randint(100000, 999999)}"
        expires_at = (datetime.now() + timedelta(minutes=15)).strftime("%Y-%m-%d %H:%M:%S")
        
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("UPDATE password_resets SET used = 1 WHERE user_id = ? AND used = 0", (user_id,))
            cursor.execute(
                "INSERT INTO password_resets (user_id, code, expires_at, used) VALUES (?, ?, ?, 0)",
                (user_id, code, expires_at)
            )
            conn.commit()
        return code

    def verify_password_reset_code(self, user_id, code):
        """Verifica si el código ingresado es válido y no ha expirado."""
        from datetime import datetime
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT id, expires_at FROM password_resets WHERE user_id = ? AND code = ? AND used = 0 ORDER BY id DESC LIMIT 1",
                (user_id, str(code).strip())
            )
            row = cursor.fetchone()
            if not row:
                return False, "El código de verificación es incorrecto o ya fue utilizado."
            
            reset_id, expires_at = row
            try:
                exp_dt = datetime.strptime(expires_at, "%Y-%m-%d %H:%M:%S")
                if datetime.now() > exp_dt:
                    return False, "El código de verificación ha expirado. Solicite uno nuevo."
            except Exception:
                pass
            return True, "Código válido."

    def complete_password_reset(self, user_id, code, new_password):
        """Restablece la contraseña del usuario tras validar el código."""
        import bcrypt
        from datetime import datetime
        
        valid, msg = self.verify_password_reset_code(user_id, code)
        if not valid:
            return False, msg
            
        new_hash = bcrypt.hashpw(new_password.encode(), bcrypt.gensalt()).decode('utf-8')
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        with self._get_connection() as conn:
            cursor = conn.cursor()
            # Actualizar contraseña y resetear bloqueos
            cursor.execute(
                """
                UPDATE users 
                SET password_hash = ?, failed_login_attempts = 0, account_locked_until = NULL, password_changed_at = ?
                WHERE id = ?
                """,
                (new_hash, now_str, user_id)
            )
            # Marcar código como usado
            cursor.execute("UPDATE password_resets SET used = 1 WHERE user_id = ? AND code = ?", (user_id, str(code).strip()))
            
            # Registrar en historial de contraseñas
            cursor.execute(
                "INSERT INTO password_history (user_id, password_hash, changed_at) VALUES (?, ?, ?)",
                (user_id, new_hash, now_str)
            )
            
            cursor.execute(
                "INSERT INTO activity_log (user_id, action, details) VALUES (?, ?, ?)",
                (user_id, "PASSWORD_RECOVERY", "Contraseña restablecida exitosamente vía código de verificación por correo")
            )
            conn.commit()
        return True, "Contraseña actualizada exitosamente."

    def get_user_security_status(self, user_id):
        """Retorna el estado de seguridad de un usuario."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT 
                    u.username,
                    u.failed_login_attempts,
                    u.account_locked_until,
                    u.password_changed_at,
                    julianday('now') - julianday(u.password_changed_at) as days_since_change,
                    COUNT(ph.id) as password_history_count
                FROM users u
                LEFT JOIN password_history ph ON u.id = ph.user_id
                WHERE u.id = ?
                GROUP BY u.id
            """, (user_id,))
            return cursor.fetchone()

    def unlock_user_account(self, user_id):
        """Desbloquea la cuenta de un usuario."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE users SET account_locked_until = NULL, failed_login_attempts = 0 WHERE id = ?",
                (user_id,)
            )
            self.log_activity(user_id, "ACCOUNT_UNLOCKED", "Cuenta desbloqueada por administrador")
            conn.commit()
            return True

    def get_all_users(self):
        """Retorna la lista de todos los usuarios no-admin."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id, username, email, phone, role FROM users WHERE role = 'usuario'")
            return cursor.fetchall()

    def get_user_activity(self, user_id=None):
        """Retorna el historial de actividad. Si se pasa user_id, filtra por ese usuario."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            if user_id:
                cursor.execute("""
                    SELECT a.id, u.username, a.action, a.details, a.timestamp, u.role 
                    FROM activity_log a JOIN users u ON a.user_id = u.id 
                    WHERE a.user_id = ? ORDER BY a.timestamp DESC
                """, (user_id,))
            else:
                cursor.execute("""
                    SELECT a.id, u.username, a.action, a.details, a.timestamp, u.role 
                    FROM activity_log a JOIN users u ON a.user_id = u.id 
                    ORDER BY a.timestamp DESC
                """)
            return cursor.fetchall()

    def get_all_users(self):
        """Retorna todos los usuarios registrados en el sistema."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id, username, email, phone, role FROM users ORDER BY id ASC")
            return cursor.fetchall()

    def get_user_metrics(self, role=None):
        """Retorna métricas resumidas por usuario (cantidad de acciones por tipo)."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            if role:
                cursor.execute("""
                    SELECT u.username, u.role, a.action, COUNT(*) as total
                    FROM activity_log a JOIN users u ON a.user_id = u.id
                    WHERE u.role = ?
                    GROUP BY u.username, u.role, a.action
                    ORDER BY u.username, total DESC
                """, (role,))
            else:
                cursor.execute("""
                    SELECT u.username, u.role, a.action, COUNT(*) as total
                    FROM activity_log a JOIN users u ON a.user_id = u.id
                    GROUP BY u.username, u.role, a.action
                    ORDER BY u.role ASC, u.username, total DESC
                """)
            return cursor.fetchall()

    def insert_batch(self, provider_name, total_sheets, observations=""):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO glass_batches (provider_name, total_sheets, observations) VALUES (?, ?, ?)",
                (provider_name, total_sheets, observations)
            )
            return cursor.lastrowid
            
    def insert_defect(self, batch_id, defect_type, x_coord, y_coord, defect_area, qc_status='APROBADO', severity='LEVE'):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO quality_inspections (batch_id, defect_type, x_coord, y_coord, defect_area, qc_status, severity) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (batch_id, defect_type, x_coord, y_coord, defect_area, qc_status, severity)
            )
            return cursor.lastrowid

    def get_quality_inspections(self):
        """Retorna todas las inspecciones con datos de control de calidad."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id, batch_id, defect_type, x_coord, y_coord, defect_area, qc_status, severity FROM quality_inspections ORDER BY id DESC")
            return cursor.fetchall()
            
    def insert_cutting_plan(self, batch_id, total_area_used, waste_area, efficiency_score):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO cutting_plans (batch_id, total_area_used, waste_area, efficiency_score) VALUES (?, ?, ?, ?)",
                (batch_id, total_area_used, waste_area, efficiency_score)
            )
            return cursor.lastrowid

    # --- Métodos para Dashboard Gráfico de Defectos ---
    
    def get_defect_statistics(self):
        """Retorna estadísticas de defectos para el dashboard."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            # Estadísticas por tipo de defecto
            cursor.execute("""
                SELECT defect_type, COUNT(*) as cantidad, 
                       AVG(defect_area) as area_promedio, 
                       AVG(x_coord) as x_promedio,
                       AVG(y_coord) as y_promedio
                FROM quality_inspections 
                GROUP BY defect_type
                ORDER BY cantidad DESC
            """)
            defect_stats = cursor.fetchall()
            
            # Distribución por severidad
            cursor.execute("""
                SELECT severity, COUNT(*) as cantidad,
                       AVG(defect_area) as area_promedio
                FROM quality_inspections 
                GROUP BY severity
                ORDER BY 
                    CASE severity 
                        WHEN 'CRÍTICA' THEN 1
                        WHEN 'GRAVE' THEN 2
                        WHEN 'MODERADA' THEN 3
                        WHEN 'LEVE' THEN 4
                        WHEN 'TOLERABLE' THEN 5
                        ELSE 6
                    END
            """)
            severity_stats = cursor.fetchall()
            
            # Estado de control de calidad
            cursor.execute("""
                SELECT qc_status, COUNT(*) as cantidad,
                       AVG(defect_area) as area_promedio
                FROM quality_inspections 
                GROUP BY qc_status
            """)
            qc_stats = cursor.fetchall()
            
            # Datos de coordenadas para mapa térmico
            cursor.execute("""
                SELECT x_coord, y_coord, defect_type, severity, defect_area
                FROM quality_inspections
                ORDER BY id DESC
                LIMIT 100
            """)
            heatmap_data = cursor.fetchall()
            
            # Estadísticas generales
            cursor.execute("""
                SELECT 
                    COUNT(*) as total_defectos,
                    AVG(defect_area) as area_promedio_total,
                    MAX(defect_area) as area_maxima,
                    MIN(defect_area) as area_minima,
                    SUM(defect_area) as area_total
                FROM quality_inspections
            """)
            general_stats = cursor.fetchone()
            
            # Estadísticas por lote
            cursor.execute("""
                SELECT gb.id, gb.provider_name, 
                       COUNT(qi.id) as defectos_lote,
                       AVG(qi.defect_area) as area_promedio_lote
                FROM glass_batches gb
                LEFT JOIN quality_inspections qi ON gb.id = qi.batch_id
                GROUP BY gb.id, gb.provider_name
                ORDER BY defectos_lote DESC
            """)
            batch_stats = cursor.fetchall()
            
            return {
                'defect_stats': defect_stats,
                'severity_stats': severity_stats,
                'qc_stats': qc_stats,
                'heatmap_data': heatmap_data,
                'general_stats': general_stats,
                'batch_stats': batch_stats
            }
    
    def get_defect_trends(self, days=30):
        """Retorna tendencias de defectos por fecha."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(f"""
                SELECT DATE(gb.date_received) as fecha, 
                       COUNT(qi.id) as total_defectos,
                       AVG(qi.defect_area) as area_promedio
                FROM glass_batches gb
                LEFT JOIN quality_inspections qi ON gb.id = qi.batch_id
                WHERE gb.date_received >= date('now', '-{days} days')
                GROUP BY DATE(gb.date_received)
                ORDER BY fecha
            """)
            return cursor.fetchall()
    
    def get_efficiency_correlation(self):
        """Retorna correlación entre defectos y eficiencia de corte."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT gb.id, 
                       COUNT(qi.id) as total_defectos,
                       COALESCE(AVG(qi.defect_area), 0) as area_defectos_promedio,
                       COALESCE(cp.efficiency_score, 0) as eficiencia,
                       COALESCE(cp.waste_area, 0) as merma
                FROM glass_batches gb
                LEFT JOIN quality_inspections qi ON gb.id = qi.batch_id
                LEFT JOIN cutting_plans cp ON gb.id = cp.batch_id
                GROUP BY gb.id
                HAVING eficiencia > 0
                ORDER BY eficiencia DESC
            """)
            return cursor.fetchall()
