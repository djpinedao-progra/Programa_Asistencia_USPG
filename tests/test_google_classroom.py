from datetime import UTC, datetime, timedelta
from unittest.mock import Mock

from google.oauth2.credentials import Credentials
from googleapiclient.errors import HttpError
from sqlalchemy import select

from app import db
from app.models import (
    Course,
    GoogleClassroomCourseLink,
    GoogleIdentity,
    GoogleOAuthConnection,
    User,
)
from app.services.course_service import build_schedule
from app.services.google_classroom_service import GoogleClassroomService

COURSE_DATA = {
    "id": "870466881464",
    "name": "Valores Progresistas",
    "section": "SecciÃ³n C, segundo semestre 2026E",
    "room": "",
    "ownerId": "teacher-1",
    "alternateLink": "https://classroom.google.com/c/ODcwNDY2ODgxNDY0",
}

TEACHERS = [
    {
        "userId": "teacher-1",
        "profile": {
            "id": "teacher-1",
            "name": {"fullName": "CatedrÃ¡tico Classroom"},
            "emailAddress": "classroom@catedratico.uspg.edu.gt",
        },
    },
    {
        "userId": "teacher-2",
        "profile": {
            "id": "teacher-2",
            "name": {"fullName": "Docente auxiliar"},
            "emailAddress": "auxiliar@catedratico.uspg.edu.gt",
        },
    },
]

STUDENTS = [
    {
        "userId": "student-1",
        "profile": {
            "id": "student-1",
            "name": {"fullName": "Estudiante Classroom"},
            "emailAddress": "classroom@alumno.uspg.edu.gt",
        },
    },
    {
        "userId": "student-2",
        "profile": {
            "id": "student-2",
            "name": {"fullName": "Estudiante sin dominio"},
            "emailAddress": "externo@gmail.com",
        },
    },
]


class FakeRequest:
    def __init__(self, payload):
        self.payload = payload

    def execute(self):
        return self.payload


class FakeRosterResource:
    def __init__(self, key, values):
        self.key = key
        self.values = values

    def list(self, **_kwargs):
        return FakeRequest({self.key: self.values})


class FakeCoursesResource:
    def list(self, **_kwargs):
        return FakeRequest({"courses": [COURSE_DATA]})

    def get(self, **_kwargs):
        return FakeRequest(COURSE_DATA)

    def teachers(self):
        return FakeRosterResource("teachers", TEACHERS)

    def students(self):
        return FakeRosterResource("students", STUDENTS)


class FakeClassroomApi:
    def courses(self):
        return FakeCoursesResource()


def _enable_google(app):
    app.config.update(
        GOOGLE_CLASSROOM_ENABLED=True,
        GOOGLE_CLIENT_ID="client-id",
        GOOGLE_CLIENT_SECRET="client-secret",
        GOOGLE_REDIRECT_URI="https://staging.example/admin/google/callback",
        GOOGLE_TOKEN_ENCRYPTION_KEY="test-encryption-secret",
    )


def test_google_classroom_is_hidden_and_routes_are_disabled_by_default(
    app, sample_data, login_as
):
    client = app.test_client()
    login_as(client, sample_data["admin_id"])

    dashboard = client.get("/admin")
    assert b"Google Classroom" not in dashboard.data
    assert client.get("/admin/google").status_code == 404


def test_google_classroom_page_reports_missing_environment_variables(
    app, sample_data, login_as
):
    app.config["GOOGLE_CLASSROOM_ENABLED"] = True
    client = app.test_client()
    login_as(client, sample_data["admin_id"])

    response = client.get("/admin/google")

    assert response.status_code == 200
    assert b"GOOGLE_CLIENT_ID" in response.data
    assert b"GOOGLE_TOKEN_ENCRYPTION_KEY" in response.data


def test_google_classroom_page_renders_spanish_text_as_utf8(app, sample_data, login_as):
    _enable_google(app)
    client = app.test_client()
    login_as(client, sample_data["admin_id"])

    response = client.get("/admin/google")

    assert response.status_code == 200
    assert "INTEGRACIÓN ACADÉMICA" in response.text
    assert "autorización" in response.text
    assert "Ã" not in response.text
    assert "Â" not in response.text


