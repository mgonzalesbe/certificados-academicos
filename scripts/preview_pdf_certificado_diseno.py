#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Vista previa del certificado (solo diseño).

  - No usa Flask, sesiones ni .env
  - No conecta a SQL Server ni a ninguna tabla
  - No llama a certificado.py ni a la API del proyecto

Solo importa modelo.pdf_diploma (layout + QR decorativo) y escribe un PDF en disco.

Requisitos: las mismas dependencias Python del proyecto (reportlab, qrcode, Pillow).

Desde la raíz del repositorio:

  python scripts/preview_pdf_certificado_diseno.py
  python scripts/preview_pdf_certificado_diseno.py -o C:\\temp\\prueba.pdf
  python scripts/preview_pdf_certificado_diseno.py --plantilla-ruta C:\\ruta\\fondo.png
"""

from __future__ import annotations

import argparse
import json
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from modelo.pdf_diploma import generar_pdf_diploma_bytes  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Genera un PDF de muestra con datos ficticios (sin base de datos).",
    )
    parser.add_argument(
        "-o",
        "--output",
        default="vista_previa_certificado_diseno.pdf",
        help="Ruta del archivo PDF de salida",
    )
    parser.add_argument(
        "--plantilla-ruta",
        default=None,
        metavar="ARCHIVO",
        help="Imagen JPG/PNG de plantilla a página completa (sin base de datos)",
    )
    args = parser.parse_args()

    plantilla_fondo_bytes = None
    if args.plantilla_ruta:
        p = os.path.abspath(args.plantilla_ruta)
        if not os.path.isfile(p):
            print(f"Error: no existe el archivo: {p}", file=sys.stderr)
            return 1
        with open(p, "rb") as f:
            plantilla_fondo_bytes = f.read()

    cert_id = "UCV-00000000-0000-4000-8000-000000000001"
    qr_payload = json.dumps({"id": cert_id, "signature": "solo-diseno-no-valido"})

    pdf_bytes = generar_pdf_diploma_bytes(
        cert_id=cert_id,
        nombre="María Fernanda Pérez López",
        curso="Programa de prácticas preprofesionales (ejemplo)",
        fecha_emision="2026-04-30",
        tipo_credencial="Reconocimiento por desempeño académico",
        qr_payload=qr_payload,
        texto_cuerpo=None,
        logo_derecho_bytes=None,
        doctor_firma_bytes=None,
        doctor_nombres="Ana María Gómez Ruiz",
        doctor_genero="Femenino",
        plantilla_fondo_bytes=plantilla_fondo_bytes,
    )

    out_path = os.path.abspath(args.output)
    with open(out_path, "wb") as f:
        f.write(pdf_bytes)
    print(out_path)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
