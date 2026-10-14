"""Generación de imágenes QR a partir de una URL."""
import io

import qrcode


def build_qr_png(value):
    """Devuelve los bytes PNG del código QR para el valor recibido."""
    output = io.BytesIO()
    qrcode.make(value).save(output, format="PNG")
    return output.getvalue()
