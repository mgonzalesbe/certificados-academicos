import os
import time
import json
import base64
import uuid
import re
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.serialization import (
    Encoding,
    NoEncryption,
    PrivateFormat,
    load_pem_private_key,
)

from modelo.database import (
    get_db_connection,
    get_app_stats,
    save_app_stats,
    obtener_id_tipo_credencial_por_nombre,
    registrar_auditoria_certificado,
)
from modelo import auth_usuarios
from modelo.pdf_diploma import generar_pdf_diploma_bytes

_KEY_PATH = os.path.join(os.path.dirname(__file__), "issuer_private_key.pem")
_MAX_FIELD_LEN = 100

TIPOS_CREDENCIAL = (
    "Constancia de Asistencia",
    "Certificado de Participación",
    "Certificado de Aprobación",
    "Diploma de Extensión Universitaria",
)


def _load_or_create_private_key():
    """
    Orden de carga (importante en Render: el disco del contenedor es efímero).

    1) ISSUER_PRIVATE_KEY_B64 — PEM PKCS8 en Base64 (recomendado en Render).
    2) ISSUER_PRIVATE_KEY_PEM — PEM completo; use \\n en .env si va en una sola línea.
    3) Archivo modelo/issuer_private_key.pem (desarrollo local).
    4) Generar clave nueva; si el disco no es escribible, solo queda en memoria (malo en producción).
    """
    pem_b64 = (os.environ.get("ISSUER_PRIVATE_KEY_B64") or "").strip()
    if pem_b64:
        try:
            pem = base64.b64decode(pem_b64)
            return load_pem_private_key(pem, password=None)
        except Exception as e:
            raise RuntimeError(
                "ISSUER_PRIVATE_KEY_B64 no es un PEM válido en Base64. "
                "Genérelo leyendo modelo/issuer_private_key.pem y codificando todo el PEM en Base64."
            ) from e

    pem_env = (os.environ.get("ISSUER_PRIVATE_KEY_PEM") or "").strip()
    if pem_env:
        try:
            pem = pem_env.replace("\\n", "\n").encode("utf-8")
            return load_pem_private_key(pem, password=None)
        except Exception as e:
            raise RuntimeError("ISSUER_PRIVATE_KEY_PEM no es un PEM válido.") from e

    if os.path.isfile(_KEY_PATH):
        with open(_KEY_PATH, "rb") as f:
            return load_pem_private_key(f.read(), password=None)

    private_key = ec.generate_private_key(ec.SECP256R1())
    pem = private_key.private_bytes(Encoding.PEM, PrivateFormat.PKCS8, NoEncryption())
    try:
        with open(_KEY_PATH, "wb") as f:
            f.write(pem)
        print("Clave emisora generada y guardada en issuer_private_key.pem")
    except OSError as e:
        print(
            "ADVERTENCIA CRÍTICA: no se pudo escribir issuer_private_key.pem (disco no persistente). "
            "En Render defina ISSUER_PRIVATE_KEY_B64 con el PEM en Base64; si no, al reiniciar el servicio "
            "cambiará la clave y los certificados antiguos dejarán de validar. "
            f"Detalle: {e}"
        )
    return private_key


private_key = _load_or_create_private_key()
public_key = private_key.public_key()


def signed_message(cert_id, name, course, issue_date, cert_type):
    t = cert_type if cert_type is not None else ""
    return f"{cert_id}|{name}|{course}|{issue_date}|{t}"


def sign_data(data_string):
    data_bytes = data_string.encode('utf-8')
    signature = private_key.sign(
        data_bytes,
        ec.ECDSA(hashes.SHA256())
    )
    return base64.b64encode(signature).decode('utf-8')


def verify_signature(data_string, signature_b64):
    try:
        data_bytes = data_string.encode('utf-8')
        sig = (signature_b64 or "").strip().replace(" ", "+").replace("\n", "").replace("\r", "")
        if not sig:
            return False
        # Reponer padding faltante si el lector QR lo recorta.
        sig += "=" * ((4 - (len(sig) % 4)) % 4)
        signature_bytes = base64.b64decode(sig)
        public_key.verify(
            signature_bytes,
            data_bytes,
            ec.ECDSA(hashes.SHA256())
        )
        return True
    except Exception:
        return False


