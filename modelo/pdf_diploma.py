"""Generación de PDF horizontal estilo reconocimiento oficial (marco, logos, cuerpo, firma, QR)."""

import io
import os
from datetime import datetime

import qrcode
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.units import cm
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas

# Estilo documento formal (marco dorado / negro / gris)
FRAME_GOLD = colors.Color(0.62, 0.48, 0.18)
MUTED = colors.Color(0.35, 0.35, 0.37)
CORNER_GRAY = colors.Color(0.72, 0.72, 0.74)

_ASSETS_DIR = os.path.normpath(
    os.path.join(os.path.dirname(__file__), "..", "vista", "assets", "imagenes", "certificados")
)


def _asset_path(*candidates: str) -> str | None:
    for name in candidates:
        p = os.path.join(_ASSETS_DIR, name)
        if os.path.isfile(p):
            return p
    return None


def _format_display_date(iso_date: str) -> str:
    try:
        d = datetime.strptime(iso_date[:10], "%Y-%m-%d")
        return d.strftime("%d/%m/%Y")
    except Exception:
        return iso_date or ""


def _wrap_centered_lines(
    c, text: str, cx: float, y_top: float, max_w: float, font: str, size: float, leading_pt: float
):
    words = text.split()
    if not words:
        return y_top
    line = ""
    y = y_top
    for word in words:
        test = (line + " " + word).strip()
        if c.stringWidth(test, font, size) <= max_w:
            line = test
        else:
            c.drawCentredString(cx, y, line)
            y -= leading_pt
            line = word
    if line:
        c.drawCentredString(cx, y, line)
        y -= leading_pt
    return y


def _draw_ornate_double_frame(c, w: float, h: float):
    """Marco doble con esquinas decorativas (aprox. al diploma de referencia)."""
    m_out = 0.55 * cm
    gap_gold = 0.32 * cm
    gap_inner = 0.22 * cm
    x0, y0 = m_out, m_out
    x1, y1 = w - m_out, h - m_out

    c.setStrokeColor(colors.black)
    c.setLineWidth(1.0)
    c.rect(x0, y0, x1 - x0, y1 - y0, fill=0, stroke=1)

    xi0 = x0 + gap_gold
    yi0 = y0 + gap_gold
    xi1 = x1 - gap_gold
    yi1 = y1 - gap_gold
    c.setStrokeColor(FRAME_GOLD)
    c.setLineWidth(2.2)
    c.rect(xi0, yi0, xi1 - xi0, yi1 - yi0, fill=0, stroke=1)

    xj0 = xi0 + gap_inner
    yj0 = yi0 + gap_inner
    xj1 = xi1 - gap_inner
    yj1 = yi1 - gap_inner
    c.setStrokeColor(colors.black)
    c.setLineWidth(0.45)
    c.rect(xj0, yj0, xj1 - xj0, yj1 - yj0, fill=0, stroke=1)

    # Ornamentos en esquinas (trazos tipo filigrana simplificada)
    L = 0.95 * cm
    tick = 0.28 * cm
    c.setStrokeColor(CORNER_GRAY)
    c.setLineWidth(0.55)
    corners = [
        (xj0, yj0, 1, 1),
        (xj1, yj0, -1, 1),
        (xj0, yj1, 1, -1),
        (xj1, yj1, -1, -1),
    ]
    for bx, by, sx, sy in corners:
        ax = bx + sx * L
        ay = by + sy * L
        c.line(bx, by, ax, by)
        c.line(bx, by, bx, ay)
        c.line(bx + sx * tick, by + sy * tick, bx + sx * (L - tick), by + sy * (L - tick))


def _draw_scaled_image(c, ir: ImageReader, cx: float, top_y: float, max_w: float, max_h: float, anchor: str):
    """anchor: 'left' (borde izquierdo en cx) o 'right' (borde derecho en cx)."""
    iw, ih = ir.getSize()
    sc = min(max_w / float(iw), max_h / float(ih))
    sw, sh = iw * sc, ih * sc
    base_y = top_y - sh
    if anchor == "right":
        x = cx - sw
    else:
        x = cx
    c.drawImage(ir, x, base_y, width=sw, height=sh, mask="auto")
    return top_y - sh - 0.15 * cm


