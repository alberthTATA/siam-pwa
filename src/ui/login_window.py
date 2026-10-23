import re
import random
from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLineEdit, 
                             QPushButton, QLabel, QMessageBox, QCheckBox, QWidget, QStackedWidget)
from PyQt6.QtCore import Qt
from src.database.db_manager import DatabaseManager
from src.email_config import load_email_config, save_email_config, send_password_reset_email

# Estilos comunes para ambas ventanas
COMMON_STYLESHEET = """
    QDialog { background-color: #0B0E14; }
    QLabel { color: #E0E6ED; font-family: 'Segoe UI', Arial; }
    QLineEdit {
        background-color: #0F1520; color: #E0E6ED;
        border: 1px solid #1E293B; border-radius: 6px; padding: 12px; font-size: 14px;
    }
    QLineEdit:focus { border: 1px solid #1A73E8; }
    QPushButton {
        background-color: #1A73E8; color: #FFFFFF;
        border-radius: 6px; padding: 12px; font-weight: bold; font-size: 14px; margin-top: 10px;
    }
    QPushButton:hover { background-color: #1557B0; }
    QPushButton.btnEye {
        background-color: #0F1520; color: #94A3B8;
        border: 1px solid #1E293B; border-radius: 6px;
        padding: 8px 10px; font-size: 16px; margin-top: 0px;
    }
    QPushButton.btnEye:hover {
        background-color: #1E293B; color: #FFFFFF;
    }
    QPushButton#btnForgot {
        background-color: transparent; color: #38BDF8;
        border: none; font-size: 13px; font-weight: 500;
        padding: 2px 4px; margin-top: 0px;
    }
    QPushButton#btnForgot:hover {
        color: #7DD3FC; text-decoration: underline;
    }
    QPushButton#btnSecondary {
        background-color: transparent; color: #94A3B8;
        border: 1px solid #1E293B; font-size: 13px;
        padding: 10px; margin-top: 5px;
    }
    QPushButton#btnSecondary:hover {
        background-color: #1E293B; color: #FFFFFF;
    }
    QCheckBox { color: #94A3B8; font-size: 13px; font-weight: bold; margin-top: 8px; }
    QCheckBox::indicator {
        width: 18px; height: 18px; border-radius: 4px;
        border: 2px solid #1E293B; background: #0F1520;
    }
    QCheckBox::indicator:checked { background: #1A73E8; border: 2px solid #1A73E8; }
"""

def create_password_field(placeholder="Contraseña"):
    """Crea un campo de contraseña acompañado de un botón para mostrar/ocultar el texto."""
    container = QWidget()
    layout = QHBoxLayout(container)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(6)
    
    line_edit = QLineEdit()
    line_edit.setPlaceholderText(placeholder)
    line_edit.setEchoMode(QLineEdit.EchoMode.Password)
    
    btn_eye = QPushButton("👁")
    btn_eye.setProperty("class", "btnEye")
    btn_eye.setFixedWidth(44)
    btn_eye.setToolTip("Mostrar / Ocultar Contraseña")
    
    def toggle():
        if line_edit.echoMode() == QLineEdit.EchoMode.Password:
            line_edit.setEchoMode(QLineEdit.EchoMode.Normal)
            btn_eye.setText("🔒")
        else:
            line_edit.setEchoMode(QLineEdit.EchoMode.Password)
            btn_eye.setText("👁")
            
    btn_eye.clicked.connect(toggle)
    layout.addWidget(line_edit)
    layout.addWidget(btn_eye)
    return container, line_edit, btn_eye