def test_google_classroom_credentials_are_encrypted_at_rest(app, sample_data):
    _enable_google(app)
    credentials = Credentials(
        token="access-token",
        refresh_token="refresh-token",
        token_uri="https://oauth2.googleapis.com/token",
        client_id="client-id",
        client_secret="client-secret",
        scopes=["scope-a"],
        expiry=datetime.now(UTC) + timedelta(hours=1),
    )
    with app.app_context():
        service = GoogleClassroomService(sample_data["admin_id"])
        connection = service._save_credentials(credentials, "admin@uspg.edu.gt")

        assert "access-token" not in connection.encrypted_credentials
        assert service._credentials().token == "access-token"


def test_google_profile_failure_does_not_block_oauth_connection(
    app, sample_data, monkeypatch
):
    _enable_google(app)
    credentials = Credentials(
        token="access-token",
        refresh_token="refresh-token",
        token_uri="https://oauth2.googleapis.com/token",
        client_id="client-id",
        client_secret="client-secret",
        scopes=["scope-a"],
        expiry=datetime.now(UTC) + timedelta(hours=1),
    )

    class FakeFlow:
        redirect_uri = ""

        def fetch_token(self, code):
            assert code == "authorization-code"

        @property
        def credentials(self):
            return credentials

    class ProfileRequest:
        def execute(self):
            response = Mock(status=403, reason="Forbidden")
            raise HttpError(response, b'{"error":{"message":"Forbidden"}}')

    class ProfilesResource:
        def get(self, userId):
            assert userId == "me"
            return ProfileRequest()

    class ProfileApi:
        def userProfiles(self):
            return ProfilesResource()

    monkeypatch.setattr(
        "app.services.google_classroom_service.Flow.from_client_config",
        lambda *_args, **_kwargs: FakeFlow(),
    )
    monkeypatch.setattr(
        "app.services.google_classroom_service.build",
        lambda *_args, **_kwargs: ProfileApi(),
    )

    with app.app_context():
        service = GoogleClassroomService(sample_data["admin_id"])
        profile = service.save_authorization_code(
            "authorization-code", "expected-state", "expected-verifier"
        )

        connection = db.session.scalar(select(GoogleOAuthConnection))
        assert profile == {}
        assert connection is not None
        assert connection.google_email == ""
        assert service._credentials().token == "access-token"


def test_google_oauth_preserves_pkce_verifier(app, sample_data, login_as, monkeypatch):
    _enable_google(app)

    class FakeFlow:
        redirect_uri = ""
        code_verifier = "pkce-verifier"

        def authorization_url(self, **kwargs):
            assert kwargs["access_type"] == "offline"
            return "https://accounts.google.com/o/oauth2/auth", "oauth-state"

    monkeypatch.setattr(
        "app.services.google_classroom_service.Flow.from_client_config",
        lambda *_args, **_kwargs: FakeFlow(),
    )
    client = app.test_client()
    login_as(client, sample_data["admin_id"])

    response = client.get("/admin/google/connect")

    assert response.status_code == 302
    with client.session_transaction() as user_session:
        assert user_session["google_oauth_state"] == "oauth-state"
        assert user_session["google_oauth_code_verifier"] == "pkce-verifier"


