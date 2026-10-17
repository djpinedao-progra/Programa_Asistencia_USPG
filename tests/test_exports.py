from app.routes import _csv_safe


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
