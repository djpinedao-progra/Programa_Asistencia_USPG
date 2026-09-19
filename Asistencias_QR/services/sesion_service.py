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

    def crear(self, curso=None, curso_id=None):
        if curso_id is not None:
            try:
                curso_id = int(curso_id)
            except (TypeError, ValueError) as error:
                raise ValueError("El curso seleccionado no es válido") from error
            with self.connection_factory() as connection:
                row = connection.execute(
                    "SELECT nombre, estado FROM cursos WHERE id = ?", (curso_id,)
                ).fetchone()
            if row is None:
                raise ValueError("El curso seleccionado no existe")
            if row["estado"] != "activo":
                raise ValueError("No se puede crear una sesión para un curso inactivo")
            curso = row["nombre"]
        elif not isinstance(curso, str) or not curso.strip():
            raise ValueError("El curso es obligatorio")
        else:
            curso = curso.strip()
        fecha_hora = datetime.now().isoformat(timespec="seconds")
        token = str(uuid.uuid4())
        with self.connection_factory() as connection:
            cursor = connection.execute(
                "INSERT INTO sesiones (curso, curso_id, fecha_hora, token_qr) VALUES (?, ?, ?, ?)",
                (curso, curso_id, fecha_hora, token),
            )
            sesion_id = cursor.lastrowid

        os.makedirs(self.qr_directory, exist_ok=True)
        qr_file = os.path.join(self.qr_directory, f"sesion_{sesion_id}.png")
        qrcode.make(token).save(qr_file)
        return Sesion(sesion_id, curso, fecha_hora, token, qr_file, curso_id)
