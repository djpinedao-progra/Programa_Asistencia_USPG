from flask import Blueprint

main = Blueprint("main", __name__)
expo = Blueprint("expo", __name__)


def register_controllers():
    from app.controllers import admin_controller, admin_courses_controller
    from app.controllers import admin_reports_controller, auth_controller
    from app.controllers import export_controller, student_controller, teacher_controller
    from app.controllers import expo_controller, teacher_attendance_controller


__all__ = ["main", "expo", "register_controllers"]
