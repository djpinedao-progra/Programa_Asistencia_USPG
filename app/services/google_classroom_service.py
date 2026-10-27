import base64
import hashlib
import json
import secrets
from datetime import UTC, datetime

from cryptography.fernet import Fernet, InvalidToken
from flask import current_app
from google.auth.exceptions import GoogleAuthError
from google.auth.transport.requests import Request as GoogleAuthRequest
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from oauthlib.oauth2 import OAuth2Error
from sqlalchemy import select

from app.extensions import db
from app.models import (
    GoogleClassroomCourseLink,
    GoogleIdentity,
    GoogleOAuthConnection,
    User,
)
from app.services.audit_service import AuditService
from app.services.course_service import CourseService
from app.services.user_service import UserService

CLASSROOM_SCOPES = (
    "https://www.googleapis.com/auth/classroom.courses.readonly",
    "https://www.googleapis.com/auth/classroom.rosters.readonly",
    "https://www.googleapis.com/auth/classroom.profile.emails",
)


class GoogleClassroomConfigurationError(ValueError):
    pass


class GoogleClassroomService:
    def __init__(self, admin_user_id, api=None):
        self.admin_user_id = admin_user_id
        self._api = api

    @staticmethod
    def enabled():
        return bool(current_app.config.get("GOOGLE_CLASSROOM_ENABLED"))

    @staticmethod
    def configuration_errors():
        required = {
            "GOOGLE_CLIENT_ID": current_app.config.get("GOOGLE_CLIENT_ID"),
            "GOOGLE_CLIENT_SECRET": current_app.config.get("GOOGLE_CLIENT_SECRET"),
            "GOOGLE_REDIRECT_URI": current_app.config.get("GOOGLE_REDIRECT_URI"),
            "GOOGLE_TOKEN_ENCRYPTION_KEY": current_app.config.get(
                "GOOGLE_TOKEN_ENCRYPTION_KEY"
            ),
        }
        return [name for name, value in required.items() if not value]

    @classmethod
    def require_available(cls):
        if not cls.enabled():
            raise GoogleClassroomConfigurationError(
                "La integraciÃ³n con Google Classroom estÃ¡ desactivada."
            )
        missing = cls.configuration_errors()
        if missing:
            raise GoogleClassroomConfigurationError(
                "Falta configurar: " + ", ".join(missing) + "."
            )

    @staticmethod
    def _client_config():
        return {
            "web": {
                "client_id": current_app.config["GOOGLE_CLIENT_ID"],
                "client_secret": current_app.config["GOOGLE_CLIENT_SECRET"],
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
                "redirect_uris": [current_app.config["GOOGLE_REDIRECT_URI"]],
            }
        }

    @staticmethod
    def _cipher():
        secret = current_app.config.get("GOOGLE_TOKEN_ENCRYPTION_KEY", "")
        if not secret:
            raise GoogleClassroomConfigurationError(
                "Falta configurar GOOGLE_TOKEN_ENCRYPTION_KEY."
            )
        key = base64.urlsafe_b64encode(hashlib.sha256(secret.encode()).digest())
        return Fernet(key)

    def authorization_url(self):
        self.require_available()
        flow = Flow.from_client_config(self._client_config(), scopes=CLASSROOM_SCOPES)
        flow.redirect_uri = current_app.config["GOOGLE_REDIRECT_URI"]
        authorization_url, state = flow.authorization_url(
            access_type="offline",
            include_granted_scopes="true",
            prompt="consent",
        )
        return authorization_url, state

    def save_authorization_code(self, code, state):
        self.require_available()
        flow = Flow.from_client_config(
            self._client_config(), scopes=CLASSROOM_SCOPES, state=state
        )
        flow.redirect_uri = current_app.config["GOOGLE_REDIRECT_URI"]
        try:
            flow.fetch_token(code=code)
            credentials = flow.credentials
            api = build(
                "classroom", "v1", credentials=credentials, cache_discovery=False
            )
            profile = api.userProfiles().get(userId="me").execute()
        except (GoogleAuthError, HttpError, OAuth2Error) as error:
            raise ValueError(
                "Google no pudo completar la autorizaciÃ³n. Intenta conectar de nuevo."
            ) from error
        self._save_credentials(credentials, profile.get("emailAddress", ""))
        return profile

    def _save_credentials(self, credentials, google_email=""):
        encrypted = self._cipher().encrypt(credentials.to_json().encode()).decode()
        connection = self.connection()
        if connection is None:
            connection = GoogleOAuthConnection(user_id=self.admin_user_id)
            db.session.add(connection)
        connection.google_email = google_email or connection.google_email
        connection.encrypted_credentials = encrypted
        connection.scopes = list(credentials.scopes or CLASSROOM_SCOPES)
        connection.updated_at = datetime.now(UTC)
        db.session.commit()
        return connection

    def connection(self):
        return db.session.scalar(
            select(GoogleOAuthConnection).where(
                GoogleOAuthConnection.user_id == self.admin_user_id
            )
        )

    def disconnect(self):
        connection = self.connection()
        if connection:
            db.session.delete(connection)
            db.session.commit()
            return True
        return False

    def _credentials(self):
        connection = self.connection()
        if not connection:
            raise ValueError("Conecta primero una cuenta de Google Classroom.")
        try:
            payload = self._cipher().decrypt(connection.encrypted_credentials.encode())
        except InvalidToken as error:
            raise ValueError(
                "No se pudieron descifrar las credenciales de Google. "
                "Vuelve a conectar la cuenta."
            ) from error
        credentials = Credentials.from_authorized_user_info(json.loads(payload))
        if credentials.expired and credentials.refresh_token:
            try:
                credentials.refresh(GoogleAuthRequest())
            except GoogleAuthError as error:
                raise ValueError(
                    "Google revocÃ³ o venciÃ³ la autorizaciÃ³n. Vuelve a conectar."
                ) from error
            self._save_credentials(credentials, connection.google_email)
        if not credentials.valid:
            raise ValueError("La autorizaciÃ³n de Google venciÃ³. Vuelve a conectar.")
        return credentials

    def api(self):
        if self._api is None:
            self.require_available()
            self._api = build(
                "classroom",
                "v1",
                credentials=self._credentials(),
                cache_discovery=False,
            )
        return self._api

    @staticmethod
    def _profile(resource):
        profile = resource.get("profile", {})
        name = profile.get("name", {})
        return {
            "google_user_id": resource.get("userId") or profile.get("id", ""),
            "name": name.get("fullName", "").strip(),
            "email": profile.get("emailAddress", "").strip().lower(),
        }

    def _paged(self, request_builder, result_key, **kwargs):
        rows = []
        page_token = None
        try:
            while True:
                request = request_builder(pageToken=page_token, **kwargs)
                response = request.execute()
                rows.extend(response.get(result_key, []))
                page_token = response.get("nextPageToken")
                if not page_token:
                    return rows
        except HttpError as error:
            status = getattr(error.resp, "status", None)
            if status in {401, 403}:
                raise ValueError(
                    "Google no autorizÃ³ la consulta. Verifica la cuenta y los permisos."
                ) from error
            raise ValueError(
                "Google Classroom no pudo completar la consulta."
            ) from error

    def list_courses(self):
        courses = self._paged(
            self.api().courses().list,
            "courses",
            courseStates=["ACTIVE"],
            pageSize=100,
        )
        linked_ids = set(
            db.session.scalars(select(GoogleClassroomCourseLink.classroom_course_id))
        )
        return [
            {
                "id": course.get("id", ""),
                "name": course.get("name", "Sin nombre"),
                "section": course.get("section", ""),
                "room": course.get("room", ""),
                "alternate_link": course.get("alternateLink", ""),
                "already_imported": course.get("id") in linked_ids,
            }
            for course in courses
        ]

    def course_preview(self, classroom_course_id):
        try:
            course = self.api().courses().get(id=classroom_course_id).execute()
            teachers = self._paged(
                self.api().courses().teachers().list,
                "teachers",
                courseId=classroom_course_id,
                pageSize=100,
            )
            students = self._paged(
                self.api().courses().students().list,
                "students",
                courseId=classroom_course_id,
                pageSize=100,
            )
        except HttpError as error:
            status = getattr(error.resp, "status", None)
            if status in {401, 403}:
                raise ValueError(
                    "La cuenta conectada no puede consultar ese curso."
                ) from error
            if status == 404:
                raise ValueError("Google Classroom no encontrÃ³ ese curso.") from error
            raise ValueError(
                "No se pudo consultar el curso en Google Classroom."
            ) from error
        normalized_teachers = [self._profile(item) for item in teachers]
        normalized_students = [self._profile(item) for item in students]
        return {
            "id": course.get("id", classroom_course_id),
            "name": course.get("name", "Sin nombre"),
            "section": course.get("section", ""),
            "room": course.get("room", ""),
            "owner_id": course.get("ownerId", ""),
            "alternate_link": course.get("alternateLink", ""),
            "teachers": normalized_teachers,
            "students": normalized_students,
            "teacher_count": len(normalized_teachers),
            "student_count": len(normalized_students),
        }

    @staticmethod
    def _upsert_identity(profile, role):
        google_user_id = profile.get("google_user_id", "").strip()
        email = profile.get("email", "").strip().lower()
        name = profile.get("name", "").strip()
        if not google_user_id or not email or not name:
            raise ValueError("Google no proporcionÃ³ nombre y correo completos.")
        identity = db.session.scalar(
            select(GoogleIdentity).where(
                GoogleIdentity.google_user_id == google_user_id
            )
        )
        if identity:
            if identity.user.role != role:
                raise ValueError(
                    f"{email} ya estÃ¡ vinculado con el rol {identity.user.role}."
                )
            identity.email = email
            identity.synced_at = datetime.now(UTC)
            return identity.user, False
        user = db.session.scalar(select(User).where(db.func.lower(User.email) == email))
        if user:
            if user.role != role:
                raise ValueError(f"{email} ya existe con el rol {user.role}.")
        else:
            UserService.validate_email_role(email, role)
            user = User(name=name, email=email, role=role)
            user.set_password(secrets.token_urlsafe(32))
            db.session.add(user)
            db.session.flush()
        db.session.add(
            GoogleIdentity(
                user_id=user.id,
                google_user_id=google_user_id,
                email=email,
            )
        )
        db.session.flush()
        return user, not bool(user.carnet) if role == "alumno" else False

    def import_course(
        self,
        classroom_course_id,
        code,
        schedule,
        location_type,
        classroom,
        actor_id,
    ):
        preview = self.course_preview(classroom_course_id)
        owner = next(
            (
                teacher
                for teacher in preview["teachers"]
                if teacher["google_user_id"] == preview["owner_id"]
            ),
            preview["teachers"][0] if preview["teachers"] else None,
        )
        if owner is None:
            raise ValueError("El curso no tiene un catedrÃ¡tico visible para importar.")
        issues = []
        created_without_carnet = 0
        try:
            teacher, _ = self._upsert_identity(owner, "docente")
            for extra_teacher in preview["teachers"]:
                if extra_teacher["google_user_id"] == owner["google_user_id"]:
                    continue
                try:
                    self._upsert_identity(extra_teacher, "docente")
                except ValueError as error:
                    issues.append(str(error))
            students = []
            for profile in preview["students"]:
                try:
                    student, missing_carnet = self._upsert_identity(profile, "alumno")
                    students.append(student)
                    created_without_carnet += int(missing_carnet)
                except ValueError as error:
                    issues.append(str(error))
            if not students:
                raise ValueError(
                    "No se pudo reconocer ningÃºn alumno con correo institucional vÃ¡lido."
                )
            link = db.session.scalar(
                select(GoogleClassroomCourseLink).where(
                    GoogleClassroomCourseLink.classroom_course_id == classroom_course_id
                )
            )
            course_service = CourseService()
            if link:
                course = course_service.update_course_roster(
                    link.course_id,
                    teacher.id,
                    schedule,
                    location_type,
                    classroom,
                    [str(student.id) for student in students],
                    True,
                    preview["name"],
                    code,
                    actor_id=actor_id,
                )
            else:
                course = course_service.create_course_for_admin(
                    preview["name"],
                    code,
                    teacher.id,
                    schedule,
                    location_type,
                    classroom,
                    [str(student.id) for student in students],
                    actor_id=actor_id,
                )
                link = GoogleClassroomCourseLink(
                    course_id=course.id,
                    classroom_course_id=classroom_course_id,
                )
                db.session.add(link)
            link.alternate_link = preview["alternate_link"]
            link.synced_at = datetime.now(UTC)
            AuditService.record(
                actor_id,
                "google_classroom_synced",
                "course",
                course.id,
                {
                    "classroom_course_id": classroom_course_id,
                    "students": len(students),
                    "issues": len(issues),
                },
            )
            db.session.commit()
        except Exception:
            db.session.rollback()
            raise
        return {
            "course": course,
            "students_imported": len(students),
            "teachers_found": preview["teacher_count"],
            "missing_carnet": created_without_carnet,
            "issues": issues,
        }


def suggested_course_code(course):
    section = "".join(
        character
        for character in course.get("section", "").upper()
        if character.isalnum()
    )[:10]
    suffix = course.get("id", "")[-6:]
    return f"GC-{section or suffix}"[:30]
