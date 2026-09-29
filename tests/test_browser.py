import threading
import re

import pytest
from werkzeug.serving import make_server

playwright_api = pytest.importorskip("playwright.sync_api")
from playwright.sync_api import Error as PlaywrightError, expect, sync_playwright

from app import db
from app.models import Course, CourseEnrollment, User


@pytest.fixture
def browser_page(app):
    server = make_server("127.0.0.1", 0, app, threaded=True)
    server_thread = threading.Thread(target=server.serve_forever, daemon=True)
    server_thread.start()
    playwright = sync_playwright().start()
    try:
        browser = playwright.chromium.launch()
    except PlaywrightError as error:
        playwright.stop()
        server.shutdown()
        server_thread.join()
        pytest.skip(f"Instala Chromium con `py -m playwright install chromium`: {error}")
    context = browser.new_context(viewport={"width": 1280, "height": 900})
    page = context.new_page()
    try:
        yield page, f"http://127.0.0.1:{server.server_port}"
    finally:
        context.close()
        browser.close()
        playwright.stop()
        server.shutdown()
        server_thread.join()


def create_user(name, email, role, carnet=None):
    user = User(name=name, email=email, role=role, carnet=carnet)
    user.set_password("password-seguro-123")
    db.session.add(user)
    db.session.commit()
    return user


def sign_in(page, base_url, identifier):
    page.goto(f"{base_url}/")
    page.get_by_label("Correo o carnet institucional").fill(identifier)
    page.get_by_label("Contraseña").fill("password-seguro-123")
    page.get_by_role("button", name="Entrar").click()
    expect(page.locator(".topbar .user-name")).to_be_visible()


def test_admin_imports_enrollments_in_browser(app, browser_page, tmp_path):
    page, base_url = browser_page
    with app.app_context():
        create_user("Admin", "admin@uspg.edu", "admin")
        teacher = create_user("Docente", "docente@uspg.edu", "docente")
        student = create_user("Alumna", "alumna@uspg.edu", "alumno", "2600403")
        course = Course(name="Programación", code="INF-101", teacher_id=teacher.id)
        db.session.add(course)
        db.session.commit()
        course_id, student_id = course.id, student.id

    sign_in(page, base_url, "admin@uspg.edu")
    page.goto(f"{base_url}/admin/cursos/importar")
    source_file = tmp_path / "matriculas.csv"
    source_file.write_text("course_code,carnet\nINF-101,2600403\nBAD-101,0000000\n", encoding="utf-8")
    page.locator("#enrollment-csv").set_input_files(str(source_file))
    page.get_by_role("button", name="Revisar archivo").click()
    expect(page.get_by_role("heading", name="Vista previa")).to_be_visible()
    expect(page.get_by_text("Curso no encontrado")).to_be_visible()
    with page.expect_download() as download_info:
        page.get_by_role("button", name="Descargar filas rechazadas").click()
    download = download_info.value
    assert download.suggested_filename == "matriculas-rechazadas.csv"

    page.get_by_role("button", name="Guardar matrículas válidas").click()
    expect(page.get_by_role("heading", name="Resultado de importación")).to_be_visible()
    expect(page.get_by_text("Se agregaron 1 matrículas nuevas.")).to_be_visible()
    with app.app_context():
        enrollment = db.session.query(CourseEnrollment).filter_by(
            course_id=course_id, student_id=student_id
        ).one_or_none()
        assert enrollment is not None


def test_teacher_starts_attendance_and_sees_live_sync_in_browser(app, browser_page):
    page, base_url = browser_page
    with app.app_context():
        teacher = create_user("Docente", "docente@uspg.edu", "docente")
        student = create_user("Alumna", "alumna@uspg.edu", "alumno", "2600403")
        course = Course(
            name="Historia", code="HIS-101", teacher_id=teacher.id,
            schedule="Lunes 08:00-09:30",
        )
        db.session.add(course)
        db.session.flush()
        db.session.add(CourseEnrollment(course_id=course.id, student_id=student.id))
        db.session.commit()
        course_id = course.id

    sign_in(page, base_url, "docente@uspg.edu")
    page.locator("#attendance-course").select_option(str(course_id))
    page.get_by_role("button", name="Iniciar asistencia").click()
    expect(page).to_have_url(re.compile(r"/docente/sesiones/\d+$"))
    status = page.locator("[data-connection-status]")
    expect(status).to_contain_text("Conectado", timeout=10000)
    row = page.locator(".live-student-row").first
    row.locator('select[name="status"]').select_option("presente")
    row.get_by_role("button", name="Guardar").click()
    expect(page.locator("[data-connection-status]")).to_be_visible()
    session_id = int(page.url.rsplit("/", 1)[-1])
    state = page.request.get(
        f"{base_url}/docente/sesiones/{session_id}/estado"
    ).json()
    expected_time = page.evaluate(
        """value => {
          const date = new Date(value);
          return `${date.toLocaleDateString("es-GT", { timeZone: "America/Guatemala" })} · ${date.toLocaleTimeString("es-GT", { timeZone: "America/Guatemala", hour: "2-digit", minute: "2-digit" })}`;
        }""",
        state["students"][0]["recorded_at"],
    )
    page.get_by_role("button", name="Actualizar lista").click()
    expect(page.locator(".live-student-row [data-student-time]")).to_contain_text(
        expected_time, timeout=5000
    )
    expect(page.get_by_text("Alumna")).to_be_visible()
