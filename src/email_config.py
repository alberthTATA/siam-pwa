# -*- coding: utf-8 -*-
"""
Servicio y Configuración de Envío de Correos Electrónicos para SIAM.
Soporta:
1. API de Correo (Brevo / Resend) - No requiere contraseñas de Google ni configuración de puertos.
2. SMTP Directo (Gmail, Outlook, servidores personalizados).
3. Respaldo de seguridad local (muestra el código si la red o servicio fallan).
"""

import os
import json
import smtplib
import ssl
import urllib.request
import urllib.error
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

CONFIG_FILE_PATH = os.path.join(os.path.dirname(__file__), "email_credentials.json")

DEFAULT_CONFIG = {
    "provider": "brevo",            # "brevo", "resend" o "smtp"
    "api_key": "",                  # API key de Brevo (xkeysib-...) o Resend (re_...)
    "sender_email": "notificaciones@siam-seguridad.com",
    "sender_name": "SIAM Seguridad",
    "smtp_server": "smtp.gmail.com",
    "smtp_port": 587,
    "smtp_user": "",
    "smtp_password": "",
    "use_tls": True
}

def load_email_config():
    """Carga la configuración de correo guardada o los valores por defecto."""
    if os.path.exists(CONFIG_FILE_PATH):
        try:
            with open(CONFIG_FILE_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
                config = DEFAULT_CONFIG.copy()
                config.update(data)
                return config
        except Exception:
            return DEFAULT_CONFIG.copy()
    return DEFAULT_CONFIG.copy()

def save_email_config(config_dict):
    """Guarda la configuración del servicio de correo."""
    current = load_email_config()
    current.update(config_dict)
    with open(CONFIG_FILE_PATH, "w", encoding="utf-8") as f:
        json.dump(current, f, indent=4)
    return current

def build_email_html(username, reset_code):
    """Genera el contenido HTML del correo con la identidad visual corporativa de SIAM."""
    return f"""
    <!DOCTYPE html>
    <html lang="es">
    <head>
        <meta charset="UTF-8">
        <style>
            body {{
                font-family: 'Segoe UI', Arial, sans-serif;
                background-color: #0B0E14;
                color: #E0E6ED;
                margin: 0;
                padding: 25px;
            }}
            .card {{
                max-width: 520px;
                margin: 0 auto;
                background-color: #0F1520;
                border: 1px solid #1E293B;
                border-radius: 12px;
                padding: 30px;
            }}
            .logo {{
                font-size: 28px;
                font-weight: bold;
                color: #1A73E8;
                text-align: center;
                margin-bottom: 5px;
                letter-spacing: 2px;
            }}
            .subtitle {{
                font-size: 13px;
                color: #94A3B8;
                text-align: center;
                margin-bottom: 25px;
            }}
            .code-box {{
                background-color: #1E293B;
                border: 2px dashed #1A73E8;
                border-radius: 8px;
                padding: 16px;
                text-align: center;
                margin: 25px 0;
            }}
            .code {{
                font-size: 36px;
                font-weight: bold;
                letter-spacing: 8px;
                color: #38BDF8;
                font-family: 'Consolas', 'Courier New', monospace;
            }}
            .footer {{
                font-size: 12px;
                color: #64748B;
                text-align: center;
                margin-top: 25px;
                border-top: 1px solid #1E293B;
                padding-top: 15px;
            }}
        </style>
    </head>
    <body>
        <div class="card">
            <div class="logo">SIAM</div>
            <div class="subtitle">Sistema Inteligente de Aseguramiento de Materiales</div>
            <p>Hola <strong>{username}</strong>,</p>
            <p>Recibimos una solicitud para restablecer la contraseña de tu cuenta registrada en SIAM.</p>
            <p>Tu código de seguridad de 6 dígitos es:</p>
            
            <div class="code-box">
                <div class="code">{reset_code}</div>
            </div>
            
            <p style="font-size: 13px; color: #94A3B8;">
                ⏱️ Este código es válido durante <strong>15 minutos</strong>.
            </p>
            <p style="font-size: 12px; color: #64748B;">
                Si tú no solicitaste este cambio, puedes ignorar este mensaje de forma segura.
            </p>
            
            <div class="footer">
                Mensaje de verificación automático generado por SIAM.
            </div>
        </div>
    </body>
    </html>
    """

def send_via_brevo(api_key, sender_email, sender_name, recipient_email, username, reset_code):
    """Envía el correo usando la API REST de Brevo (Sendinblue)."""
    url = "https://api.brevo.com/v3/smtp/email"
    html_content = build_email_html(username, reset_code)
    
    payload = {
        "sender": {"name": sender_name or "SIAM Seguridad", "email": sender_email or "notificaciones@siam-seguridad.com"},
        "to": [{"email": recipient_email, "name": username}],
        "subject": "SIAM - Código de Recuperación de Contraseña",
        "htmlContent": html_content
    }
    
    headers = {
        "api-key": api_key.strip(),
        "Content-Type": "application/json",
        "Accept": "application/json",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
    }
    
    req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"), headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=12) as response:
            if response.status in (200, 201):
                return True, f"Correo enviado exitosamente a {recipient_email} vía Brevo"
            return False, f"Respuesta de Brevo: {response.status}"
    except urllib.error.HTTPError as e:
        error_body = e.read().decode("utf-8", errors="ignore")
        return False, f"Error HTTP {e.code} de Brevo: {error_body}"
    except Exception as e:
        return False, f"Error de conexión con Brevo: {str(e)}"

def send_via_resend(api_key, sender_email, recipient_email, username, reset_code):
    """Envía el correo usando la API REST de Resend."""
    url = "https://api.resend.com/emails"
    html_content = build_email_html(username, reset_code)
    
    # En cuentas gratuitas de Resend sin dominio propio verificado,
    # el remitente obligatorio es onboarding@resend.dev
    from_address = "SIAM Seguridad <onboarding@resend.dev>"
    if sender_email and "resend.dev" in sender_email:
        from_address = sender_email
        
    payload = {
        "from": from_address,
        "to": [recipient_email],
        "subject": "SIAM - Código de Recuperación de Contraseña",
        "html": html_content
    }
    
    headers = {
        "Authorization": f"Bearer {api_key.strip()}",
        "Content-Type": "application/json",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
    }
    
    req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"), headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=12) as response:
            if response.status in (200, 201):
                return True, f"Correo enviado exitosamente a {recipient_email} vía Resend"
            return False, f"Respuesta de Resend: {response.status}"
    except urllib.error.HTTPError as e:
        error_body = e.read().decode("utf-8", errors="ignore")
        return False, f"Error HTTP {e.code} de Resend: {error_body}"
    except Exception as e:
        return False, f"Error de conexión con Resend: {str(e)}"

def send_via_smtp(config, recipient_email, username, reset_code):
    """Envía el correo mediante servidor SMTP tradicional."""
    smtp_server = config.get("smtp_server", "smtp.gmail.com")
    smtp_port = config.get("smtp_port", 587)
    sender_email = config.get("sender_email") or config.get("smtp_user", "")
    sender_password = config.get("sender_password") or config.get("smtp_password", "")
    
    if not sender_email or not sender_password:
        return False, "Faltan credenciales SMTP (usuario y contraseña)."

    msg = MIMEMultipart("alternative")
    msg["Subject"] = "SIAM - Código de Recuperación de Contraseña"
    msg["From"] = f"SIAM Sistema <{sender_email}>"
    msg["To"] = recipient_email

    text_content = f"Hola {username},\n\nTu código de recuperación de SIAM es: {reset_code}\nVálido por 15 minutos."
    html_content = build_email_html(username, reset_code)

    msg.attach(MIMEText(text_content, "plain", "utf-8"))
    msg.attach(MIMEText(html_content, "html", "utf-8"))

    context = ssl.create_default_context()
    try:
        try:
            server = smtplib.SMTP_SSL(smtp_server, 465, context=context, timeout=12)
        except Exception:
            server = smtplib.SMTP(smtp_server, smtp_port, timeout=12)
            server.ehlo()
            server.starttls(context=context)
            server.ehlo()

        server.login(sender_email, sender_password)
        server.send_message(msg)
        server.quit()
        return True, f"Correo enviado exitosamente a {recipient_email}"
    except Exception as e:
        return False, f"Error SMTP: {str(e)}"

def send_password_reset_email(recipient_email, username, reset_code):
    """
    Función principal para enviar el correo de recuperación.
    Evalúa el proveedor configurado (Brevo, Resend o SMTP).
    """
    config = load_email_config()
    provider = config.get("provider", "brevo")
    api_key = config.get("api_key", "").strip()

    # Si hay API key de Brevo configurada
    if provider == "brevo" and api_key:
        return send_via_brevo(
            api_key,
            config.get("sender_email"),
            config.get("sender_name"),
            recipient_email,
            username,
            reset_code
        )
    # Si hay API key de Resend configurada
    elif provider == "resend" and api_key:
        return send_via_resend(
            api_key,
            config.get("sender_email"),
            recipient_email,
            username,
            reset_code
        )
    # Si está configurado SMTP
    elif provider == "smtp" and (config.get("sender_email") or config.get("smtp_user")):
        return send_via_smtp(config, recipient_email, username, reset_code)

    # Si aún no se ha configurado ninguna clave o proveedor
    return False, (
        "No se ha configurado aún un servicio de correo en el sistema.\n"
        "Puedes configurar tu clave gratuita de Brevo o Resend para envíos automáticos."
    )
