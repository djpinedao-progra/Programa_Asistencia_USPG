from flask import Blueprint

main = Blueprint("main", __name__)
expo = Blueprint("expo", __name__)


def register_controllers():
    from app.controllers import (  # noqa: F401
        admin_controller,
        admin_courses_controller,
        admin_reports_controller,
        auth_controller,
        expo_controller,
        export_controller,
        google_classroom_controller,
        student_controller,
        teacher_attendance_controller,
        teacher_controller,
    )


__all__ = ["expo", "main", "register_controllers"]