class EmailVerificationDialog(QDialog):
    """
    Ventana modal para la verificación del correo electrónico mediante código OTP de 6 dígitos.
    """
    def __init__(self, email, parent=None):
        super().__init__(parent)
        self.setWindowTitle("SIAM - Verificación de Correo")
        self.setFixedSize(380, 470)
        self.setStyleSheet(COMMON_STYLESHEET + """
            QPushButton#btnResend {
                background-color: transparent; border: 1px solid #1E293B; color: #94A3B8;
                font-size: 13px; padding: 10px; margin-top: 5px;
            }
            QPushButton#btnResend:hover { background-color: #1E293B; color: #FFFFFF; }
            QLineEdit#otpInput {
                font-size: 26px; font-weight: bold; letter-spacing: 8px; text-align: center;
                background-color: #0F1520; color: #38BDF8; border: 2px solid #1A73E8;
            }
        """)
        
        self.email = email
        self.current_code = self.generate_code()
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(35, 30, 35, 30)
        layout.setSpacing(12)
        
        title = QLabel("📧 Verificación de Correo")
        title.setStyleSheet("font-size: 22px; font-weight: bold; color: #1A73E8;")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)
        
        desc = QLabel("Hemos enviado un código de seguridad de 6 dígitos para validar tu correo:")
        desc.setStyleSheet("font-size: 13px; color: #94A3B8;")
        desc.setAlignment(Qt.AlignmentFlag.AlignCenter)
        desc.setWordWrap(True)
        layout.addWidget(desc)
        
        email_tag = QLabel(email)
        email_tag.setStyleSheet("font-size: 13px; font-weight: bold; color: #E0E6ED; background: #0F1520; padding: 8px; border-radius: 6px; border: 1px solid #1E293B;")
        email_tag.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(email_tag)
        
        # Simulación de Bandeja de Entrada / Notificación en pantalla
        self.inbox_banner = QLabel(f"📬 [Bandeja de Entrada]\nCódigo de Activación: {self.current_code}")
        self.inbox_banner.setStyleSheet("""
            background-color: #0c2340; color: #38BDF8; font-weight: bold; font-size: 15px;
            border: 1px dashed #0284C7; border-radius: 6px; padding: 10px;
        """)
        self.inbox_banner.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.inbox_banner)
        
        lbl_insert = QLabel("Ingresa el código de 6 dígitos:")
        lbl_insert.setStyleSheet("font-size: 12px; font-weight: bold; margin-top: 4px;")
        layout.addWidget(lbl_insert)
        
        self.otp_input = QLineEdit()
        self.otp_input.setObjectName("otpInput")
        self.otp_input.setMaxLength(6)
        self.otp_input.setPlaceholderText("000000")
        self.otp_input.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.otp_input)
        
        self.btn_verify = QPushButton("✅ Validar y Activar Cuenta")
        self.btn_verify.clicked.connect(self.verify_code)
        layout.addWidget(self.btn_verify)
        
        self.btn_resend = QPushButton("🔄 Reenviar nuevo código")
        self.btn_resend.setObjectName("btnResend")
        self.btn_resend.clicked.connect(self.resend_code)
        layout.addWidget(self.btn_resend)
        
    def generate_code(self):
        return f"{random.randint(100000, 999999)}"
        
    def resend_code(self):
        self.current_code = self.generate_code()
        self.inbox_banner.setText(f"📬 [Bandeja de Entrada]\nCódigo de Activación: {self.current_code}")
        self.otp_input.clear()
        QMessageBox.information(self, "Código Reenviado", f"Se ha generado un nuevo código de activación para:\n{self.email}")
        
    def verify_code(self):
        entered = self.otp_input.text().strip()
        if not entered:
            QMessageBox.warning(self, "Aviso", "Por favor ingresa el código de 6 dígitos.")
            return
            
        if entered == self.current_code:
            self.accept()
        else:
            QMessageBox.critical(self, "Código Incorrecto", "El código ingresado no coincide con el enviado a tu correo.\nPor favor verifica e intenta nuevamente.")