def _parse_qr_payload(qr_payload_str):
    """
    Acepta payload QR en JSON limpio o con ruido (saltos, prefijos/sufijos).
    Devuelve (cert_id, signature) o (None, None).
    """
    raw = (qr_payload_str or "").strip().replace("\ufeff", "")
    if not raw:
        return None, None

    obj = None
    try:
        obj = json.loads(raw)
    except Exception:
        # Intentar extraer el bloque JSON desde texto más largo.
        m = re.search(r"\{.*\}", raw, flags=re.DOTALL)
        if m:
            try:
                obj = json.loads(m.group(0))
            except Exception:
                obj = None

    if isinstance(obj, dict):
        cert_id = str(obj.get("id") or "").strip()
        signature = str(obj.get("signature") or "").strip()
        return cert_id or None, signature or None

    return None, None


def validar_datos_generacion(datos):
    if not isinstance(datos, dict):
        raise ValueError("El cuerpo debe ser un objeto JSON")
    for key in ("name", "date"):
        if key not in datos:
            raise ValueError(f"Falta el campo obligatorio: {key}")
        val = datos[key]
        if val is None or not str(val).strip():
            raise ValueError(f"El campo «{key}» no puede estar vacío")
        if len(str(val).strip()) > _MAX_FIELD_LEN:
            raise ValueError(f"El campo «{key}» no puede superar {_MAX_FIELD_LEN} caracteres")

    # Curso (por IdCurso) o texto libre (fallback)
    if datos.get("course_id") in (None, ""):
        curso_txt = str(datos.get("course") or "").strip()
        if not curso_txt:
            raise ValueError("Debe indicar el curso (o enviar «course_id»)")
        if len(curso_txt) > 200:
            raise ValueError("El curso no puede superar 200 caracteres")
    else:
        try:
            ic = int(datos.get("course_id"))
            if ic < 1:
                raise ValueError()
        except Exception:
            raise ValueError("«course_id» debe ser un entero positivo") from None

    # Tipo de credencial (por IdTipoCredencial) o por nombre (fallback)
    if datos.get("type_id") in (None, ""):
        tipo_txt = str(datos.get("type") or "").strip()
        if not tipo_txt:
            raise ValueError("Debe indicar el tipo de credencial (o enviar «type_id»)")
    else:
        try:
            it = int(datos.get("type_id"))
            if it < 1:
                raise ValueError()
        except Exception:
            raise ValueError("«type_id» debe ser un entero positivo") from None

    bt = datos.get("body_text")
    if bt is not None and len(str(bt)) > 4000:
        raise ValueError("El texto del diploma no puede superar 4000 caracteres")

    if datos.get("body_text_catalog_id") not in (None, ""):
        try:
            icat = int(datos.get("body_text_catalog_id"))
            if icat < 1:
                raise ValueError()
        except Exception:
            raise ValueError("«body_text_catalog_id» debe ser un entero positivo") from None
        conn = get_db_connection()
        if not conn:
            raise RuntimeError("Base de datos no disponible")
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT 1 FROM TextosCuerpoCertificado
                WHERE IdTextoCuerpo = ? AND Activo = 1
                """,
                (icat,),
            )
            if cursor.fetchone() is None:
                raise ValueError("Texto guardado no válido o inactivo")
        finally:
            conn.close()

    if datos.get("include_months"):
        try:
            m = int(datos.get("months") or 0)
            if m < 1 or m > 600:
                raise ValueError()
        except Exception:
            raise ValueError("Si indica meses de formación, debe ser un número entre 1 y 600") from None

    # Validación de existencia en BD (si se envían IDs)
    if datos.get("course_id") not in (None, ""):
        conn = get_db_connection()
        if not conn:
            raise RuntimeError("Base de datos no disponible")
        try:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT 1 FROM Cursos WHERE IdCurso = ? AND Activo = 1",
                (int(datos["course_id"]),),
            )
            if cursor.fetchone() is None:
                raise ValueError("Curso no válido o inactivo")
        finally:
            conn.close()
    if datos.get("type_id") not in (None, ""):
        conn = get_db_connection()
        if not conn:
            raise RuntimeError("Base de datos no disponible")
        try:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT 1 FROM TiposCredencial WHERE IdTipoCredencial = ? AND Activo = 1",
                (int(datos["type_id"]),),
            )
            if cursor.fetchone() is None:
                raise ValueError("Tipo de credencial no válido o inactivo")
        finally:
            conn.close()

    if datos.get("centro_educativo_id") in (None, ""):
        raise ValueError("Debe indicar el centro educativo (centro_educativo_id)")
    try:
        id_ce = int(datos.get("centro_educativo_id"))
        if id_ce < 1:
            raise ValueError()
    except Exception:
        raise ValueError("«centro_educativo_id» debe ser un entero positivo") from None
    conn = get_db_connection()
    if not conn:
        raise RuntimeError("Base de datos no disponible")
    try:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT 1 FROM CentroEducativo WHERE IdCentroEducativo = ? AND Estado = N'Activo'",
            (id_ce,),
        )
        if cursor.fetchone() is None:
            raise ValueError("Centro educativo no válido o inactivo")
    finally:
        conn.close()

    if datos.get("firma_doctor_id") in (None, ""):
        raise ValueError("Debe indicar la firma del director (firma_doctor_id)")
    try:
        id_fd = int(datos.get("firma_doctor_id"))
        if id_fd < 1:
            raise ValueError()
    except Exception:
        raise ValueError("«firma_doctor_id» debe ser un entero positivo") from None
    conn = get_db_connection()
    if not conn:
        raise RuntimeError("Base de datos no disponible")
    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT 1 FROM FirmaDoctores
            WHERE IdFirmaDoctores = ? AND Estado = N'Activo'
            """,
            (id_fd,),
        )
        if cursor.fetchone() is None:
            raise ValueError("Firma de director no válida o inactiva")
    finally:
        conn.close()


