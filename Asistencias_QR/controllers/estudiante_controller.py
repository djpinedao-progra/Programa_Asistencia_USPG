from flask import Blueprint, jsonify, request

from database.conexion import get_connection
from services.estudiante_service import EstudianteService

estudiante_bp = Blueprint("estudiante", __name__)
service = EstudianteService(get_connection)


@estudiante_bp.post("/api/estudiantes")
def registrar_estudiante():
    try:
        estudiante = service.registrar(request.get_json(silent=True) or {})
        return jsonify({"status": "ok", "data": estudiante.to_dict()}), 201
    except ValueError as error:
        return jsonify({"status": "error", "message": str(error)}), 400


@estudiante_bp.get("/api/estudiantes")
def listar_estudiantes():
    return jsonify({"status": "ok", "data": [e.to_dict() for e in service.listar()]})