from flask import Blueprint, jsonify, redirect, request, session

from database.conexion import get_connection
from services.google_classroom_service import GoogleClassroomService


google_bp = Blueprint("google", __name__)
service = GoogleClassroomService(get_connection)


@google_bp.get("/google/login")
def google_login():
    try:
        authorization_url, state = service.authorization_url(request)
        session["google_oauth_state"] = state
        return redirect(authorization_url)
    except ValueError as error:
        return jsonify({"status": "error", "message": str(error)}), 503


@google_bp.get("/oauth2callback")
def google_callback():
    try:
        if request.args.get("state") != session.pop("google_oauth_state", None):
            raise ValueError("Estado OAuth inválido o expirado")
        service.complete_authorization(request)
        return redirect("/?google=connected")
    except Exception as error:
        return jsonify({"status": "error", "message": f"No se pudo conectar con Google: {error}"}), 400


@google_bp.get("/api/google/status")
def google_status():
    return jsonify({"status": "ok", "data": {"configured": service.configured(), "connected": service.is_connected()}})


@google_bp.get("/api/google/cursos")
def google_courses():
    try:
        return jsonify({"status": "ok", "data": service.list_courses()})
    except ValueError as error:
        return jsonify({"status": "error", "message": str(error)}), 401


@google_bp.post("/api/google/sincronizar")
def google_sync():
    try:
        course_id = (request.get_json(silent=True) or {}).get("course_id")
        if not course_id:
            raise ValueError("Selecciona un curso de Google Classroom")
        result = service.sync_students(course_id)
        return jsonify({"status": "ok", "data": result})
    except ValueError as error:
        return jsonify({"status": "error", "message": str(error)}), 400
