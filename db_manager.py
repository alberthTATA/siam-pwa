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
    # Credenciales por defecto del Superusuario exclusivo para el Programador
    SUPERUSER_USERNAME = "programador"
    SUPERUSER_EMAIL = "programador@siam.com"
    SUPERUSER_PHONE = "04120000000"
    SUPERUSER_DEFAULT_PASS = "SiamProg2026!"

    @staticmethod
    def validate_strict_email(email):
        """
        Valida de forma estricta un correo electrónico.
        Retorna (True, "") si es válido o (False, mensaje_error) si es inválido.
        """
        import re
        if not email or not isinstance(email, str):
            return False, "El correo electrónico es obligatorio."
        email = email.strip()
        if " " in email:
            return False, "El correo electrónico no puede contener espacios en blanco."
        if email.count("@") != 1:
            return False, "El correo electrónico debe contener exactamente un símbolo '@'."
        local_part, domain_part = email.split("@")
        if not local_part or len(local_part) < 2:
            return False, "El nombre de usuario del correo (antes del @) debe tener al menos 2 caracteres."
        if len(local_part) > 64 or len(email) > 254:
            return False, "El correo electrónico excede la longitud máxima permitida."
        if local_part.startswith(".") or local_part.endswith(".") or ".." in email:
            return False, "El correo electrónico no puede iniciar, terminar ni tener puntos consecutivos (..)."
        if not re.match(r"^[A-Za-z0-9._%+\-]+$", local_part):
            return False, "El usuario del correo contiene caracteres inválidos."
        if not domain_part or "." not in domain_part:
            return False, "El dominio del correo debe incluir una extensión válida (ejemplo: @gmail.com)."
        if domain_part.startswith(".") or domain_part.endswith(".") or domain_part.startswith("-") or domain_part.endswith("-"):
            return False, "El dominio del correo tiene un formato inválido."
        domain_labels = domain_part.lower().split(".")
        if any(len(lbl) == 0 for lbl in domain_labels):
            return False, "El dominio del correo contiene puntos vacíos consecutivos."
        tld = domain_labels[-1]
        sld = domain_labels[-2]
        if len(sld) < 2:
            return False, "El nombre del proveedor de correo después del '@' es demasiado corto."
        if not re.match(r"^[a-z]{2,12}$", tld):
            return False, "La extensión del correo (ej. .com, .es, .ve, .org) debe tener entre 2 y 12 letras sin números."
        for lbl in domain_labels:
            if not re.match(r"^[a-z0-9\-]+$", lbl) or lbl.startswith("-") or lbl.endswith("-"):
                return False, f"El segmento de dominio '{lbl}' no es válido."
        common_typos = {
            "gmal.com": "gmail.com",
            "gmial.com": "gmail.com",
            "gamil.com": "gmail.com",
            "gmail.co": "gmail.com",
            "gmail.c": "gmail.com",
            "hotmial.com": "hotmail.com",
            "hotmal.com": "hotmail.com",
            "outlok.com": "outlook.com",
            "yaho.com": "yahoo.com"
        }
        domain_low = domain_part.lower()
        if domain_low in common_typos:
            sugerencia = common_typos[domain_low]
            return False, f"Dominio '{domain_low}' inválido o mal escrito. ¿Quiso decir '@{sugerencia}'?"
        return True, "Correo electrónico válido."
    
    def __init__(self, db_name=None):
        if db_name is None:
            base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
            db_name = os.path.join(base_dir, "siam_traceability.db")
        self.db_name = db_name
        self._initialize_db()
        
    def _get_connection(self):
        """Retorna una conexión activa a la base de datos local con timeout para evitar bloqueos."""
        return sqlite3.connect(self.db_name, timeout=10)
        
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

            # Tabla 8: Pedidos de Corte Solicitados (Trazabilidad de Órdenes de Clientes)
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS cutting_orders (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    order_code TEXT NOT NULL,
                    width_mm INTEGER NOT NULL,
                    height_mm INTEGER NOT NULL,
                    status TEXT DEFAULT 'PENDIENTE',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Asegurar que exista el Superusuario exclusivo para el Programador (Rol: superadmin)
            cursor.execute("SELECT id, role FROM users WHERE LOWER(username) = LOWER(?)", (self.SUPERUSER_USERNAME,))
            super_row = cursor.fetchone()
            if not super_row:
                import hashlib
                try:
                    import bcrypt
                    pwd_hash = bcrypt.hashpw(self.SUPERUSER_DEFAULT_PASS.encode(), bcrypt.gensalt()).decode('utf-8')
                except Exception:
                    pwd_hash = hashlib.sha256(self.SUPERUSER_DEFAULT_PASS.encode()).hexdigest()
                try:
                    cursor.execute(
                        "INSERT INTO users (username, email, phone, password_hash, role) VALUES (?, ?, ?, ?, 'superadmin')",
                        (self.SUPERUSER_USERNAME, self.SUPERUSER_EMAIL, self.SUPERUSER_PHONE, pwd_hash)
                    )
                except sqlite3.IntegrityError:
                    pass
            elif super_row[1] != 'superadmin':
                cursor.execute("UPDATE users SET role = 'superadmin' WHERE id = ?", (super_row[0],))
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
        
        identifier = (identifier or "").strip()
        password = (password or "").strip()
        
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            # Primero verificar si la cuenta está bloqueada (búsqueda insensible a mayúsculas/minúsculas)
            cursor.execute(
                """
                SELECT id, username, role, password_hash, failed_login_attempts, account_locked_until
                FROM users 
                WHERE LOWER(username) = LOWER(?) OR LOWER(email) = LOWER(?) OR phone = ?
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
                    cursor.execute(
                        "INSERT INTO activity_log (user_id, action, details) VALUES (?, ?, ?)",
                        (user_id, "LOGIN_BLOCKED", f"Cuenta bloqueada hasta {locked_until}")
                    )
                    conn.commit()
                    return "account_locked"
            
            # Verificar contraseña con bcrypt (con soporte de migración para SHA-256)
            import hashlib
            password_ok = False
            try:
                if stored_hash.startswith(('$2b$', '$2a$', '$2y$')):
                    password_ok = bcrypt.checkpw(password.encode(), stored_hash.encode('utf-8'))
                else:
                    # Respaldo para cuentas creadas con SHA-256 (como alberth19)
                    sha256_hash = hashlib.sha256(password.encode()).hexdigest()
                    if sha256_hash == stored_hash:
                        password_ok = True
                        # Actualizar automáticamente el hash a bcrypt
                        new_bcrypt_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode('utf-8')
                        cursor.execute("UPDATE users SET password_hash = ? WHERE id = ?", (new_bcrypt_hash, user_id))
            except Exception:
                password_ok = False

            if password_ok:
                # Login exitoso - resetear intentos fallidos
                cursor.execute(
                    "UPDATE users SET failed_login_attempts = 0, account_locked_until = NULL WHERE id = ?",
                    (user_id,)
                )
                cursor.execute(
                    "INSERT INTO activity_log (user_id, action, details) VALUES (?, ?, ?)",
                    (user_id, "LOGIN_SUCCESS", "Autenticación exitosa")
                )
                conn.commit()
                return (user_id, username, role)
            else:
                # Login fallido - incrementar contador
                cursor.execute(
                    "UPDATE users SET failed_login_attempts = failed_login_attempts + 1 WHERE id = ?",
                    (user_id,)
                )
                cursor.execute(
                    "INSERT INTO activity_log (user_id, action, details) VALUES (?, ?, ?)",
                    (user_id, "LOGIN_FAILED", f"Intento fallido #{failed_attempts + 1}")
                )
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
            conn.commit()

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
            row_hist = cursor.fetchone()
            if row_hist and row_hist[0] > 0:
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
            
            cursor.execute(
                "INSERT INTO activity_log (user_id, action, details) VALUES (?, ?, ?)",
                (user_id, "PASSWORD_CHANGE", "Contraseña cambiada exitosamente")
            )
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
            cursor.execute(
                "INSERT INTO activity_log (user_id, action, details) VALUES (?, ?, ?)",
                (user_id, "ACCOUNT_UNLOCKED", "Cuenta desbloqueada por administrador")
            )
            conn.commit()
            return True

    def get_all_users(self):
        """Retorna todos los usuarios registrados en el sistema."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id, username, email, phone, role FROM users ORDER BY id ASC")
            return cursor.fetchall()

    def get_user_by_id(self, user_id):
        """Obtiene los datos de un usuario por su ID."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id, username, email, phone, role FROM users WHERE id = ?", (int(user_id),))
            return cursor.fetchone()

    def admin_search_users(self, search_term=""):
        """4. Consultar Usuario: Busca usuarios por ID, nombre de usuario, correo, teléfono o rol."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            term = (search_term or "").strip()
            if not term:
                cursor.execute("SELECT id, username, email, phone, role FROM users ORDER BY id ASC")
                return cursor.fetchall()
            like_term = f"%{term}%"
            cursor.execute(
                """
                SELECT id, username, email, phone, role
                FROM users
                WHERE CAST(id AS TEXT) = ?
                   OR LOWER(username) LIKE LOWER(?)
                   OR LOWER(email) LIKE LOWER(?)
                   OR phone LIKE ?
                   OR LOWER(role) LIKE LOWER(?)
                ORDER BY id ASC
                """,
                (term, like_term, like_term, like_term, like_term)
            )
            return cursor.fetchall()

    def admin_add_user(self, username, email, phone, password, role='usuario'):
        """1. Agregar Usuario desde el Panel Administrativo con validación estricta."""
        username = (username or "").strip()
        email = (email or "").strip()
        phone = (phone or "").strip()
        if not username or len(username) < 3:
            return False, "El nombre de usuario debe tener al menos 3 caracteres."
        valid_mail, mail_msg = self.validate_strict_email(email)
        if not valid_mail:
            return False, mail_msg
        if not phone.isdigit() or len(phone) < 10:
            return False, "El teléfono debe contener solo dígitos numéricos (mínimo 10 dígitos)."
        if not password or len(password) < 6:
            return False, "La contraseña debe tener al menos 6 caracteres."
        dup = self.check_user_exists(username, email, phone)
        if dup:
            return False, dup
        if role not in ('usuario', 'admin', 'superadmin'):
            role = 'usuario'
        ok = self.register_user(username, email, phone, password, role)
        if ok:
            return True, f"Usuario '{username}' agregado exitosamente con rol '{role}'."
        return False, "No se pudo agregar el usuario por conflicto de integridad en la base de datos."

    def admin_update_user(self, user_id, username, email, phone, role='usuario', new_password=None):
        """2. Modificar Usuario desde el Panel Administrativo."""
        import bcrypt
        username = (username or "").strip()
        email = (email or "").strip()
        phone = (phone or "").strip()
        if not username or len(username) < 3:
            return False, "El nombre de usuario debe tener al menos 3 caracteres."
        valid_mail, mail_msg = self.validate_strict_email(email)
        if not valid_mail:
            return False, mail_msg
        if not phone.isdigit() or len(phone) < 10:
            return False, "El teléfono debe contener solo dígitos numéricos (mínimo 10 dígitos)."
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT username, role FROM users WHERE id = ?", (int(user_id),))
            existing = cursor.fetchone()
            if not existing:
                return False, "El usuario seleccionado no existe."
            if existing[0].lower() == self.SUPERUSER_USERNAME.lower():
                role = 'superadmin'
                username = self.SUPERUSER_USERNAME
            cursor.execute(
                "SELECT id FROM users WHERE (LOWER(username) = LOWER(?) OR LOWER(email) = LOWER(?) OR phone = ?) AND id != ?",
                (username, email, phone, int(user_id))
            )
            if cursor.fetchone():
                return False, "Otro usuario ya tiene registrado ese nombre, correo o teléfono."
            if new_password and new_password.strip():
                if len(new_password.strip()) < 6:
                    return False, "La nueva contraseña debe tener al menos 6 caracteres."
                new_hash = bcrypt.hashpw(new_password.strip().encode(), bcrypt.gensalt()).decode('utf-8')
                cursor.execute(
                    "UPDATE users SET username = ?, email = ?, phone = ?, role = ?, password_hash = ? WHERE id = ?",
                    (username, email, phone, role, new_hash, int(user_id))
                )
            else:
                cursor.execute(
                    "UPDATE users SET username = ?, email = ?, phone = ?, role = ? WHERE id = ?",
                    (username, email, phone, role, int(user_id))
                )
            conn.commit()
            return True, f"Usuario ID #{user_id} ('{username}') modificado correctamente."

    def admin_delete_user(self, user_id):
        """3. Eliminar Usuario desde el Panel Administrativo (protege al superusuario)."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT username, role FROM users WHERE id = ?", (int(user_id),))
            row = cursor.fetchone()
            if not row:
                return False, "El usuario especificado no existe."
            uname, urole = row
            if uname.lower() == self.SUPERUSER_USERNAME.lower() or urole == 'superadmin':
                return False, "El Superusuario del Programador está protegido y no puede ser eliminado."
            cursor.execute("DELETE FROM activity_log WHERE user_id = ?", (int(user_id),))
            cursor.execute("DELETE FROM password_history WHERE user_id = ?", (int(user_id),))
            cursor.execute("DELETE FROM password_resets WHERE user_id = ?", (int(user_id),))
            cursor.execute("DELETE FROM users WHERE id = ?", (int(user_id),))
            conn.commit()
            return True, f"Usuario '{uname}' (ID #{user_id}) eliminado permanentemente."

    # --- Métodos exclusivos del Módulo de Mantenimiento (Superusuario Programador) ---

    def backup_database(self):
        """Crea una copia de seguridad física (.db) de la base de datos SQLite."""
        import shutil
        from datetime import datetime
        base_dir = os.path.dirname(os.path.abspath(self.db_name))
        backup_dir = os.path.join(base_dir, "backups")
        os.makedirs(backup_dir, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = os.path.join(backup_dir, f"siam_backup_{stamp}.db")
        shutil.copy2(self.db_name, backup_path)
        return True, backup_path

    def run_maintenance_diagnostics(self):
        """Ejecuta PRAGMA integrity_check, optimiza índices y retorna métricas técnicas para el Programador."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("PRAGMA integrity_check")
            row_int = cursor.fetchone()
            integrity = row_int[0] if row_int else "ok"
            tables = ["users", "glass_batches", "quality_inspections", "cutting_plans", "cutting_orders", "activity_log"]
            counts = {}
            for t in tables:
                cursor.execute(f"SELECT COUNT(*) FROM {t}")
                row_cnt = cursor.fetchone()
                counts[t] = row_cnt[0] if row_cnt else 0
        try:
            with self._get_connection() as conn:
                conn.isolation_level = None
                conn.execute("VACUUM")
        except Exception:
            pass
        db_size_kb = round(os.path.getsize(self.db_name) / 1024.0, 2) if os.path.exists(self.db_name) else 0.0
        return {
            "integrity": integrity,
            "db_size_kb": db_size_kb,
            "db_path": self.db_name,
            "table_counts": counts,
            "users_count": counts.get("users", 0),
            "locked_users": 0,
            "logs_count": counts.get("activity_log", 0),
            "grid_modality": "Motor Matricial 2D FFD Activo"
        }

    def unlock_all_accounts(self):
        """Desbloquea todas las cuentas de usuario y reinicia los contadores de intentos fallidos."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("UPDATE users SET failed_login_attempts = 0, account_locked_until = NULL")
            affected = cursor.rowcount
            conn.commit()
            return True, f"Se restablecieron los bloqueos de seguridad en {affected} cuentas registradas."

    def clear_old_activity_logs(self):
        """Limpia registros antiguos de auditoría manteniendo los últimos 25 eventos."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "DELETE FROM activity_log WHERE id NOT IN (SELECT id FROM activity_log ORDER BY id DESC LIMIT 25)"
            )
            deleted = cursor.rowcount
            conn.commit()
            return True, f"Mantenimiento de auditoría completado. Registros antiguos depurados: {deleted}."

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
            conn.commit()
            return cursor.lastrowid

    def insert_cutting_order(self, order_code, width_mm, height_mm, status='PENDIENTE'):
        """Registra un pedido de corte en la tabla relacional cutting_orders."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO cutting_orders (order_code, width_mm, height_mm, status) VALUES (?, ?, ?, ?)",
                (order_code, int(width_mm), int(height_mm), status)
            )
            conn.commit()
            return cursor.lastrowid

    def get_cutting_orders(self):
        """Retorna todos los pedidos de corte registrados."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id, order_code, width_mm, height_mm, status, created_at FROM cutting_orders ORDER BY id DESC")
            return cursor.fetchall()

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