stats_tesis = {
    'totalGenTime': 0.0, 'genCount': 0,
    'totalVerTime': 0.0, 'verCount': 0,
    'validCount': 0, 'invalidCount': 0
}


def init_stats_from_db():
    data = get_app_stats()
    if not data:
        return
    stats_tesis['totalGenTime'] = data['totalGenTime']
    stats_tesis['genCount'] = data['genCount']
    stats_tesis['totalVerTime'] = data['totalVerTime']
    stats_tesis['verCount'] = data['verCount']
    stats_tesis['validCount'] = data['validCount']
    stats_tesis['invalidCount'] = data['invalidCount']


def _persist_stats():
    try:
        save_app_stats(stats_tesis)
    except Exception:
        pass


def _intentar_enviar_correo_certificado_asignado(
    recipient_user_id,
    cert_id,
    nombre_en_certificado,
    curso,
    tipo_credencial,
    created_by_user_id=None,
    pdf_bytes=None,
):
    """Si hay SMTP configurado, avisa al estudiante con enlace de descarga directa y adjunto."""
    from urllib.parse import quote

    from modelo.email_certificado import correo_habilitado, enviar_correo_certificado_asignado
    from modelo.pdf_download_token import crear_token_descarga_pdf

    if not correo_habilitado():
        print("DEBUG: Correo no habilitado (MAIL_ENABLED=false o faltan variables SMTP)")
        return False
    u = auth_usuarios.obtener_usuario_por_id(recipient_user_id)
    if not u:
        print(f"DEBUG: No se encontró usuario con ID {recipient_user_id}")
        return False
    if not u.get("email"):
        print(f"DEBUG: El usuario {recipient_user_id} no tiene correo registrado")
        return False
    nombre = (
        f"{u.get('nombres') or ''} {u.get('apellidos') or ''}".strip() or nombre_en_certificado
    )
    print(f"DEBUG: Intentando enviar correo a {u['email']} para certificado {cert_id}")
    base = (os.environ.get("PUBLIC_APP_URL") or "http://127.0.0.1:5000").rstrip("/")
    token = crear_token_descarga_pdf(cert_id, int(recipient_user_id))
    url = f"{base}/api/certificates/{cert_id}/pdf/by-token?token={quote(token, safe='')}"
    remitente_preferido = ""
    if created_by_user_id:
        admin = auth_usuarios.obtener_usuario_por_id(created_by_user_id)
        if admin and admin.get("email"):
            remitente_preferido = str(admin["email"]).strip().lower()

    exito = enviar_correo_certificado_asignado(
        u["email"],
        nombre,
        cert_id,
        curso,
        tipo_credencial,
        url,
        remitente_preferido=remitente_preferido,
        pdf_bytes=pdf_bytes,
        pdf_filename=f"Certificado_{cert_id.replace('UCV-', '')}.pdf",
    )
    if exito:
        print(f"DEBUG: Correo enviado exitosamente a {u['email']}")
    else:
        print(f"DEBUG: Falló el envío de correo a {u['email']}")
    return exito


