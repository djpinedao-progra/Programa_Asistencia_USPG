import json
import os
import pickle
from pathlib import Path

from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build


SCOPES = [
    "https://www.googleapis.com/auth/classroom.courses.readonly",
    "https://www.googleapis.com/auth/classroom.rosters.readonly",
]
BASE_DIR = Path(__file__).resolve().parents[1]
CLIENT_SECRET_FILE = BASE_DIR / "client_secret.json"
TOKEN_FILE = BASE_DIR / "google_token.pickle"


class GoogleClassroomService:
    def __init__(self, connection_factory):
        self.connection_factory = connection_factory

    @staticmethod
    def configured():
        return CLIENT_SECRET_FILE.exists()

    @staticmethod
    def redirect_uri(request):
        return f"{request.url_root.rstrip('/')}/oauth2callback"

    def authorization_url(self, request):
        self._require_configuration()
        flow = Flow.from_client_secrets_file(
            str(CLIENT_SECRET_FILE), scopes=SCOPES,
            redirect_uri=self.redirect_uri(request),
        )
        url, state = flow.authorization_url(
            access_type="offline", include_granted_scopes="true", prompt="consent"
        )
        return url, state

    def complete_authorization(self, request):
        self._require_configuration()
        flow = Flow.from_client_secrets_file(
            str(CLIENT_SECRET_FILE), scopes=SCOPES,
            state=request.args.get("state"),
            redirect_uri=self.redirect_uri(request),
        )
        flow.fetch_token(authorization_response=request.url)
        self._save_credentials(flow.credentials)

    def is_connected(self):
        return self._credentials() is not None

    def list_courses(self):
        service = self._classroom_api()
        result = service.courses().list(courseStates=["ACTIVE"]).execute()
        return [
            {"id": course["id"], "name": course.get("name", "Sin nombre"),
             "section": course.get("section", ""), "room": course.get("room", "")}
            for course in result.get("courses", [])
        ]

    def sync_students(self, course_id):
        service = self._classroom_api()
        students = service.courses().students().list(courseId=course_id).execute().get("students", [])
        imported = 0
        with self.connection_factory() as connection:
            for student in students:
                profile = student.get("profile", {})
                name = profile.get("name", {}).get("fullName", "Estudiante Classroom")
                email = profile.get("emailAddress") or f"{student['userId']}@classroom.local"
                existing = connection.execute(
                    "SELECT carnet FROM estudiantes WHERE correo = ?", (email,)
                ).fetchone()
                if existing:
                    connection.execute(
                        "UPDATE estudiantes SET nombre = ? WHERE correo = ?", (name, email)
                    )
                else:
                    connection.execute(
                        "INSERT INTO estudiantes (carnet, nombre, correo, carrera) VALUES (?, ?, ?, ?)",
                        (f"GC-{student['userId']}", name, email, "Google Classroom"),
                    )
                    imported += 1
        return {"found": len(students), "imported": imported}

    def _classroom_api(self):
        credentials = self._credentials()
        if credentials is None:
            raise ValueError("Conecta primero tu cuenta de Google Classroom")
        return build("classroom", "v1", credentials=credentials)

    def _credentials(self):
        if not TOKEN_FILE.exists():
            return None
        with TOKEN_FILE.open("rb") as token:
            credentials = pickle.load(token)
        if credentials.expired and credentials.refresh_token:
            credentials.refresh(Request())
            self._save_credentials(credentials)
        return credentials if credentials.valid else None

    @staticmethod
    def _save_credentials(credentials):
        with TOKEN_FILE.open("wb") as token:
            pickle.dump(credentials, token)

    @staticmethod
    def _require_configuration():
        if not CLIENT_SECRET_FILE.exists():
            raise ValueError(
                "Falta Asistencias_QR/client_secret.json. Créalo desde Google Cloud Console."
            )
