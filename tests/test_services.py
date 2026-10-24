import hashlib
import secrets
from datetime import datetime, timedelta, timezone

import pytest

from app import db
from app.models import Attendance, AttendanceSession, Course, CourseEnrollment, User
from app.services.attendance_calculation_service import (
    attendance_percentage,
    exam_eligibility,
)
from app.services.attendance_service import AttendanceService
from app.services.expo_service import ExpoService
from app.services.metrics_service import admin_student_summaries
from app.services.student_metrics_service import student_dashboard_data


@pytest.mark.parametrize(
    ("present", "justified", "sessions", "expected"),
    [
        (3, 1, 12, 33.33),
        (0, 2, 4, 50),
    ],
)
def test_attendance_percentage_counts_justified_absences(
    present, justified, sessions, expected
):
    assert attendance_percentage(present, justified, sessions) == expected


@pytest.mark.parametrize(
    ("absences", "eligible", "remaining", "risk"),
    [
        (2, True, 1, "medio"),
        (3, False, 0, "alto"),
    ],
)
def test_exam_eligibility_uses_three_unjustified_absences(
    absences, eligible, remaining, risk
):
    result = exam_eligibility(absences)
    assert result == {
        "eligible": eligible,
        "absences_remaining": remaining,
        "risk": risk,
    }


def test_course_without_sessions_has_no_risk_or_misleading_percentage(
    app, sample_data, login_as
):
    with app.app_context():
        course = Course(
            name="Curso sin sesiones",
            code="EMPTY-1",
            teacher_id=sample_data["teacher_id"],
            schedule="Viernes, 14:00–16:00",
            location_type="virtual",
            classroom="Virtual",
        )
        db.session.add(course)
        db.session.flush()
        db.session.add(
            CourseEnrollment(
                course_id=course.id, student_id=sample_data["outsider_id"]
            )
        )
        db.session.commit()

        data = student_dashboard_data(sample_data["outsider_id"])
        assert data["total_sessions"] == 0
        assert data["overall_percentage"] == 0
        assert data["notices"] == []

    client = app.test_client()
    login_as(client, sample_data["outsider_id"])
    response = client.get("/alumno")
    assert response.status_code == 200
    assert "Sin sesiones" in response.text
    assert "100 por ciento de faltas" not in response.text
    assert "Riesgo de perder derecho" not in response.text


def test_metrics_calculate_percentage_and_risk_levels(app, sample_data):
    ids = sample_data
    with app.app_context():
        now = datetime.now(timezone.utc)
        sessions = [
            AttendanceSession(
                course_id=ids["course_id"],
                token_hash=f"{index:064x}",
                created_at=now - timedelta(minutes=index),
                expires_at=now - timedelta(minutes=index - 1),
                active=False,
                closed_at=now - timedelta(minutes=index - 1),
            )
            for index in range(2, 6)
        ]
        db.session.add_all(sessions)
        db.session.flush()
        db.session.add_all(
            [
                Attendance(
                    session_id=sessions[0].id,
                    student_id=ids["student_id"],
                    recorded_at=now,
                    status="presente",
                ),
            ]
        )
        db.session.commit()

        summary = admin_student_summaries()[0]
        assert summary["percentage"] == 40
        assert summary["risk"] == "alto"

        sessions[2].attendances.append(
            Attendance(
                student_id=ids["student_id"],
                recorded_at=now,
                status="presente",
            )
        )
        db.session.commit()
        summary = admin_student_summaries()[0]
        assert summary["percentage"] == 60
        assert summary["risk"] == "medio"

        sessions[3].attendances.append(
            Attendance(
                student_id=ids["student_id"],
                recorded_at=now,
                status="presente",
            )
        )
        db.session.commit()
        summary = admin_student_summaries()[0]
        assert summary["percentage"] == 80
        assert summary["risk"] == "ninguno"


def test_expo_service_validates_and_registers_without_http(app):
    with app.app_context():
        service = ExpoService()
        with pytest.raises(ValueError, match="nombre completo"):
            service.register("", "ana@example.com", "publico", "Visitante", "", "yes")

        assert service.register(
            "Ana Pérez", " ANA@example.com ", "publico", "Visitante", "Muy bien", "yes"
        )
        assert not service.register(
            "Ana Pérez", "ana@example.com", "publico", "Visitante", "Otra opinión", "yes"
        )


def test_attendance_service_records_once_without_http(app, sample_data):
    raw_token = secrets.token_urlsafe(32)
    with app.app_context():
        now = datetime.now(timezone.utc)
        attendance_session = AttendanceSession(
            course_id=sample_data["course_id"],
            token_hash=hashlib.sha256(raw_token.encode()).hexdigest(),
            created_at=now,
            expires_at=now + timedelta(minutes=1),
            active=True,
        )
        db.session.add(attendance_session)
        db.session.commit()
        student = db.session.get(User, sample_data["student_id"])
        service = AttendanceService()

        attendance = service.record_attendance(raw_token, student)

        assert attendance.student_id == student.id
        with pytest.raises(ValueError, match="ya quedó registrada"):
            service.record_attendance(raw_token, student)