def crear_certificado(datos_estudiante, created_by_user_id=None):
    start_time = time.perf_counter()

    incluir_meses = bool(datos_estudiante.get("include_months"))
    training_months_db = None
    meses_pdf = None
    if incluir_meses:
        meses_pdf = int(datos_estudiante.get("months") or 0)
        training_months_db = meses_pdf

    body_text = datos_estudiante.get("body_text")
    if body_text is not None:
        body_text = str(body_text).strip() or None

    id_texto_cuerpo_catalogo = None
    raw_cat = datos_estudiante.get("body_text_catalog_id")
    if raw_cat not in (None, ""):
        try:
            id_texto_cuerpo_catalogo = int(raw_cat)
        except (TypeError, ValueError):
            id_texto_cuerpo_catalogo = None

    recipient_id = int(datos_estudiante.get("recipient_user_id")) if datos_estudiante.get("recipient_user_id") else None
    created_by = int(created_by_user_id) if created_by_user_id else None
    id_curso = int(datos_estudiante["course_id"]) if datos_estudiante.get("course_id") not in (None, "") else None
    id_tipo_credencial = int(datos_estudiante["type_id"]) if datos_estudiante.get("type_id") not in (None, "") else None
    id_centro_educativo = int(datos_estudiante["centro_educativo_id"])
    id_firma_doctores = int(datos_estudiante["firma_doctor_id"])

    # Resolver nombres finales (para PDF/firma) desde BD si hay IDs
    curso_nombre = (datos_estudiante.get("course") or "").strip() or None
    tipo_nombre = (datos_estudiante.get("type") or "").strip() or None
    logo_derecho_bytes = None
    doctor_firma_bytes = None
    doctor_nombres = None
    doctor_genero = None
    conn = get_db_connection()
    if not conn:
        raise RuntimeError("No se pudo conectar a la base de datos para resolver catálogos")
    try:
        cursor = conn.cursor()
        if id_curso is not None:
            cursor.execute("SELECT Nombre FROM Cursos WHERE IdCurso = ? AND Activo = 1", (id_curso,))
            r = cursor.fetchone()
            if not r:
                raise ValueError("Curso no válido o inactivo")
            curso_nombre = str(r.Nombre)
        if id_tipo_credencial is not None:
            cursor.execute(
                "SELECT Nombre FROM TiposCredencial WHERE IdTipoCredencial = ? AND Activo = 1",
                (id_tipo_credencial,),
            )
            r = cursor.fetchone()
            if not r:
                raise ValueError("Tipo de credencial no válido o inactivo")
            tipo_nombre = str(r.Nombre)
        cursor.execute(
            """
            SELECT Nombre, LogoDerecho FROM CentroEducativo
            WHERE IdCentroEducativo = ? AND Estado = N'Activo'
            """,
            (id_centro_educativo,),
        )
        cr = cursor.fetchone()
        if not cr:
            raise ValueError("Centro educativo no válido o inactivo")
        raw_ld = getattr(cr, "LogoDerecho", None)
        if raw_ld is not None:
            logo_derecho_bytes = bytes(raw_ld) if not isinstance(raw_ld, (bytes, bytearray)) else bytes(raw_ld)
            if len(logo_derecho_bytes) == 0:
                logo_derecho_bytes = None
        cursor.execute(
            """
            SELECT Firma, Nombres, Genero FROM FirmaDoctores
            WHERE IdFirmaDoctores = ? AND Estado = N'Activo'
            """,
            (id_firma_doctores,),
        )
        dr = cursor.fetchone()
        if not dr:
            raise ValueError("Firma de director no válida o inactiva")
        doctor_nombres = str(dr.Nombres or "").strip()
        doctor_genero = str(dr.Genero or "").strip()
        raw_f = getattr(dr, "Firma", None)
        if raw_f is not None:
            doctor_firma_bytes = bytes(raw_f) if not isinstance(raw_f, (bytes, bytearray)) else bytes(raw_f)
            if len(doctor_firma_bytes) == 0:
                doctor_firma_bytes = None
    finally:
        conn.close()

    if not curso_nombre:
        raise ValueError("Debe indicar el curso")
    if not tipo_nombre:
        raise ValueError("Debe indicar el tipo de credencial")

    if id_tipo_credencial is None:
        # fallback: resolver por nombre si existen semillas
        id_tipo_credencial = obtener_id_tipo_credencial_por_nombre(tipo_nombre)

    cert_id = f"UCV-{uuid.uuid4()}"
    raw_data = signed_message(
        cert_id,
        datos_estudiante['name'],
        curso_nombre,
        datos_estudiante['date'],
        tipo_nombre,
    )

    signature = sign_data(raw_data)
    qr_payload = json.dumps({"id": cert_id, "signature": signature})

    pdf_bytes = None
    pdf_error = None
    try:
        pdf_bytes = generar_pdf_diploma_bytes(
            cert_id=cert_id,
            nombre=datos_estudiante['name'],
            curso=curso_nombre,
            fecha_emision=datos_estudiante['date'],
            tipo_credencial=tipo_nombre,
            qr_payload=qr_payload,
            texto_cuerpo=body_text,
            incluir_meses=incluir_meses,
            meses=meses_pdf,
            logo_centro_bytes=None,
            logo_derecho_bytes=logo_derecho_bytes,
            doctor_firma_bytes=doctor_firma_bytes,
            doctor_nombres=doctor_nombres,
            doctor_genero=doctor_genero,
        )
    except Exception as e:
        pdf_error = str(e)
        print(f"ADVERTENCIA: Error generando PDF: {e}")

    # Calcular TGC antes de guardar en la BD para que el valor esté disponible
    end_time = time.perf_counter()
    tgc = end_time - start_time

    conn = get_db_connection()
    if not conn:
        raise RuntimeError("No se pudo conectar a la base de datos para guardar el certificado")
    try:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO Certificados (
                IdCertificado, NombreEstudiante, IdCurso, FechaEmision,
                IdTipoCredencial, FirmaDigital, Estado, ContenidoPdf,
                IdUsuarioDestinatario, IdUsuarioCreador, MesesFormacion, TextoCuerpo,
                TiempoGeneracionSeg, IdCentroEducativo, IdFirmaDoctores, IdTextoCuerpoCatalogo
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            cert_id,
            datos_estudiante['name'],
            id_curso,
            datos_estudiante['date'],
            id_tipo_credencial,
            signature,
            'Activo',
            pdf_bytes,
            recipient_id,
            created_by,
            training_months_db,
            body_text,
            tgc,
            id_centro_educativo,
            id_firma_doctores,
            id_texto_cuerpo_catalogo,
        ))
        cursor.execute(
            """
            UPDATE EstadisticasAplicacion
            SET IdUltimoCertificadoGenerado = ?
            WHERE IdEstadistica = 1
            """,
            (cert_id,),
        )
        conn.commit()
    finally:
        conn.close()

    registrar_auditoria_certificado(cert_id, "GENERAR", created_by, None)

    stats_tesis['totalGenTime'] += tgc
    stats_tesis['genCount'] += 1
    _persist_stats()

    has_pdf = pdf_error is None and pdf_bytes is not None and len(pdf_bytes) > 0
    print(f"DEBUG: recipient_id={recipient_id}, has_pdf={has_pdf}")

    mail_sent = False
    if recipient_id and has_pdf:
        mail_sent = _intentar_enviar_correo_certificado_asignado(
            recipient_id,
            cert_id,
            datos_estudiante["name"],
            curso_nombre,
            tipo_nombre,
            created_by,
            pdf_bytes=pdf_bytes,
        )

    return {
        "id": cert_id,
        "name": datos_estudiante['name'],
        "course": curso_nombre,
        "type": tipo_nombre,
        "status": 'Activo',
        "signature": signature,
        "qrPayload": qr_payload,
        "hasPdf": has_pdf,
        "pdfError": pdf_error,
        "mailSent": mail_sent,
    }, tgc