def generar_pdf_diploma(
    dest,
    cert_id: str,
    nombre: str,
    curso: str,
    fecha_emision: str,
    tipo_credencial: str,
    qr_payload: str,
    horas: int = 120,
    texto_cuerpo: str | None = None,
    incluir_meses: bool = False,
    meses: int | None = None,
    *,
    logo_centro_bytes: bytes | None = None,
    logo_derecho_bytes: bytes | None = None,
    doctor_firma_bytes: bytes | None = None,
    doctor_nombres: str | None = None,
    doctor_genero: str | None = None,
):
    """
    Diploma horizontal estilo «reconocimiento»: logos superior, textos institucionales
    fijos (Hospital Distrital de Laredo / Reconocimiento), «Otorgado a», cuerpo, firma
    manuscrita del director (tabla FirmaDoctores) y QR.

    Logos: izquierda desde centro (Logo); derecha desde LogoDerecho del centro o assets.
    """
    w, h = landscape(A4)
    c = canvas.Canvas(dest, pagesize=(w, h))

    c.setFillColor(colors.white)
    c.rect(0, 0, w, h, fill=1, stroke=0)
    _draw_ornate_double_frame(c, w, h)

    margin_x = 1.85 * cm
    inner_w = w - 2 * margin_x
    cx = w / 2

    # --- Logos superiores (izq. / der.) ---
    y_header_top = h - 1.55 * cm
    y_below_logos = y_header_top

    max_logo_w, max_logo_h = 4.2 * cm, 3.0 * cm
    left_x = margin_x
    right_x = w - margin_x

    left_ir = None
    if logo_centro_bytes:
        try:
            left_ir = ImageReader(io.BytesIO(logo_centro_bytes))
        except Exception:
            left_ir = None
    if left_ir is None:
        lp = _asset_path(
            "logo_regional.png",
            "logo_izquierda.png",
            "logo_gobierno.png",
            "logo.png",
        )
        if lp:
            left_ir = ImageReader(lp)
    if left_ir:
        y_below_logos = min(
            y_below_logos,
            _draw_scaled_image(c, left_ir, left_x, y_header_top, max_logo_w, max_logo_h, "left"),
        )

    right_ir = None
    if logo_derecho_bytes:
        try:
            right_ir = ImageReader(io.BytesIO(logo_derecho_bytes))
        except Exception:
            right_ir = None
    if right_ir is None:
        right_path = _asset_path(
            "logo_secundario.png",
            "logo_upao.png",
            "logo_derecha.png",
            "logo_institucion.png",
        )
        if right_path:
            right_ir = ImageReader(right_path)
    if right_ir:
        y_below_logos = min(
            y_below_logos,
            _draw_scaled_image(c, right_ir, right_x, y_header_top, max_logo_w, max_logo_h, "right"),
        )

    y = y_below_logos - 0.35 * cm

    inst = "HOSPITAL DISTRITAL DE LAREDO"
    c.setFillColor(colors.black)
    c.setFont("Helvetica-Bold", 10.5)
    fs = 10.5
    while fs >= 8 and c.stringWidth(inst, "Helvetica-Bold", fs) > inner_w:
        fs -= 0.5
    c.setFont("Helvetica-Bold", fs)
    c.drawCentredString(cx, y, inst)
    y -= 0.85 * cm

    titulo = "RECONOCIMIENTO"
    titulo_size = 22
    c.setFont("Helvetica-Bold", titulo_size)
    title_leading = titulo_size * 1.15
    c.drawCentredString(cx, y, titulo)
    y -= title_leading
    y -= 0.35 * cm

    c.setFillColor(colors.black)
    c.setFont("Times-Italic", 12)
    c.drawString(margin_x, y, "Otorgado a:")
    y -= 0.75 * cm

    # Nombre del beneficiario
    nombre_clean = (nombre or "").strip().upper()
    name_size = 20
    c.setFont("Helvetica-Bold", name_size)
    while name_size >= 14 and c.stringWidth(nombre_clean, "Helvetica-Bold", name_size) > inner_w:
        name_size -= 0.5
    c.setFont("Helvetica-Bold", name_size)
    c.drawCentredString(cx, y, nombre_clean)
    y -= name_size * 1.25

    y -= 0.35 * cm

    # Cuerpo (cursiva, centrado)
    if texto_cuerpo and texto_cuerpo.strip():
        body = texto_cuerpo.strip()
    else:
        body = (
            f"Por haber culminado satisfactoriamente el programa «{curso}» "
            f"en la modalidad «{tipo_credencial}», conforme a los requisitos académicos establecidos."
        )

    body_size = 11
    leading = body_size * 1.35
    c.setFont("Times-Italic", body_size)
    c.setFillColor(colors.black)
    y = _wrap_centered_lines(c, body, cx, y, inner_w, "Times-Italic", body_size, leading)
    y -= 0.45 * cm

    # Metadatos discretos (horas / meses / fecha)
    c.setFont("Helvetica", 8)
    c.setFillColor(MUTED)
    meta_parts = [f"Fecha de emisión: {_format_display_date(fecha_emision)}"]
    if horas and horas > 0:
        meta_parts.append(f"Carga horaria referencial: {horas} h")
    if incluir_meses and meses is not None:
        meta_parts.append(f"Duración referencial: {meses} mes(es)")
    c.drawCentredString(cx, y, "   ·   ".join(meta_parts))
    y -= 0.65 * cm

    # --- Firma central (imagen + Dr./Dra. + cargo fijo) ---
    line_y = 2.85 * cm
    line_half = 4.2 * cm
    max_sig_w, max_sig_h = 4.8 * cm, 2.1 * cm
    if doctor_firma_bytes:
        try:
            ir_sig = ImageReader(io.BytesIO(doctor_firma_bytes))
            iw, ih = ir_sig.getSize()
            sc = min(max_sig_w / float(iw), max_sig_h / float(ih))
            sw, sh = iw * sc, ih * sc
            c.drawImage(
                ir_sig,
                cx - sw / 2,
                line_y + 0.12 * cm,
                width=sw,
                height=sh,
                mask="auto",
            )
        except Exception:
            pass

    c.setStrokeColor(colors.black)
    c.setLineWidth(0.6)
    c.line(cx - line_half, line_y, cx + line_half, line_y)

    gen = (doctor_genero or "").strip()
    pref = "Dr. " if gen == "Masculino" else "Dra. " if gen == "Femenino" else ""
    nom_doc = (doctor_nombres or "").strip()
    firmante_line = (pref + nom_doc).strip() or (os.environ.get("CERT_FIRMANTE_NOMBRE") or "").strip()
    if firmante_line:
        c.setFont("Helvetica", 9.5)
        c.setFillColor(colors.black)
        c.drawCentredString(cx, line_y - 0.42 * cm, firmante_line)
    c.setFont("Helvetica-Bold", 8.5)
    c.drawCentredString(cx, line_y - 0.82 * cm, "DIRECTOR DEL HOSPITAL DISTRITAL DE LAREDO")

    # --- QR verificación (esquina inferior derecha) ---
    qr = qrcode.QRCode(version=None, box_size=3, border=1)
    qr.add_data(qr_payload)
    qr.make(fit=True)
    pil_img = qr.make_image(fill_color="black", back_color="white")
    buf = io.BytesIO()
    pil_img.save(buf, format="PNG")
    buf.seek(0)
    qr_size = 2.65 * cm
    qx = w - margin_x - qr_size
    qy = 1.05 * cm
    c.setStrokeColor(MUTED)
    c.setLineWidth(0.5)
    pad = 0.1 * cm
    c.rect(qx - pad, qy - pad, qr_size + 2 * pad, qr_size + 2 * pad, fill=0, stroke=1)
    c.drawImage(ImageReader(buf), qx, qy, width=qr_size, height=qr_size, mask="auto")
    c.setFont("Helvetica", 6.5)
    c.setFillColor(MUTED)
    c.drawCentredString(qx + qr_size / 2, qy - 0.38 * cm, "Verificación")

    # Identificador breve (pie izquierdo)
    uid_short = cert_id.replace("UCV-", "")[:16]
    c.setFont("Helvetica", 7)
    c.drawString(margin_x, 1.0 * cm, f"Id. documento: {uid_short}")

    c.showPage()
    c.save()


