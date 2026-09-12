import sqlite3
from datetime import datetime

from models.asistencia import Asistencia


class AsistenciaService:
    def __init__(self, connection_factory):
        self.connection_factory = connection_factory

    def registrar(self, carnet, sesion_id, token_qr):
        if not carnet or not sesion_id or not token_qr:
            raise ValueError("carnet, sesion_id y token_qr son obligatorios")
        fecha_hora = datetime.now().isoformat(timespec="seconds")
        try:
            with self.connection_factory() as connection:
                sesion = connection.execute(
                    "SELECT token_qr FROM sesiones WHERE id = ?", (sesion_id,)
                ).fetchone()
                if sesion is None:
                    raise ValueError("Sesión no encontrada")
                if sesion["token_qr"] != token_qr:
                    raise ValueError("Token QR inválido")
                if connection.execute(
                    "SELECT 1 FROM estudiantes WHERE carnet = ?", (carnet,)
                ).fetchone() is None:
                    raise ValueError("Estudiante no registrado")
                cursor = connection.execute(
                    "INSERT INTO asistencias (carnet, sesion_id, fecha_hora) VALUES (?, ?, ?)",
                    (carnet, sesion_id, fecha_hora),
                )
        except sqlite3.IntegrityError as error:
            raise ValueError("Asistencia ya registrada") from error
        return Asistencia(cursor.lastrowid, carnet, sesion_id, fecha_hora)