def verificar_certificado(qr_payload_str):
    start_time = time.perf_counter()
    is_valid = False
    parsed_data = {}
    conn = None

    try:
        cert_id, cert_sig = _parse_qr_payload(qr_payload_str)
        parsed_data = {"id": cert_id, "signature": cert_sig} if cert_id or cert_sig else {}
        if not cert_id or not cert_sig:
            raise ValueError("Payload QR incompleto")

        conn = get_db_connection()
        if conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT c.NombreEstudiante, cu.Nombre AS CursoNombre, c.FechaEmision, tc.Nombre AS TipoNombre, c.Estado
                FROM Certificados c
                INNER JOIN Cursos cu ON cu.IdCurso = c.IdCurso
                INNER JOIN TiposCredencial tc ON tc.IdTipoCredencial = c.IdTipoCredencial
                WHERE c.IdCertificado = ?
                """,
                (cert_id,),
            )
            row = cursor.fetchone()

            if row and row.Estado == 'Activo':
                raw_data = signed_message(
                    cert_id,
                    row.NombreEstudiante,
                    (row.CursoNombre or ""),
                    row.FechaEmision,
                    (row.TipoNombre or ""),
                )
                if verify_signature(raw_data, cert_sig):
                    is_valid = True

        # Actualizar métricas del certificado en BD
        if conn:
            try:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    UPDATE Certificados 
                    SET TiempoVerificacionSeg = ?, EsValido = ? 
                    WHERE IdCertificado = ?
                    """,
                    (time.perf_counter() - start_time, 1 if is_valid else 0, cert_id)
                )
                conn.commit()
            except Exception as e:
                print(f"Error actualizando métricas de verificación: {e}")
    except Exception:
        is_valid = False
    finally:
        if conn:
            try:
                conn.close()
            except Exception:
                pass

    end_time = time.perf_counter()
    tv = end_time - start_time

    stats_tesis['totalVerTime'] += tv
    stats_tesis['verCount'] += 1

    if is_valid:
        stats_tesis['validCount'] += 1
    else:
        stats_tesis['invalidCount'] += 1

    _persist_stats()

    return is_valid, tv, parsed_data


