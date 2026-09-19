from flask import Blueprint, jsonify, request

from database.conexion import get_connection
from services.sesion_service import SesionService

sesion_bp = Blueprint("sesion", __name__)
service = SesionService(get_connection)


@sesion_bp.post("/api/sesiones")
def crear_sesion():
    try:
        sesion = service.crear((request.get_json(silent=True) or {}).get("curso"))
        return jsonify({"status": "ok", "data": sesion.to_dict()}), 201
    except ValueError as error:
        return jsonify({"status": "error", "message": str(error)}), 400


@sesion_bp.get("/api/sesiones")
def listar_sesiones():
    with get_connection() as connection:
        sesiones = connection.execute(
            "SELECT id, curso, fecha_hora, token_qr FROM sesiones ORDER BY id DESC"
        ).fetchall()
    return jsonify({"status": "ok", "data": [dict(sesion) for sesion in sesiones]})