def test_imports_course_teacher_and_valid_students_without_duplicates(app, sample_data):
    _enable_google(app)
    with app.app_context():
        service = GoogleClassroomService(
            sample_data["admin_id"], api=FakeClassroomApi()
        )
        result = service.import_course(
            COURSE_DATA["id"],
            "VAL-2026-C",
            build_schedule(["Martes"], "10:00", "11:00"),
            "virtual",
            "",
            sample_data["admin_id"],
        )

        assert result["students_imported"] == 1
        assert result["teachers_found"] == 2
        assert result["missing_carnet"] == 1
        assert len(result["issues"]) == 1
        course = db.session.scalar(select(Course).where(Course.code == "VAL-2026-C"))
        assert course.name == "Valores Progresistas"
        assert course.classroom == "Virtual"
        assert len(course.enrollments) == 1
        assert course.teacher.email == "classroom@catedratico.uspg.edu.gt"
        assert (
            db.session.scalar(
                select(GoogleClassroomCourseLink).where(
                    GoogleClassroomCourseLink.course_id == course.id
                )
            ).classroom_course_id
            == COURSE_DATA["id"]
        )
        assert len(db.session.scalars(select(GoogleIdentity)).all()) == 3
        assert (
            db.session.scalar(select(User).where(User.email == "externo@gmail.com"))
            is None
        )

        repeated = service.import_course(
            COURSE_DATA["id"],
            "VAL-2026-C",
            build_schedule(["Martes"], "10:00", "11:00"),
            "virtual",
            "",
            sample_data["admin_id"],
        )
        assert repeated["students_imported"] == 1
        assert (
            len(
                db.session.scalars(
                    select(Course).where(Course.code == "VAL-2026-C")
                ).all()
            )
            == 1
        )
        assert len(db.session.scalars(select(GoogleIdentity)).all()) == 3


def test_import_accepts_manual_teacher_email_when_google_hides_it(app, sample_data):
    _enable_google(app)
    preview = {
        "id": "course-with-hidden-teacher-email",
        "name": "Curso con correo docente oculto",
        "section": "Sección A",
        "room": "",
        "owner_id": "teacher-hidden",
        "alternate_link": "https://classroom.google.com/",
        "teachers": [
            {
                "google_user_id": "teacher-hidden",
                "name": "Docente Visible",
                "email": "",
            }
        ],
        "students": [
            {
                "google_user_id": "student-visible",
                "name": "Alumno Visible",
                "email": "visible@alumno.uspg.edu.gt",
            }
        ],
        "teacher_count": 1,
        "student_count": 1,
    }
    with app.app_context():
        service = GoogleClassroomService(sample_data["admin_id"])
        service.course_preview = lambda _course_id: preview

        result = service.import_course(
            preview["id"],
            "HIDDEN-101",
            build_schedule(["Martes"], "10:00", "11:00"),
            "virtual",
            "",
            sample_data["admin_id"],
            teacher_email="visible@catedratico.uspg.edu.gt",
        )

        assert result["course"].teacher.email == "visible@catedratico.uspg.edu.gt"
        assert result["students_imported"] == 1


def test_admin_can_preview_google_course_with_mocked_api(
    app, sample_data, login_as, monkeypatch
):
    _enable_google(app)
    monkeypatch.setattr(
        GoogleClassroomService,
        "course_preview",
        lambda _self, _course_id: {
            "id": COURSE_DATA["id"],
            "name": COURSE_DATA["name"],
            "section": COURSE_DATA["section"],
            "room": "",
            "owner_id": COURSE_DATA["ownerId"],
            "alternate_link": COURSE_DATA["alternateLink"],
            "teachers": [GoogleClassroomService._profile(TEACHERS[0])],
            "students": [GoogleClassroomService._profile(STUDENTS[0])],
            "teacher_count": 1,
            "student_count": 1,
        },
    )
    client = app.test_client()
    login_as(client, sample_data["admin_id"])

    response = client.get(f"/admin/google/cursos/{COURSE_DATA['id']}")

    assert response.status_code == 200
    assert "Valores Progresistas" in response.text
    assert "Classroom no proporciona un horario semanal" in response.text
    assert 'name="teacher_email"' in response.text
    assert 'value="classroom@catedratico.uspg.edu.gt"' in response.text


def test_google_callback_rejects_invalid_state(app, sample_data, login_as):
    _enable_google(app)
    client = app.test_client()
    login_as(client, sample_data["admin_id"])
    with client.session_transaction() as user_session:
        user_session["google_oauth_state"] = "expected"
        user_session["google_oauth_code_verifier"] = "expected-verifier"

    response = client.get("/admin/google/callback?state=wrong&code=code")

    assert response.status_code == 400
    with app.app_context():
        assert db.session.scalar(select(GoogleOAuthConnection)) is None
