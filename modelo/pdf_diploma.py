"""Generación de PDF tipo diploma horizontal con QR de verificación."""

import io
import os
from datetime import datetime

import qrcode
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.units import cm
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas

# Universidad César Vallejo — rojo y azul institucional
UCV_RED = colors.Color(0.75, 0.09, 0.12)
UCV_RED_DARK = colors.Color(0.55, 0.06, 0.1)
UCV_BLUE = colors.Color(0.0, 0.2, 0.55)
UCV_BLUE_DARK = colors.Color(0.0, 0.14, 0.42)
ACCENT_BLUE = colors.Color(0.45, 0.58, 0.82)
CREAM = colors.Color(0.99, 0.985, 0.98)
MUTED = colors.Color(0.38, 0.38, 0.4)

INSTITUTION_LINE = "Universidad César Vallejo"

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


def _wrap_centered_lines(c, text: str, cx: float, y_top: float, max_w: float, font: str, size: float, leading_pt: float):
    """Dibuja texto centrado con varias líneas hacia abajo; devuelve la Y del último renglón dibujado (misma unidad que ReportLab)."""
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
    return y


def _draw_corner_flourishes(canvas_obj, x0: float, y0: float, x1: float, y1: float, color, stroke: float = 0.85):
    """Esquinas tipo marco doble en las cuatro esquinas del rectángulo interior."""
    L = 1.15 * cm
    canvas_obj.setStrokeColor(color)
    canvas_obj.setLineWidth(stroke)
    # inferior izquierda
    canvas_obj.line(x0, y0, x0 + L, y0)
    canvas_obj.line(x0, y0, x0, y0 + L)
    # inferior derecha
    canvas_obj.line(x1, y0, x1 - L, y0)
    canvas_obj.line(x1, y0, x1, y0 + L)
    # superior izquierda
    canvas_obj.line(x0, y1, x0 + L, y1)
    canvas_obj.line(x0, y1, x0, y1 - L)
    # superior derecha
    canvas_obj.line(x1, y1, x1 - L, y1)
    canvas_obj.line(x1, y1, x1, y1 - L)


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
):
    """
    Dibuja el diploma en un archivo (str) o buffer binario (io.BytesIO).
    """
    w, h = landscape(A4)
    c = canvas.Canvas(dest, pagesize=(w, h))

    # Fondo crema
    c.setFillColor(CREAM)
    c.rect(0, 0, w, h, fill=1, stroke=0)

    margin_out = 0.85 * cm
    margin_in = 1.35 * cm
    # Marco exterior rojo, interior azul
    c.setStrokeColor(UCV_RED_DARK)
    c.setLineWidth(2.8)
    c.rect(margin_out, margin_out, w - 2 * margin_out, h - 2 * margin_out, fill=0, stroke=1)
    c.setStrokeColor(UCV_BLUE)
    c.setLineWidth(0.7)
    c.rect(margin_in, margin_in, w - 2 * margin_in, h - 2 * margin_in, fill=0, stroke=1)

    inner_left = margin_in + 0.55 * cm
    inner_right = w - margin_in - 0.55 * cm
    inner_bottom = margin_in + 0.55 * cm
    inner_top = h - margin_in - 0.55 * cm
    _draw_corner_flourishes(c, inner_left, inner_bottom, inner_right, inner_top, UCV_BLUE_DARK, 0.85)

    # Logo (opcional): colocar PNG/JPG en vista/assets/imagenes/certificados/logo.png
    logo_path = _asset_path(
        "logo.png",
        "logo.jpg",
        "logo.jpeg",
        "logotipo.png",
        "logotipo.jpg",
    )
    # Margen superior mayor para que el logo no quede pegado al borde del marco
    logo_top_y = h - 1.75 * cm
    y_below_header = logo_top_y
    if logo_path:
        ir_logo = ImageReader(logo_path)
        iw, ih = ir_logo.getSize()
        max_logo_w, max_logo_h = 13.5 * cm, 2.35 * cm
        scale = min(max_logo_w / float(iw), max_logo_h / float(ih))
        lw, lh = iw * scale, ih * scale
        logo_bottom = logo_top_y - lh
        c.drawImage(ir_logo, w / 2 - lw / 2, logo_bottom, width=lw, height=lh, mask="auto")
        y_below_header = logo_bottom - 0.5 * cm
    else:
        y_below_header = h - 2.1 * cm

    # Cabecera institucional
    c.setFillColor(UCV_BLUE_DARK)
    c.setFont("Helvetica-Bold", 9)
    c.drawCentredString(w / 2, y_below_header, INSTITUTION_LINE.upper())

    # Título principal = tipo de credencial
    titulo = (tipo_credencial or "Certificado").strip().upper()
    titulo_size = 20 if len(titulo) <= 42 else 17 if len(titulo) <= 56 else 14
    c.setFillColor(UCV_RED_DARK)
    c.setFont("Helvetica-Bold", titulo_size)
    title_max = w - 4.2 * cm
    tw = c.stringWidth(titulo, "Helvetica-Bold", titulo_size)
    title_leading = titulo_size * 1.2
    title_baseline = y_below_header - 0.65 * cm
    if tw <= title_max:
        c.drawCentredString(w / 2, title_baseline, titulo)
        y_after_title = title_baseline
    else:
        y_after_title = _wrap_centered_lines(
            c, titulo, w / 2, title_baseline + 0.15 * cm, title_max, "Helvetica-Bold", titulo_size, title_leading
        )

    # Regla decorativa rojo / azul bajo el título
    rule_y = y_after_title - 0.55 * cm
    rule_w = min(12 * cm, w * 0.42)
    c.setStrokeColor(UCV_RED)
    c.setLineWidth(1.15)
    c.line(w / 2 - rule_w / 2, rule_y, w / 2 + rule_w / 2, rule_y)
    c.setLineWidth(0.4)
    c.setStrokeColor(UCV_BLUE)
    c.line(w / 2 - rule_w / 2 + 0.45 * cm, rule_y - 0.12 * cm, w / 2 + rule_w / 2 - 0.45 * cm, rule_y - 0.12 * cm)

    c.setFillColor(MUTED)
    c.setFont("Helvetica-Oblique", 10.5)
    c.drawCentredString(w / 2, rule_y - 0.75 * cm, "Se certifica que")

    nombre_clean = (nombre or "").strip().upper()
    c.setFillColor(UCV_BLUE_DARK)
    name_size = 24
    name_max = w - 4.5 * cm
    while name_size >= 18 and c.stringWidth(nombre_clean, "Times-Bold", name_size) > name_max:
        name_size -= 1
    c.setFont("Times-Bold", name_size)
    c.drawCentredString(w / 2, rule_y - 1.85 * cm, nombre_clean)

    c.setFont("Helvetica", 10.5)
    c.setFillColor(colors.black)
    if texto_cuerpo and texto_cuerpo.strip():
        body = texto_cuerpo.strip()
    else:
        body = (
            f"Ha aprobado satisfactoriamente el programa «{curso}» en la modalidad "
            f"«{tipo_credencial}», cumpliendo con los requisitos académicos establecidos."
        )

    y_text = rule_y - 2.75 * cm
    max_w = w - 5.2 * cm
    first_para = True
    for para in body.split("\n"):
        para = para.strip()
        if not para:
            continue
        if not first_para:
            y_text -= 0.3 * cm
        first_para = False
        words = para.split()
        line = ""
        for word in words:
            test = (line + " " + word).strip()
            if c.stringWidth(test, "Helvetica", 10.5) <= max_w:
                line = test
            else:
                c.drawCentredString(w / 2, y_text, line)
                y_text -= 0.52 * cm
                line = word
        if line:
            c.drawCentredString(w / 2, y_text, line)
            y_text -= 0.52 * cm
    y_text -= 0.33 * cm

    c.setFont("Helvetica", 9.5)
    c.setFillColor(MUTED)
    c.drawCentredString(
        w / 2,
        y_text,
        f"Fecha de emisión: {_format_display_date(fecha_emision)}",
    )

    row_y = y_text - 1.75 * cm
    uid_part = cert_id.split("-")[-1] if "-" in cert_id else cert_id
    num_display = (uid_part[:13] + "…") if len(uid_part) > 14 else uid_part

    def col_num(xc, col_w, num, label, font_size=20):
        c.setFillColor(UCV_RED)
        c.setFont("Helvetica-Bold", font_size)
        c.drawCentredString(xc + col_w / 2, row_y, str(num))
        c.setFillColor(MUTED)
        c.setFont("Helvetica", 8.5)
        c.drawCentredString(xc + col_w / 2, row_y - 0.62 * cm, label)

    if incluir_meses and meses is not None:
        col_w = (w - 4 * cm) / 3
        x0 = 2 * cm
        col_num(x0, col_w, meses, "Meses de formación")
        cx_mid = x0 + col_w + col_w / 2
        c.setFont("Helvetica-Bold", 15)
        c.setFillColor(UCV_BLUE_DARK)
        c.drawCentredString(cx_mid, row_y, num_display.upper())
        c.setFillColor(MUTED)
        c.setFont("Helvetica", 8.5)
        c.drawCentredString(cx_mid, row_y - 0.62 * cm, "Certificado N.º")
        col_num(x0 + 2 * col_w, col_w, horas, "Horas académicas")
    else:
        col_w = (w - 4 * cm) / 2
        x0 = 2 * cm
        cx_mid = x0 + col_w / 2
        c.setFont("Helvetica-Bold", 15)
        c.setFillColor(UCV_BLUE_DARK)
        c.drawCentredString(cx_mid, row_y, num_display.upper())
        c.setFillColor(MUTED)
        c.setFont("Helvetica", 8.5)
        c.drawCentredString(cx_mid, row_y - 0.62 * cm, "Certificado N.º")
        col_num(x0 + col_w, col_w, horas, "Horas académicas")

    # --- Bloque inferior: firmas en los extremos, QR centrado debajo (sin solapamiento) ---
    path_dir = _asset_path(
        "firma_director_academico.png",
        "firma_director_academico.jpg",
        "firma_director.png",
    )
    path_coord = _asset_path(
        "firma_coordinador.png",
        "firma_coordinador.jpg",
        "firma_coordinacion.png",
    )
    # Firmas en columnas laterales equilibradas (sin pegarlas al borde ni al QR)
    left_cx = 4.85 * cm
    right_cx = w - 4.85 * cm
    max_sig_w, max_sig_h = 3.2 * cm, 1.45 * cm

    qr = qrcode.QRCode(version=None, box_size=4, border=1)
    qr.add_data(qr_payload)
    qr.make(fit=True)
    pil_img = qr.make_image(fill_color="#001f5c", back_color="white")
    buf = io.BytesIO()
    pil_img.save(buf, format="PNG")
    buf.seek(0)
    qr_size = 3.45 * cm
    qx = w / 2 - qr_size / 2
    qy = 1.95 * cm

    qr_top = qy + qr_size
    gap_qr_to_label = 0.62 * cm
    label_baseline = qr_top + gap_qr_to_label
    gap_label_to_sig = 0.48 * cm
    sig_img_bottom = label_baseline + gap_label_to_sig

    def _draw_sig_image(path: str, cx: float, img_bottom_y: float) -> float:
        """Dibuja la firma con borde inferior en img_bottom_y; devuelve la Y del borde superior."""
        ir = ImageReader(path)
        iw, ih = ir.getSize()
        sc = min(max_sig_w / float(iw), max_sig_h / float(ih))
        sw, sh = iw * sc, ih * sc
        base_y = img_bottom_y
        c.drawImage(ir, cx - sw / 2, base_y, width=sw, height=sh, mask="auto")
        return base_y + sh

    line_half = 2.85 * cm
    if path_dir:
        _draw_sig_image(path_dir, left_cx, sig_img_bottom)
    else:
        c.setStrokeColor(UCV_BLUE_DARK)
        c.setLineWidth(0.45)
        line_y = sig_img_bottom + 0.88 * cm
        c.line(left_cx - line_half, line_y, left_cx + line_half, line_y)

    if path_coord:
        _draw_sig_image(path_coord, right_cx, sig_img_bottom)
    else:
        c.setStrokeColor(UCV_BLUE_DARK)
        c.setLineWidth(0.45)
        line_y = sig_img_bottom + 0.88 * cm
        c.line(right_cx - line_half, line_y, right_cx + line_half, line_y)

    label_y = label_baseline
    c.setFont("Helvetica", 8.5)
    c.setFillColor(MUTED)
    c.drawCentredString(left_cx, label_y, "Director académico")
    c.drawCentredString(right_cx, label_y, "Coordinación")

    c.setStrokeColor(ACCENT_BLUE)
    c.setLineWidth(0.6)
    pad = 0.12 * cm
    c.rect(qx - pad, qy - pad, qr_size + 2 * pad, qr_size + 2 * pad, fill=0, stroke=1)
    c.drawImage(ImageReader(buf), qx, qy, width=qr_size, height=qr_size, mask="auto")

    c.setFillColor(MUTED)
    c.setFont("Helvetica", 7.5)
    c.drawCentredString(w / 2, qy - 0.42 * cm, "Código de verificación — documento electrónico autenticable")

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
    )
    return buf.getvalue()
