from flask import Blueprint, jsonify, request

from database.conexion import get_connection
from services.curso_service import CursoService

curso_bp = Blueprint("curso", __name__)
service = CursoService(get_connection)


@curso_bp.get("/api/cursos")
def listar_cursos():
    return jsonify({"status": "ok", "data": [curso.to_dict() for curso in service.listar()]})


@curso_bp.post("/api/cursos")
def crear_curso():
    try:
        curso = service.crear(request.get_json(silent=True) or {})
        return jsonify({"status": "ok", "data": curso.to_dict()}), 201
    except ValueError as error:
        return jsonify({"status": "error", "message": str(error)}), 400


@curso_bp.put("/api/cursos/<int:curso_id>")
def actualizar_curso(curso_id):
    try:
        curso = service.actualizar(curso_id, request.get_json(silent=True) or {})
        return jsonify({"status": "ok", "data": curso.to_dict()})
    except ValueError as error:
        return jsonify({"status": "error", "message": str(error)}), 400


@curso_bp.delete("/api/cursos/<int:curso_id>")
def eliminar_curso(curso_id):
    try:
        service.eliminar(curso_id)
        return jsonify({"status": "ok", "data": {"id": curso_id}})
    except ValueError as error:
        return jsonify({"status": "error", "message": str(error)}), 400