def obtener_todos_los_certificados():
    conn = get_db_connection()
    certs = []
    if conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT c.IdCertificado, c.NombreEstudiante, cu.Nombre AS NombreCurso, tc.Nombre AS NombreTipoCredencial, c.FirmaDigital, c.Estado,
                   c.IdUsuarioDestinatario, c.MesesFormacion,
                   c.TiempoGeneracionSeg, c.TiempoVerificacionSeg, c.EsValido,
                   CASE WHEN c.ContenidoPdf IS NOT NULL AND DATALENGTH(c.ContenidoPdf) > 0 THEN 1 ELSE 0 END AS HasPdfDb
            FROM Certificados c
            INNER JOIN Cursos cu ON cu.IdCurso = c.IdCurso
            INNER JOIN TiposCredencial tc ON tc.IdTipoCredencial = c.IdTipoCredencial
            ORDER BY c.FechaCreacion DESC
        """)
        for row in cursor.fetchall():
            qr_payload = json.dumps({"id": row.IdCertificado, "signature": row.FirmaDigital})
            rid = getattr(row, "IdUsuarioDestinatario", None)
            has_pdf = bool(getattr(row, "HasPdfDb", 0))
            certs.append({
                "id": row.IdCertificado, "name": row.NombreEstudiante, "course": row.NombreCurso,
                "type": row.NombreTipoCredencial, "status": row.Estado,
                "signature": row.FirmaDigital, "qrPayload": qr_payload,
                "hasPdf": has_pdf,
                "recipientUserId": int(rid) if rid is not None else None,
                "months": getattr(row, "MesesFormacion", None),
                "tgc": getattr(row, "TiempoGeneracionSeg", 0),
                "tv": getattr(row, "TiempoVerificacionSeg", 0),
                "isValid": bool(getattr(row, "EsValido", 0)),
            })
        conn.close()
    return certs


def obtener_certificados_por_alumno(user_id):
    conn = get_db_connection()
    certs = []
    if not conn:
        return certs
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT c.IdCertificado, c.NombreEstudiante, cu.Nombre AS NombreCurso, tc.Nombre AS NombreTipoCredencial,
                   c.FechaEmision, c.Estado,
                   CASE WHEN c.ContenidoPdf IS NOT NULL AND DATALENGTH(c.ContenidoPdf) > 0 THEN 1 ELSE 0 END AS HasPdfDb
            FROM Certificados c
            INNER JOIN Cursos cu ON cu.IdCurso = c.IdCurso
            INNER JOIN TiposCredencial tc ON tc.IdTipoCredencial = c.IdTipoCredencial
            WHERE c.IdUsuarioDestinatario = ?
            ORDER BY c.FechaCreacion DESC
        """, (user_id,))
        for row in cursor.fetchall():
            certs.append({
                "id": row.IdCertificado,
                "name": row.NombreEstudiante,
                "course": row.NombreCurso,
                "type": row.NombreTipoCredencial,
                "issueDate": row.FechaEmision,
                "status": row.Estado,
                "hasPdf": bool(getattr(row, "HasPdfDb", 0)),
            })
    finally:
        conn.close()
    return certs


def leer_pdf_bytes(cert_id):
    """Lee el PDF almacenado en ContenidoPdf (SQL Server)."""
    conn = get_db_connection()
    if not conn:
        return None
    try:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT ContenidoPdf FROM Certificados WHERE IdCertificado = ?",
            (cert_id,),
        )
        row = cursor.fetchone()
        if not row:
            return None
        pc = getattr(row, "ContenidoPdf", None)
        if pc is None:
            return None
        raw = bytes(pc) if not isinstance(pc, (bytes, bytearray)) else pc
        return raw if len(raw) > 0 else None
    finally:
        conn.close()


