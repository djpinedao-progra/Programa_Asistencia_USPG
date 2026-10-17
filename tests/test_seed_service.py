from app.models import Course, CourseEnrollment, User
from app.services.seed_service import seed_demo_data


def test_demo_seed_is_idempotent(app):
    with app.app_context():
        seed_demo_data()
        seed_demo_data()

        assert User.query.count() == 3
        course = Course.query.filter_by(code="DEMO-101").one()
        assert course.teacher.email == "docente@catedratico.uspg.edu.gt"
        assert len(course.enrollments) == 1
        enrollment = CourseEnrollment.query.one()
        assert enrollment.student.email == "alumno@alumno.uspg.edu.gt"