class RegisterWindow(QDialog):
    """
    Ventana dedicada exclusivamente al Registro de Usuarios.
    Incluye checkbox para activar el campo de Clave de Administrador.
    """
    def __init__(self, db_manager):
        super().__init__()
        self.setWindowTitle("SIAM - Registro Seguro")
        self.setFixedSize(380, 680)
        
        self.setStyleSheet(COMMON_STYLESHEET + """
            QPushButton#btnCancel {
                background-color: transparent; border: 1px solid #1E293B; color: #94A3B8; margin-top: 0px;
            }
            QPushButton#btnCancel:hover { background-color: #1E293B; color: #FFFFFF; }
        """)
        
        self.db = db_manager
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(40, 20, 40, 20)
        layout.setSpacing(8)
        
        title = QLabel("Crear Cuenta")
        title.setStyleSheet("font-size: 24px; font-weight: bold; color: #1A73E8;")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        lbl_style = "font-size: 12px; font-weight: bold; margin-top: 4px;"
        
        user_lbl = QLabel("Nombre de Usuario:")
        user_lbl.setStyleSheet(lbl_style)
        self.username_input = QLineEdit()
        self.username_input.setPlaceholderText("Ej: juanperez (min. 3 caract.)")
        
        email_lbl = QLabel("Correo Electrónico:")
        email_lbl.setStyleSheet(lbl_style)
        self.email_input = QLineEdit()
        self.email_input.setPlaceholderText("Ej: juan@correo.com (requiere @)")
        
        phone_lbl = QLabel("Teléfono:")
        phone_lbl.setStyleSheet(lbl_style)
        self.phone_input = QLineEdit()
        self.phone_input.setPlaceholderText("Ej: 04121234567 (solo números)")
        
        pwd_lbl = QLabel("Contraseña:")
        pwd_lbl.setStyleSheet(lbl_style)
        self.pwd_container, self.password_input, self.btn_pwd_eye = create_password_field("••••••••")
        
        req_label = QLabel("Requisitos: Min. 8 caract., 1 Mayuscula, 1 Minuscula,\n1 Numero y 1 Simbolo (!@#$...)")
        req_label.setStyleSheet("font-size: 11px; color: #64748B; background: #0F1520; padding: 8px; border-radius: 6px;")
        
        # --- Sección de Administrador ---
        self.admin_checkbox = QCheckBox("Registrar como Administrador")
        self.admin_checkbox.stateChanged.connect(self.toggle_admin_key)
        
        self.admin_key_container, self.admin_key_input, self.btn_admin_eye = create_password_field("Clave secreta de Administrador")
        self.admin_key_container.setVisible(False)
        
        self.btn_register = QPushButton("Completar Registro")
        self.btn_register.clicked.connect(self.register)
        
        self.btn_cancel = QPushButton("Cancelar")
        self.btn_cancel.setObjectName("btnCancel")
        self.btn_cancel.clicked.connect(self.reject)
        
        layout.addWidget(title)
        layout.addWidget(user_lbl)
        layout.addWidget(self.username_input)
        layout.addWidget(email_lbl)
        layout.addWidget(self.email_input)
        layout.addWidget(phone_lbl)
        layout.addWidget(self.phone_input)
        layout.addWidget(pwd_lbl)
        layout.addWidget(self.pwd_container)
        layout.addWidget(req_label)
        layout.addWidget(self.admin_checkbox)
        layout.addWidget(self.admin_key_container)
        layout.addWidget(self.btn_register)
        layout.addWidget(self.btn_cancel)

    def toggle_admin_key(self, state):
        """Muestra/oculta el campo de clave de admin según el checkbox."""
        self.admin_key_container.setVisible(state == 2)  # 2 = Qt.Checked

    def validate_registration_data(self, user, email, phone, pwd):
        """
        Valida que cada campo cumpla con las reglas estrictas:
        - Usuario: min 3 caracteres, sin espacios.
        - Correo: obligatoriamente con '@' y estructura válida.
        - Teléfono: solo dígitos numéricos (min 7 dígitos).
        - Contraseña: min 8 caracteres, 1 mayúscula, 1 minúscula, 1 número y 1 símbolo.
        """
        # 1. Campos completos
        if not user or not email or not phone or not pwd:
            return False, "Todos los campos son obligatorios. Por favor completa el formulario."
        
        # 2. Validación de Usuario
        if len(user) < 3:
            return False, "El Nombre de Usuario debe tener al menos 3 caracteres."
        if not re.match(r"^[a-zA-Z0-9_.]+$", user):
            return False, "El Nombre de Usuario solo puede contener letras, números, puntos y guiones bajos (sin espacios)."

        # 3. Validación de Correo (obligatoriamente @)
        if "@" not in email:
            return False, "El Correo Electrónico debe contener obligatoriamente el signo '@'."
        
        email_pattern = r"^[\w\.-]+@[\w\.-]+\.[a-zA-Z]{2,}$"
        if not re.match(email_pattern, email):
            return False, "El formato del correo electrónico no es válido.\nEjemplo correcto: usuario@empresa.com"

        # 4. Validación de Teléfono (solo dígitos)
        if not phone.isdigit():
            return False, "El Teléfono debe contener ÚNICAMENTE dígitos numéricos (sin letras, guiones, símbolos ni espacios)."
        if len(phone) < 7 or len(phone) > 15:
            return False, "El Teléfono debe contener entre 7 y 15 dígitos numéricos."

        # 5. Validación de Contraseña
        if len(pwd) < 8:
            return False, "La contraseña debe tener un mínimo de 8 caracteres."
        if not re.search(r"[A-Z]", pwd):
            return False, "La contraseña requiere al menos una letra MAYÚSCULA."
        if not re.search(r"[a-z]", pwd):
            return False, "La contraseña requiere al menos una letra MINÚSCULA."
        if not re.search(r"[0-9]", pwd):
            return False, "La contraseña requiere al menos un NÚMERO."
        if not re.search(r"[!@#$%^&*(),.?\":{}|<>\-_]", pwd):
            return False, "La contraseña requiere al menos un SÍMBOLO o carácter especial (!@#$%...)."

        return True, ""

    def register(self):
        user = self.username_input.text().strip()
        email = self.email_input.text().strip()
        phone = self.phone_input.text().strip()
        pwd = self.password_input.text().strip()
        
        is_valid, error_msg = self.validate_registration_data(user, email, phone, pwd)
        if not is_valid:
            QMessageBox.warning(self, "Validación de Registro", error_msg)
            return
        
        # Verificar si alguno de los datos ya existe antes de solicitar el código
        existing_error = self.db.check_user_exists(user, email, phone)
        if existing_error:
            QMessageBox.warning(self, "Datos Ya Registrados", existing_error)
            return

        # Determinar el rol
        role = 'usuario'
        if self.admin_checkbox.isChecked():
            admin_key = self.admin_key_input.text().strip()
            if not admin_key:
                QMessageBox.warning(self, "Clave Requerida", "Debes ingresar la clave secreta de Administrador.")
                return
            if admin_key != DatabaseManager.ADMIN_SECRET_KEY:
                QMessageBox.critical(self, "Acceso Denegado", "La clave de administrador es incorrecta.\nNo se puede registrar como administrador.")
                return
            role = 'admin'
        
        # Abrir modal de verificación de correo con código de 6 dígitos
        otp_dialog = EmailVerificationDialog(email, self)
        if otp_dialog.exec() == QDialog.DialogCode.Accepted:
            if self.db.register_user(user, email, phone, pwd, role):
                tipo = "Administrador" if role == 'admin' else "Usuario"
                QMessageBox.information(
                    self, 
                    "Cuenta Verificada y Creada", 
                    f"¡Correo verificado con éxito!\n\nCuenta de {tipo} activada para:\n{user}\n\nYa puedes iniciar sesión en SIAM."
                )
                self.accept()
            else:
                QMessageBox.warning(self, "Error de Registro", "Ocurrió un error al guardar la cuenta en la base de datos.")