def usuario_puede_descargar_pdf(cert_id, user_id, role):
    """
    Devuelve (True, bytes) si hay PDF y permiso, o (False, None).
    """
    if role != auth_usuarios.ROLE_ADMIN:
        conn = get_db_connection()
        if not conn:
            return False, None
        try:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT IdUsuarioDestinatario FROM Certificados WHERE IdCertificado = ?",
                (cert_id,),
            )
            row = cursor.fetchone()
            if not row:
                return False, None
            rid = row.IdUsuarioDestinatario
            if rid is None or int(rid) != int(user_id):
                return False, None
        finally:
            conn.close()

    data = leer_pdf_bytes(cert_id)
    if not data:
        return False, None
    return True, data


def cambiar_estado_certificado(cert_id, id_usuario_actor=None):
    conn = get_db_connection()
    if not conn:
        return False
    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            UPDATE Certificados SET Estado = CASE WHEN Estado = N'Activo' THEN N'Revocado' ELSE N'Activo' END
            WHERE IdCertificado = ?
            """,
            (cert_id,),
        )
        affected = cursor.rowcount
        conn.commit()
        if affected > 0:
            registrar_auditoria_certificado(cert_id, "CAMBIO_ESTADO", id_usuario_actor, None)
        return affected > 0
    finally:
        conn.close()


def obtener_estadisticas():
    avg_gen = (stats_tesis['totalGenTime'] / stats_tesis['genCount']) if stats_tesis['genCount'] > 0 else 0
    avg_ver = (stats_tesis['totalVerTime'] / stats_tesis['verCount']) if stats_tesis['verCount'] > 0 else 0

    return {
        "avgGenTime": f"{avg_gen:.4f}",
        "avgVerTime": f"{avg_ver:.4f}",
        "validCount": stats_tesis['validCount'],
        "invalidCount": stats_tesis['invalidCount'],
        "verCount": stats_tesis['verCount'],
        "genCount": stats_tesis['genCount']
    }


def obtener_dashboard_insights():
    """Devuelve comparativas para graficos del dashboard admin."""
    conn = get_db_connection()
    default_payload = {
        "monthly": [],
        "status": {"total": 0, "active": 0, "revoked": 0},
        "topCourses": [],
        "topTypes": [],
    }
    if not conn:
        return default_payload

    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT
                COUNT(*) AS Total,
                SUM(CASE WHEN Estado = N'Activo' THEN 1 ELSE 0 END) AS Activos,
                SUM(CASE WHEN Estado = N'Revocado' THEN 1 ELSE 0 END) AS Revocados
            FROM Certificados
            """
        )
        row = cursor.fetchone()
        status_total = int(getattr(row, "Total", 0) or 0)
        status_active = int(getattr(row, "Activos", 0) or 0)
        status_revoked = int(getattr(row, "Revocados", 0) or 0)

        cursor.execute(
            """
            SELECT
                YEAR(FechaCreacion) AS Anio,
                MONTH(FechaCreacion) AS Mes,
                COUNT(*) AS Emitidos,
                SUM(CASE WHEN Estado = N'Activo' THEN 1 ELSE 0 END) AS Activos,
                SUM(CASE WHEN Estado = N'Revocado' THEN 1 ELSE 0 END) AS Revocados,
                AVG(CAST(TiempoGeneracionSeg AS FLOAT)) AS AvgGen,
                AVG(CAST(TiempoVerificacionSeg AS FLOAT)) AS AvgVer
            FROM Certificados
            WHERE FechaCreacion >= DATEADD(MONTH, -5, DATEFROMPARTS(YEAR(GETDATE()), MONTH(GETDATE()), 1))
            GROUP BY YEAR(FechaCreacion), MONTH(FechaCreacion)
            ORDER BY Anio ASC, Mes ASC
            """
        )
        monthly_rows = cursor.fetchall()
        monthly = []
        for r in monthly_rows:
            monthly.append(
                {
                    "year": int(r.Anio),
                    "month": int(r.Mes),
                    "label": f"{int(r.Mes):02d}/{int(r.Anio)}",
                    "emitted": int(getattr(r, "Emitidos", 0) or 0),
                    "active": int(getattr(r, "Activos", 0) or 0),
                    "revoked": int(getattr(r, "Revocados", 0) or 0),
                    "avgGen": float(getattr(r, "AvgGen", 0) or 0),
                    "avgVer": float(getattr(r, "AvgVer", 0) or 0),
                }
            )

        cursor.execute(
            """
            SELECT TOP 5
                ISNULL(cu.Nombre, N'(Sin curso)') AS Nombre,
                COUNT(*) AS Total
            FROM Certificados c
            LEFT JOIN Cursos cu ON cu.IdCurso = c.IdCurso
            GROUP BY cu.Nombre
            ORDER BY COUNT(*) DESC, ISNULL(cu.Nombre, N'(Sin curso)') ASC
            """
        )
        top_courses = [
            {"name": (r.Nombre or "(Sin curso)"), "count": int(getattr(r, "Total", 0) or 0)}
            for r in cursor.fetchall()
        ]

        cursor.execute(
            """
            SELECT TOP 5
                ISNULL(tc.Nombre, N'(Sin tipo)') AS Nombre,
                COUNT(*) AS Total
            FROM Certificados c
            LEFT JOIN TiposCredencial tc ON tc.IdTipoCredencial = c.IdTipoCredencial
            GROUP BY tc.Nombre
            ORDER BY COUNT(*) DESC, ISNULL(tc.Nombre, N'(Sin tipo)') ASC
            """
        )
        top_types = [
            {"name": (r.Nombre or "(Sin tipo)"), "count": int(getattr(r, "Total", 0) or 0)}
            for r in cursor.fetchall()
        ]

        return {
            "monthly": monthly,
            "status": {
                "total": status_total,
                "active": status_active,
                "revoked": status_revoked,
            },
            "topCourses": top_courses,
            "topTypes": top_types,
        }
    except Exception:
        return default_payload
    finally:
        conn.close()