def generar_pdf_diploma_bytes(
    cert_id: str,
    nombre: str,
    curso: str,
    fecha_emision: str,
    tipo_credencial: str,
    qr_payload: str,
    horas: int = 120,
    texto_cuerpo: str | None = None,
    incluir_meses: bool = False,
    meses: int | None = None,
    *,
    logo_centro_bytes: bytes | None = None,
    logo_derecho_bytes: bytes | None = None,
    doctor_firma_bytes: bytes | None = None,
    doctor_nombres: str | None = None,
    doctor_genero: str | None = None,
) -> bytes:
    """Genera el PDF en memoria (para guardar en SQL Server VARBINARY)."""
    buf = io.BytesIO()
    generar_pdf_diploma(
        buf,
        cert_id=cert_id,
        nombre=nombre,
        curso=curso,
        fecha_emision=fecha_emision,
        tipo_credencial=tipo_credencial,
        qr_payload=qr_payload,
        horas=horas,
        texto_cuerpo=texto_cuerpo,
        incluir_meses=incluir_meses,
        meses=meses,
        logo_centro_bytes=logo_centro_bytes,
        logo_derecho_bytes=logo_derecho_bytes,
        doctor_firma_bytes=doctor_firma_bytes,
        doctor_nombres=doctor_nombres,
        doctor_genero=doctor_genero,
    )
    return buf.getvalue()
