from datetime import datetime, timedelta, timezone

import pytest

from app import db
from app.models import AttendanceSession, Course, CourseEnrollment, User
from app.services import AttendanceService


def make_user(name, email, role):
    user = User(name=name, email=email, role=role)
    user.set_password("password-seguro-123")
    db.session.add(user)
    db.session.commit()
    return user


def test_attendance_can_only_be_recorded_once(app):
    with app.app_context():
        teacher = make_user("Docente", "docente@catedratico.uspg.edu.gt", "docente")
        student = make_user("Alumno", "alumno@alumno.uspg.edu.gt", "alumno")
        course = Course(name="Matemática", code="MAT-01", teacher_id=teacher.id)
        db.session.add(course)
        db.session.flush()
        db.session.add(CourseEnrollment(course_id=course.id, student_id=student.id))
        db.session.commit()
        service = AttendanceService()
        attendance_session, token = service.create_session(course.id, teacher.id)

        service.record_attendance(token, student)
        with pytest.raises(ValueError, match="ya quedó registrada"):
            service.record_attendance(token, student)

        assert len(attendance_session.attendances) == 1


def test_expired_session_is_rejected(app):
    with app.app_context():
        teacher = make_user("Docente", "docente@catedratico.uspg.edu.gt", "docente")
        student = make_user("Alumno", "alumno@alumno.uspg.edu.gt", "alumno")
        course = Course(name="Historia", code="HIS-01", teacher_id=teacher.id)
        db.session.add(course)
        db.session.flush()
        db.session.add(CourseEnrollment(course_id=course.id, student_id=student.id))
        db.session.commit()
        service = AttendanceService()
        attendance_session, token = service.create_session(course.id, teacher.id)
        attendance_session.expires_at = datetime.now(timezone.utc) - timedelta(minutes=1)
        db.session.commit()

        with pytest.raises(ValueError, match="venció"):
            service.record_attendance(token, student)


def test_only_course_owner_can_open_qr(app):
    with app.app_context():
        teacher = make_user("Docente", "docente@catedratico.uspg.edu.gt", "docente")
        other_teacher = make_user("Otro", "otro@catedratico.uspg.edu.gt", "docente")
        course = Course(name="Física", code="FIS-01", teacher_id=teacher.id)
        db.session.add(course)
        db.session.commit()

        with pytest.raises(ValueError, match="No tienes permiso"):
            AttendanceService().create_session(course.id, other_teacher.id)


def test_student_not_enrolled_cannot_record_attendance(app):
    with app.app_context():
        teacher = make_user("Docente", "docente@catedratico.uspg.edu.gt", "docente")
        student = make_user("Alumno", "alumno@alumno.uspg.edu.gt", "alumno")
        course = Course(name="Arte", code="ART-01", teacher_id=teacher.id)
        db.session.add(course)
        db.session.commit()
        attendance_session, token = AttendanceService().create_session(course.id, teacher.id)

        with pytest.raises(ValueError, match="No estás asignado"):
            AttendanceService().record_attendance(token, student)
        assert attendance_session.attendances == []
