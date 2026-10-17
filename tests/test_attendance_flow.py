from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from app import db
from app.models import Attendance, AttendanceSession, CourseEnrollment


def test_qr_attendance_flow_duplicate_expiry_and_missing_students(
    app, sample_data, login_as, csrf_token
):
    ids = sample_data
    with app.app_context():
        db.session.add(
            CourseEnrollment(
                course_id=ids["course_id"],
                student_id=ids["other_student_id"],
            )
        )
        db.session.commit()

    teacher = app.test_client()
    login_as(teacher, ids["teacher_id"])
    token = csrf_token(teacher)
    started = teacher.post(
        f"/docente/cursos/{ids['course_id']}/sesion", data={"csrf_token": token}
    )
    assert started.status_code == 302
    with teacher.session_transaction() as session:
        session_id, qr_token = next(
            (int(key), value)
            for key, value in session["teacher_qr_tokens"].items()
        )

    student = app.test_client()
    login_as(student, ids["student_id"])
    student_csrf = csrf_token(student)
    present = student.post(
        "/api/asistencia",
        data={"csrf_token": student_csrf, "token": qr_token},
    )
    assert present.status_code == 302

    duplicate = student.post(
        "/api/asistencia",
        data={"csrf_token": student_csrf, "token": qr_token},
    )
    assert duplicate.status_code == 302
    with app.app_context():
        rows = db.session.scalars(
            select(Attendance).where(Attendance.session_id == session_id)
        ).all()
        assert len(rows) == 1
        assert rows[0].student_id == ids["student_id"]

    outsider = app.test_client()
    login_as(outsider, ids["outsider_id"])
    outsider_csrf = csrf_token(outsider)
    rejected = outsider.post(
        "/api/asistencia",
        data={"csrf_token": outsider_csrf, "token": qr_token},
    )
    assert rejected.status_code == 302

    with app.app_context():
        attendance_session = db.session.get(AttendanceSession, session_id)
        attendance_session.expires_at = datetime.now(timezone.utc) - timedelta(minutes=1)
        db.session.commit()
    expired = student.post(
        "/api/asistencia",
        data={"csrf_token": student_csrf, "token": qr_token},
    )
    assert expired.status_code == 302

    login_as(teacher, ids["teacher_id"])
    closed = teacher.post(
        f"/docente/sesiones/{session_id}/cerrar",
        data={"csrf_token": token},
    )
    assert closed.status_code == 302
    with app.app_context():
        absent = db.session.scalar(
            select(Attendance).where(
                Attendance.session_id == session_id,
                Attendance.student_id == ids["other_student_id"],
            )
        )
        assert absent is not None
        assert absent.status == "ausente"
