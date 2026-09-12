import os
import uuid
from datetime import datetime
from pathlib import Path

import qrcode

from models.sesion import Sesion


class SesionService:
    def __init__(self, connection_factory, qr_directory=None):
        self.connection_factory = connection_factory
        self.qr_directory = qr_directory or Path(__file__).resolve().parents[1] / "static" / "qr_codes"

    def crear(self, curso):
        if not isinstance(curso, str) or not curso.strip():
            raise ValueError("El curso es obligatorio")
        curso = curso.strip()
        fecha_hora = datetime.now().isoformat(timespec="seconds")
        token = str(uuid.uuid4())
        with self.connection_factory() as connection:
            cursor = connection.execute(
                "INSERT INTO sesiones (curso, fecha_hora, token_qr) VALUES (?, ?, ?)",
                (curso, fecha_hora, token),
            )
            sesion_id = cursor.lastrowid

        os.makedirs(self.qr_directory, exist_ok=True)
        qr_file = os.path.join(self.qr_directory, f"sesion_{sesion_id}.png")
        qrcode.make(token).save(qr_file)
        return Sesion(sesion_id, curso, fecha_hora, token, qr_file)