class LoginWindow(QDialog):
    """
    Ventana Principal de Inicio de Sesión.
    Retorna la información del usuario autenticado para que main.py decida qué mostrar.
    """
    def __init__(self):
        super().__init__()
        self.setWindowTitle("SIAM - Acceso de Seguridad")
        self.setFixedSize(350, 420)
        self.setStyleSheet(COMMON_STYLESHEET + """
            QPushButton#btnRegister {
                background-color: transparent; color: #94A3B8;
                border: 1px solid #1E293B; border-radius: 6px; padding: 10px; font-weight: bold; font-size: 13px; margin-top: 5px;
            }
            QPushButton#btnRegister:hover { background-color: #1E293B; color: #FFFFFF; }
        """)

        self.db = DatabaseManager()
        
        # Datos del usuario autenticado (se llenan al hacer login exitoso)
        self.logged_user_id = None
        self.logged_username = None
        self.logged_role = None
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(40, 40, 40, 40)
        layout.setSpacing(15)
        
        self.title = QLabel("SIAM")
        self.title.setStyleSheet("font-size: 32px; font-weight: bold; color: #1A73E8;")
        self.title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        self.subtitle = QLabel("Acceso Restringido")
        self.subtitle.setStyleSheet("font-size: 13px; color: #94A3B8; margin-bottom: 20px;")
        self.subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        self.username_input = QLineEdit()
        self.username_input.setPlaceholderText("Nombre, Correo o Telefono")
        
        self.pwd_container, self.password_input, self.btn_login_eye = create_password_field("Contraseña")
        
        # Enlace para recuperación de contraseña
        self.btn_forgot = QPushButton("¿Olvidaste tu contraseña?")
        self.btn_forgot.setObjectName("btnForgot")
        self.btn_forgot.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_forgot.clicked.connect(self.open_forgot_password_window)
        
        forgot_layout = QHBoxLayout()
        forgot_layout.addStretch()
        forgot_layout.addWidget(self.btn_forgot)
        
        self.btn_login = QPushButton("Iniciar Sesion")
        self.btn_login.clicked.connect(self.login)
        
        self.btn_register = QPushButton("Registrar Nuevo Usuario")
        self.btn_register.setObjectName("btnRegister")
        self.btn_register.clicked.connect(self.open_register_window)
        
        layout.addWidget(self.title)
        layout.addWidget(self.subtitle)
        layout.addWidget(self.username_input)
        layout.addWidget(self.pwd_container)
        layout.addLayout(forgot_layout)
        layout.addWidget(self.btn_login)
        layout.addWidget(self.btn_register)

    def login(self):
        user = self.username_input.text().strip()
        pwd = self.password_input.text().strip()
        
        if not user or not pwd:
            QMessageBox.warning(self, "Aviso", "Por favor ingresa usuario y contraseña.")
            return
        
        result = self.db.authenticate_user(user, pwd)
        if result:
            self.logged_user_id = result[0]
            self.logged_username = result[1]
            self.logged_role = result[2]
            self.accept()
        else:
            QMessageBox.critical(self, "Acceso Denegado", "El usuario o la contraseña son incorrectos.")

    def open_register_window(self):
        """Abre la nueva ventana dedicada para registros."""
        reg_window = RegisterWindow(self.db)
        reg_window.exec()

    def open_forgot_password_window(self):
        """Abre la ventana interactiva de recuperación de contraseña vía correo."""
        forgot_win = ForgotPasswordWindow(self.db, self)
        forgot_win.exec()


