from flask import Blueprint, jsonify, request

from database.conexion import get_connection
from services.asistencia_service import AsistenciaService

asistencia_bp = Blueprint("asistencia", __name__)
service = AsistenciaService(get_connection)


@asistencia_bp.post("/api/asistencias")
def registrar_asistencia():
    try:
        datos = request.get_json(silent=True) or {}
        asistencia = service.registrar(
            datos.get("carnet"), datos.get("sesion_id"), datos.get("token_qr")
        )
        return jsonify({"status": "ok", "data": asistencia.to_dict()}), 201
    except ValueError as error:
        return jsonify({"status": "error", "message": str(error)}), 400


@asistencia_bp.get("/api/asistencias")
def listar_asistencias():
    with get_connection() as connection:
        asistencias = connection.execute(
            """
            SELECT a.id, a.carnet, e.nombre, a.sesion_id, s.curso, a.fecha_hora
            FROM asistencias a
            JOIN estudiantes e ON e.carnet = a.carnet
            JOIN sesiones s ON s.id = a.sesion_id
            ORDER BY a.id DESC
            """
        ).fetchall()
    return jsonify({"status": "ok", "data": [dict(asistencia) for asistencia in asistencias]})