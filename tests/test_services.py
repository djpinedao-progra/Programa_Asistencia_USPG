from datetime import datetime, timedelta, timezone

import pytest

from app import db
from app.models import Attendance, AttendanceSession
from app.services.expo_service import ExpoService
from app.services.metrics_service import admin_student_summaries


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
