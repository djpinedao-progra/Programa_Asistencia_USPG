from app import db
from app.models import Course, CourseEnrollment
from app.routes import _csv_safe
from app.views.reports.pdf_builder import _percentage_label


def test_course_attendance_csv_and_pdf_exports(
    app, sample_data, login_as
):
    client = app.test_client()
    login_as(client, sample_data["admin_id"])

    csv_response = client.get(
        f"/api/cursos/{sample_data['course_id']}/asistencias.csv"
    )
    assert csv_response.status_code == 200
    assert csv_response.mimetype == "text/csv"
    assert "2600001" in csv_response.get_data(as_text=True)

    pdf_response = client.get(
        f"/api/cursos/{sample_data['course_id']}/asistencias.pdf"
    )
    assert pdf_response.status_code == 200
    assert pdf_response.mimetype == "application/pdf"
    assert pdf_response.data.startswith(b"%PDF")


def test_admin_report_exports_and_csv_formula_neutralization(
    app, sample_data, login_as
):
    client = app.test_client()
    login_as(client, sample_data["admin_id"])

    pdf_response = client.get("/admin/reportes.pdf")
    assert pdf_response.status_code == 200
    assert pdf_response.mimetype == "application/pdf"
    assert pdf_response.data.startswith(b"%PDF")

    assert _csv_safe("=SUM(A1:A2)") == "'=SUM(A1:A2)"
    assert _csv_safe("@cmd") == "'@cmd"


def test_course_export_access_checks(app, sample_data, login_as):
    client = app.test_client()
    login_as(client, sample_data["teacher_id"])

    response = client.get(
        f"/api/cursos/{sample_data['course_id']}/asistencias.csv"
    )
    assert response.status_code == 200


def test_report_percentage_label_distinguishes_courses_without_sessions():
    assert _percentage_label({"percentage": 0, "total_sessions": 0}) == "Sin sesiones"
    assert _percentage_label({"percentage": 50, "total_sessions": 4}) == "50%"


def test_admin_report_does_not_draw_zero_percent_for_no_sessions(
    app, sample_data, login_as
):
    with app.app_context():
        course = Course(
            name="Reporte sin sesiones",
            code="REPORT-EMPTY",
            teacher_id=sample_data["teacher_id"],
            schedule="Viernes, 16:00–18:00",
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
        course_id = course.id

    client = app.test_client()
    login_as(client, sample_data["admin_id"])
    response = client.get(f"/admin/reportes?curso={course_id}")

    assert response.status_code == 200
    assert "Sin sesiones" in response.text
    assert "width: 0%" not in response.text