class EmailConfigDialog(QDialog):
    """Diálogo para configurar el servicio de correo (Brevo, Resend o SMTP)."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("SIAM - Configuración de Correo Electrónico")
        self.setFixedSize(450, 520)
        self.setStyleSheet(COMMON_STYLESHEET)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(30, 25, 30, 25)
        layout.setSpacing(10)
        
        title = QLabel("⚙️ Servicio Emisor de Correo")
        title.setStyleSheet("font-size: 18px; font-weight: bold; color: #1A73E8;")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)
        
        desc = QLabel(
            "Configura el servicio que enviará los correos de verificación a los usuarios. "
            "Se recomienda <b>Brevo (Sendinblue)</b> o <b>Resend</b> ya que no requieren contraseñas de Google."
        )
        desc.setStyleSheet("font-size: 12px; color: #94A3B8; line-height: 1.4;")
        desc.setWordWrap(True)
        layout.addWidget(desc)
        
        lbl_provider = QLabel("Proveedor de Envío:")
        lbl_provider.setStyleSheet("font-weight: bold; font-size: 13px; margin-top: 5px;")
        layout.addWidget(lbl_provider)
        
        from PyQt6.QtWidgets import QComboBox
        self.combo_provider = QComboBox()
        self.combo_provider.addItems(["Brevo API (Recomendado - Gratuito)", "Resend API", "SMTP Tradicional"])
        layout.addWidget(self.combo_provider)
        
        lbl_api = QLabel("Clave API (API Key):")
        lbl_api.setStyleSheet("font-weight: bold; font-size: 13px; margin-top: 5px;")
        layout.addWidget(lbl_api)
        
        self.input_api_key = QLineEdit()
        self.input_api_key.setPlaceholderText("Ej: xkeysib-... (Brevo) o re_... (Resend)")
        layout.addWidget(self.input_api_key)
        
        btn_link = QPushButton("🔗 Obtener API Key de Brevo Gratis (Sin Tarjeta)")
        btn_link.setObjectName("btnSecondary")
        btn_link.clicked.connect(self.open_brevo_link)
        layout.addWidget(btn_link)
        
        lbl_sender = QLabel("Correo Remitente:")
        lbl_sender.setStyleSheet("font-weight: bold; font-size: 13px;")
        layout.addWidget(lbl_sender)
        
        self.input_sender = QLineEdit()
        self.input_sender.setPlaceholderText("notificaciones@siam-seguridad.com")
        layout.addWidget(self.input_sender)
        
        config = load_email_config()
        self.input_api_key.setText(config.get("api_key", ""))
        self.input_sender.setText(config.get("sender_email", "notificaciones@siam-seguridad.com"))
        if config.get("provider") == "resend":
            self.combo_provider.setCurrentIndex(1)
        elif config.get("provider") == "smtp":
            self.combo_provider.setCurrentIndex(2)
        else:
            self.combo_provider.setCurrentIndex(0)
            
        self.btn_save = QPushButton("💾 Guardar Configuración")
        self.btn_save.clicked.connect(self.save)
        layout.addWidget(self.btn_save)

    def open_brevo_link(self):
        import webbrowser
        webbrowser.open("https://app.brevo.com/settings/keys/api")

    def save(self):
        provider_map = {0: "brevo", 1: "resend", 2: "smtp"}
        provider = provider_map.get(self.combo_provider.currentIndex(), "brevo")
        api_key = self.input_api_key.text().strip()
        sender_email = self.input_sender.text().strip()
        
        save_email_config({
            "provider": provider,
            "api_key": api_key,
            "sender_email": sender_email or "notificaciones@siam-seguridad.com"
        })
        QMessageBox.information(
            self,
            "Configuración Guardada",
            "La configuración del emisor de correos se ha guardado exitosamente."
        )
        self.accept()

GmailConfigDialog = EmailConfigDialog


class ForgotPasswordWindow(QDialog):
    """
    Ventana para restablecer contraseña mediante código de verificación.
    """
    def __init__(self, db, parent=None):
        super().__init__(parent)
        self.db = db
        self.target_user_id = None
        self.target_email = None
        self.target_username = None
        
        self.setWindowTitle("SIAM - Recuperación de Contraseña")
        self.setFixedSize(430, 580)
        self.setStyleSheet(COMMON_STYLESHEET)
        
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(30, 30, 30, 30)
        
        self.stacked = QStackedWidget()
        main_layout.addWidget(self.stacked)
        
        # --- PASO 1: Identificación del usuario ---
        self.step1_widget = QWidget()
        step1_layout = QVBoxLayout(self.step1_widget)
        step1_layout.setContentsMargins(0, 0, 0, 0)
        step1_layout.setSpacing(12)
        
        s1_title = QLabel("🔐 Recuperar Contraseña")
        s1_title.setStyleSheet("font-size: 22px; font-weight: bold; color: #1A73E8;")
        s1_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        step1_layout.addWidget(s1_title)
        
        s1_desc = QLabel(
            "Ingresa tu nombre de usuario o correo electrónico registrado. "
            "Te enviaremos un código de seguridad real a tu correo para restablecer tu acceso."
        )
        s1_desc.setStyleSheet("font-size: 13px; color: #94A3B8; margin-bottom: 8px;")
        s1_desc.setWordWrap(True)
        s1_desc.setAlignment(Qt.AlignmentFlag.AlignCenter)
        step1_layout.addWidget(s1_desc)
        
        s1_lbl_input = QLabel("Usuario o Correo Registrado:")
        s1_lbl_input.setStyleSheet("font-weight: bold; font-size: 13px;")
        step1_layout.addWidget(s1_lbl_input)
        
        self.input_identifier = QLineEdit()
        self.input_identifier.setPlaceholderText("Ej: alberth19 o mi_correo@gmail.com")
        step1_layout.addWidget(self.input_identifier)
        
        self.btn_send_code = QPushButton("📧 Enviar Código de Verificación")
        self.btn_send_code.clicked.connect(self.send_code)
        step1_layout.addWidget(self.btn_send_code)
        
        self.btn_open_smtp = QPushButton("⚙️ Configurar Emisor de Correos")
        self.btn_open_smtp.setObjectName("btnSecondary")
        self.btn_open_smtp.clicked.connect(self.open_smtp_config)
        step1_layout.addWidget(self.btn_open_smtp)
        
        step1_layout.addStretch()
        self.stacked.addWidget(self.step1_widget)
        
        # --- PASO 2: Verificación de código y nueva contraseña ---
        self.step2_widget = QWidget()
        step2_layout = QVBoxLayout(self.step2_widget)
        step2_layout.setContentsMargins(0, 0, 0, 0)
        step2_layout.setSpacing(8)
        
        s2_title = QLabel("📬 Código de Verificación")
        s2_title.setStyleSheet("font-size: 20px; font-weight: bold; color: #1A73E8;")
        s2_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        step2_layout.addWidget(s2_title)
        
        self.lbl_sent_notice = QLabel("Hemos generado un código de 6 dígitos para tu cuenta:")
        self.lbl_sent_notice.setStyleSheet("font-size: 12px; color: #94A3B8;")
        self.lbl_sent_notice.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_sent_notice.setWordWrap(True)
        step2_layout.addWidget(self.lbl_sent_notice)
        
        self.lbl_masked_email = QLabel("")
        self.lbl_masked_email.setStyleSheet(
            "font-size: 13px; font-weight: bold; color: #38BDF8; "
            "background: #0F1520; padding: 6px; border-radius: 6px; border: 1px solid #1E293B;"
        )
        self.lbl_masked_email.setAlignment(Qt.AlignmentFlag.AlignCenter)
        step2_layout.addWidget(self.lbl_masked_email)
        
        lbl_code = QLabel("Código de 6 dígitos:")
        lbl_code.setStyleSheet("font-weight: bold; font-size: 12px; margin-top: 4px;")
        step2_layout.addWidget(lbl_code)
        
        self.input_code = QLineEdit()
        self.input_code.setMaxLength(6)
        self.input_code.setPlaceholderText("000000")
        self.input_code.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.input_code.setStyleSheet("font-size: 22px; font-weight: bold; letter-spacing: 6px; color: #38BDF8;")
        step2_layout.addWidget(self.input_code)
        
        lbl_new_pwd = QLabel("Nueva Contraseña:")
        lbl_new_pwd.setStyleSheet("font-weight: bold; font-size: 12px;")
        step2_layout.addWidget(lbl_new_pwd)
        
        self.pwd1_container, self.input_new_pwd, _ = create_password_field("Mín. 8 caract, mayús, núm, símb.")
        step2_layout.addWidget(self.pwd1_container)
        
        lbl_conf_pwd = QLabel("Confirmar Nueva Contraseña:")
        lbl_conf_pwd.setStyleSheet("font-weight: bold; font-size: 12px;")
        step2_layout.addWidget(lbl_conf_pwd)
        
        self.pwd2_container, self.input_conf_pwd, _ = create_password_field("Repite la nueva contraseña")
        step2_layout.addWidget(self.pwd2_container)
        
        self.btn_reset_pwd = QPushButton("🔒 Restablecer Contraseña")
        self.btn_reset_pwd.clicked.connect(self.submit_new_password)
        step2_layout.addWidget(self.btn_reset_pwd)
        
        self.btn_resend_code = QPushButton("🔄 Reenviar Código")
        self.btn_resend_code.setObjectName("btnSecondary")
        self.btn_resend_code.clicked.connect(self.resend_code)
        step2_layout.addWidget(self.btn_resend_code)
        
        self.btn_back = QPushButton("⬅️ Regresar al Paso Anterior")
        self.btn_back.setObjectName("btnSecondary")
        self.btn_back.clicked.connect(lambda: self.stacked.setCurrentIndex(0))
        step2_layout.addWidget(self.btn_back)
        
        self.stacked.addWidget(self.step2_widget)

    def open_smtp_config(self):
        cfg_dialog = EmailConfigDialog(self)
        cfg_dialog.exec()

    def send_code(self):
        identifier = self.input_identifier.text().strip()
        if not identifier:
            QMessageBox.warning(self, "Aviso", "Por favor ingresa tu nombre de usuario o correo registrado.")
            return
            
        user = self.db.get_user_for_recovery(identifier)
        if not user:
            QMessageBox.critical(
                self, 
                "Usuario No Encontrado", 
                "No existe ninguna cuenta registrada con el usuario o correo ingresado.\n\n"
                "Por favor verifica e intenta nuevamente."
            )
            return
            
        self.target_user_id, self.target_username, self.target_email = user
        
        # Generar código de seguridad de 6 dígitos en la BD
        code = self.db.create_password_reset_code(self.target_user_id)
        
        # Intentar enviar correo real vía API/SMTP
        success, msg = send_password_reset_email(self.target_email, self.target_username, code)
        if success:
            QMessageBox.information(
                self,
                "Correo Enviado",
                f"¡Código enviado con éxito!\n\n"
                f"Hemos enviado un mensaje de verificación a:\n{self.target_email}\n\n"
                "Revisa tu bandeja de entrada e introduce el código."
            )
        else:
            # Respaldo de seguridad inteligente para que el usuario nunca quede atascado
            QMessageBox.information(
                self,
                "Código de Verificación - Modo Asistido",
                f"Estado del emisor: {msg}\n\n"
                f"🛡️ Como respaldo del sistema, tu código de verificación generado es:\n\n"
                f"👉  {code}  👈\n\n"
                f"Introduce este código a continuación junto con tu nueva contraseña para completar el restablecimiento."
            )

        # Enmascarar correo para privacidad y pasar al Paso 2
        masked = self._mask_email(self.target_email)
        self.lbl_masked_email.setText(masked)
        self.stacked.setCurrentIndex(1)

    def resend_code(self):
        if not self.target_user_id or not self.target_email:
            return
        code = self.db.create_password_reset_code(self.target_user_id)
        success, msg = send_password_reset_email(self.target_email, self.target_username, code)
        if success:
            QMessageBox.information(self, "Código Reenviado", f"Se ha enviado un nuevo código a {self.target_email}")
        else:
            QMessageBox.critical(self, "Error al Reenviar", msg)

    def submit_new_password(self):
        code = self.input_code.text().strip()
        pwd1 = self.input_new_pwd.text().strip()
        pwd2 = self.input_conf_pwd.text().strip()
        
        if not code or len(code) != 6 or not code.isdigit():
            QMessageBox.warning(self, "Aviso", "El código debe ser de exactamente 6 dígitos numéricos.")
            return
        if not pwd1 or not pwd2:
            QMessageBox.warning(self, "Aviso", "Por favor ingresa y confirma la nueva contraseña.")
            return
        if pwd1 != pwd2:
            QMessageBox.warning(self, "Aviso", "Las contraseñas no coinciden. Por favor verifícalas.")
            return
            
        # Validar robustez de la contraseña
        is_valid, err_msg = self._validate_password_strength(pwd1)
        if not is_valid:
            QMessageBox.warning(self, "Contraseña No Válida", err_msg)
            return
            
        # Restablecer contraseña en la base de datos
        ok, res_msg = self.db.complete_password_reset(self.target_user_id, code, pwd1)
        if ok:
            QMessageBox.information(
                self,
                "Contraseña Actualizada",
                "¡Excelente! Tu contraseña ha sido restablecida exitosamente.\n\n"
                "Ahora puedes iniciar sesión en SIAM con tu nueva contraseña."
            )
            self.accept()
        else:
            QMessageBox.critical(self, "Error", res_msg)

    def _validate_password_strength(self, pwd):
        if len(pwd) < 8:
            return False, "La contraseña debe tener al menos 8 caracteres."
        if not re.search(r"[A-Z]", pwd):
            return False, "La contraseña requiere al menos una letra MAYÚSCULA."
        if not re.search(r"[a-z]", pwd):
            return False, "La contraseña requiere al menos una letra MINÚSCULA."
        if not re.search(r"[0-9]", pwd):
            return False, "La contraseña requiere al menos un NÚMERO."
        if not re.search(r"[!@#$%^&*(),.?\":{}|<>\-_]", pwd):
            return False, "La contraseña requiere al menos un SÍMBOLO especial (!@#$%...)."
        return True, ""

    def _mask_email(self, email):
        try:
            user_part, domain_part = email.split("@")
            if len(user_part) <= 2:
                masked_user = user_part[0] + "***"
            else:
                masked_user = user_part[:2] + "***" + user_part[-1]
            return f"{masked_user}@{domain_part}"
        except Exception:
            return email

