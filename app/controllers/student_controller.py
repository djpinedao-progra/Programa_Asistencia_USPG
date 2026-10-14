from app.controllers import main
from app.controllers.decorators import roles_required
from app.controllers._support import *
from app.services.metrics_service import student_dashboard_data


@main.get("/alumno")
@roles_required("alumno")
def student_dashboard():
    data = student_dashboard_data(
        current_user.id, request.args.get("page", 1, type=int)
    )
    return render_template("student.html", **data)


@main.get("/check-in")
@roles_required("alumno")
def checkin():
    return render_template("checkin.html", qr_token=request.args.get("token", ""))


@main.post("/api/asistencia")
@roles_required("alumno")
def record_attendance():
    try:
        attendance = AttendanceService().record_attendance(
            request.form.get("token", ""), current_user
        )
    except ValueError as error:
        flash(str(error), "error")
        return redirect(url_for("main.student_dashboard"))
    flash(
        f"Asistencia registrada para {attendance.session.course.name}.", "success"
    )
    return redirect(url_for("main.student_dashboard"))
