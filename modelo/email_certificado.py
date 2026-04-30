import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders

# Seguridad: nunca exponer credenciales en codigo fuente.
# Configure estas variables en su entorno local/servidor.
ENV_SMTP_HOST = "SMTP_HOST"
ENV_SMTP_PORT = "SMTP_PORT"
ENV_SMTP_USER = "SMTP_USER"
ENV_SMTP_PASSWORD = "SMTP_PASSWORD"
ENV_MAIL_FROM = "MAIL_FROM"


def _required_env(var_name: str) -> str:
    value = (os.environ.get(var_name) or "").strip()
    if not value:
        raise RuntimeError(f"Falta variable de entorno obligatoria: {var_name}")
    return value


def _smtp_settings():
    host = _required_env(ENV_SMTP_HOST)
    port = int(os.environ.get(ENV_SMTP_PORT, "587"))
    user = _required_env(ENV_SMTP_USER)
    password = _required_env(ENV_SMTP_PASSWORD)
    use_tls = True
    mail_from = _required_env(ENV_MAIL_FROM)
    return host, port, user, password, use_tls, mail_from


def correo_habilitado():
    if os.environ.get("MAIL_ENABLED", "true").lower() in ("0", "false", "no", "n"):
        return False
    try:
        _smtp_settings()
        return True
    except Exception:
        return False


def enviar_correo_certificado_asignado(
    destinatario: str,
    nombre_estudiante: str,
    cert_id: str,
    curso: str,
    tipo_credencial: str,
    url_descarga_pdf: str,
    remitente_preferido: str = "",
    pdf_bytes: bytes = None,
    pdf_filename: str = "certificado.pdf",
) -> bool:
    """
    Envía aviso de certificado asignado con enlace directo de descarga (token)
    y opcionalmente adjunta el archivo PDF.
    Usa SIEMPRE la cuenta unica configurada por variables SMTP_* y MAIL_FROM.
    """
    try:
        host, port, user, password, use_tls, mail_from = _smtp_settings()
    except Exception as e:
        print(f"Correo no enviado: {e}")
        return False
    if not destinatario:
        return False

    from_header = mail_from

    subject = f"Certificado asignado: {tipo_credencial}"
    text_body = (
        f"Hola {nombre_estudiante},\n\n"
        f"Se le ha asignado un certificado en el sistema.\n\n"
        f"Identificador: {cert_id}\n"
        f"Curso / programa: {curso}\n"
        f"Tipo: {tipo_credencial}\n\n"
        f"Se adjunta el certificado en formato PDF para su comodidad.\n\n"
        f"También puede descargarlo usando este enlace temporal:\n{url_descarga_pdf}\n\n"
        f"Si el enlace vence, puede iniciar sesión en el portal del alumno y descargarlo desde allí.\n"
    )
    html_body = f"""\
<html>
<body>
<p>Hola <strong>{nombre_estudiante}</strong>,</p>
<p>Se le ha asignado un certificado en el sistema.</p>
<p>Se adjunta el certificado en formato PDF a este correo.</p>
<ul>
<li><strong>Identificador:</strong> {cert_id}</li>
<li><strong>Curso / programa:</strong> {curso}</li>
<li><strong>Tipo:</strong> {tipo_credencial}</li>
</ul>
<p><a href="{url_descarga_pdf}">Descargar certificado (Enlace alternativo)</a></p>
<p><small>Si el enlace vence, inicie sesión en el portal del alumno para descargarlo.</small></p>
</body>
</html>
"""

    msg = MIMEMultipart()
    msg["Subject"] = subject
    msg["From"] = from_header
    msg["To"] = destinatario

    # Cuerpo del mensaje (texto y HTML)
    msg_alt = MIMEMultipart("alternative")
    msg_alt.attach(MIMEText(text_body, "plain", "utf-8"))
    msg_alt.attach(MIMEText(html_body, "html", "utf-8"))
    msg.attach(msg_alt)

    # Adjuntar PDF si se proporcionan los bytes
    if pdf_bytes:
        part = MIMEBase("application", "octet-stream")
        part.set_payload(pdf_bytes)
        encoders.encode_base64(part)
        part.add_header(
            "Content-Disposition",
            f"attachment; filename={pdf_filename}",
        )
        msg.attach(part)

    try:
        with smtplib.SMTP(host, port, timeout=30) as server:
            if use_tls:
                server.starttls()
            server.login(user, password)
            server.sendmail(mail_from, [destinatario], msg.as_string())
        return True
    except Exception as e:
        print(f"Error SMTP enviando correo a {destinatario}: {e}")
        return False


def enviar_correo_credenciales_registro(
    destinatario: str,
    username: str,
    password: str,
    rol: str = "student",
    portal_url: str = "",
) -> bool:
    """
    Envía las credenciales iniciales al correo registrado.
    Nota: se envía la contraseña en texto plano por requerimiento funcional.
    """
    try:
        host, port, user, password_smtp, use_tls, mail_from = _smtp_settings()
    except Exception as e:
        print(f"Correo de credenciales no enviado: {e}")
        return False

    destinatario = (destinatario or "").strip()
    username = (username or "").strip()
    if not destinatario or not username or not password:
        return False

    rol_label = "Administrador" if (rol or "").strip().lower() == "admin" else "Alumno"
    access_url = portal_url.strip() or "http://127.0.0.1:5000/"

    subject = "Credenciales de acceso — Sistema de Certificados"
    text_body = (
        f"Hola,\n\n"
        f"Se creó su cuenta en el Sistema de Certificados.\n\n"
        f"Rol: {rol_label}\n"
        f"Usuario: {username}\n"
        f"Contraseña: {password}\n\n"
        f"Ingreso: {access_url}\n\n"
        f"Recomendación: cambie su contraseña después del primer ingreso.\n"
    )
    html_body = f"""\
<html>
<body>
<p>Hola,</p>
<p>Se creó su cuenta en el <strong>Sistema de Certificados</strong>.</p>
<ul>
<li><strong>Rol:</strong> {rol_label}</li>
<li><strong>Usuario:</strong> {username}</li>
<li><strong>Contraseña:</strong> {password}</li>
</ul>
<p><a href="{access_url}">Ingresar al sistema</a></p>
<p><small>Recomendación: cambie su contraseña después del primer ingreso.</small></p>
</body>
</html>
"""

    msg = MIMEMultipart()
    msg["Subject"] = subject
    msg["From"] = mail_from
    msg["To"] = destinatario

    msg_alt = MIMEMultipart("alternative")
    msg_alt.attach(MIMEText(text_body, "plain", "utf-8"))
    msg_alt.attach(MIMEText(html_body, "html", "utf-8"))
    msg.attach(msg_alt)

    try:
        with smtplib.SMTP(host, port, timeout=30) as server:
            if use_tls:
                server.starttls()
            server.login(user, password_smtp)
            server.sendmail(mail_from, [destinatario], msg.as_string())
        return True
    except Exception as e:
        print(f"Error SMTP enviando credenciales a {destinatario}: {e}")
        return False