def buscar_certificados(q=None, page=1, page_size=5):
    conn = get_db_connection()
    certs = []
    total = 0
    if not conn:
        return [], 0
    try:
        cursor = conn.cursor()
        params = []
        where = ""
        if q:
            where = "WHERE (c.NombreEstudiante LIKE ? OR cu.Nombre LIKE ? OR tc.Nombre LIKE ?)"
            qlike = f"%{q}%"
            params.extend([qlike, qlike, qlike])
        # Total count
        cursor.execute(
            f"""
            SELECT COUNT(*)
            FROM Certificados c
            INNER JOIN Cursos cu ON cu.IdCurso = c.IdCurso
            INNER JOIN TiposCredencial tc ON tc.IdTipoCredencial = c.IdTipoCredencial
            {where}
            """,
            params,
        )
        total = cursor.fetchone()[0]
        # Paged results, newest first
        offset = (page - 1) * page_size
        sql = f"""
            SELECT c.IdCertificado, c.NombreEstudiante, cu.Nombre AS NombreCurso, tc.Nombre AS NombreTipoCredencial,
                   c.FirmaDigital, c.Estado,
                   c.IdUsuarioDestinatario, c.MesesFormacion,
                   c.TiempoGeneracionSeg, c.TiempoVerificacionSeg, c.EsValido,
                   CASE WHEN c.ContenidoPdf IS NOT NULL AND DATALENGTH(c.ContenidoPdf) > 0 THEN 1 ELSE 0 END AS HasPdfDb
            FROM Certificados c
            INNER JOIN Cursos cu ON cu.IdCurso = c.IdCurso
            INNER JOIN TiposCredencial tc ON tc.IdTipoCredencial = c.IdTipoCredencial
            {where}
            ORDER BY c.FechaCreacion DESC
            OFFSET ? ROWS FETCH NEXT ? ROWS ONLY
        """
        params.extend([offset, page_size])
        cursor.execute(sql, params)
        for row in cursor.fetchall():
            qr_payload = json.dumps({"id": row.IdCertificado, "signature": row.FirmaDigital})
            rid = getattr(row, "IdUsuarioDestinatario", None)
            has_pdf = bool(getattr(row, "HasPdfDb", 0))
            certs.append({
                "id": row.IdCertificado, "name": row.NombreEstudiante, "course": row.NombreCurso,
                "type": row.NombreTipoCredencial, "status": row.Estado,
                "signature": row.FirmaDigital, "qrPayload": qr_payload,
                "hasPdf": has_pdf,
                "recipientUserId": int(rid) if rid is not None else None,
                "months": getattr(row, "MesesFormacion", None),
                "tgc": getattr(row, "TiempoGeneracionSeg", 0),
                "tv": getattr(row, "TiempoVerificacionSeg", 0),
                "isValid": bool(getattr(row, "EsValido", 0)),
            })
    finally:
        conn.close()
    return certs, total
