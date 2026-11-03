from datetime import UTC, datetime

from app.extensions import db


# Guarda la conexión que un administrador autorizó con su cuenta de Google.
class GoogleOAuthConnection(db.Model):
    __tablename__ = "google_oauth_connections"

    id = db.Column(db.Integer, primary_key=True)
    # Cada usuario puede conectar una sola cuenta de Google.
    user_id = db.Column(
        db.Integer, db.ForeignKey("users.id"), nullable=False, unique=True
    )
    google_email = db.Column(db.String(180), nullable=False, default="")
    # Aquí se guarda el permiso de Google protegido, no la contraseña del usuario.
    encrypted_credentials = db.Column(db.Text, nullable=False)
    scopes = db.Column(db.JSON, nullable=False, default=list)
    # Estas fechas ayudan a saber cuándo se creó o actualizó la conexión.
    created_at = db.Column(
        db.DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )
    updated_at = db.Column(
        db.DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        nullable=False,
    )
    # Une esta conexión con el usuario administrador que la creó.
    user = db.relationship("User")


# Relaciona una persona de Google Classroom con un usuario de nuestra aplicación.
class GoogleIdentity(db.Model):
    __tablename__ = "google_identities"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(
        db.Integer, db.ForeignKey("users.id"), nullable=False, unique=True
    )
    # El identificador de Google permite reconocer a la misma persona al sincronizar.
    google_user_id = db.Column(db.String(100), nullable=False, unique=True)
    email = db.Column(db.String(180), nullable=False)
    synced_at = db.Column(
        db.DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )
    # Una persona de la aplicación tiene solamente una identidad de Google.
    user = db.relationship("User", backref=db.backref("google_identity", uselist=False))


# Guarda el enlace entre un curso importado y su curso original de Classroom.
class GoogleClassroomCourseLink(db.Model):
    __tablename__ = "google_classroom_course_links"

    id = db.Column(db.Integer, primary_key=True)
    # Los dos identificadores son únicos para evitar importar el mismo curso dos veces.
    course_id = db.Column(
        db.Integer, db.ForeignKey("courses.id"), nullable=False, unique=True
    )
    classroom_course_id = db.Column(db.String(100), nullable=False, unique=True)
    alternate_link = db.Column(db.String(500), nullable=False, default="")
    synced_at = db.Column(
        db.DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )
    # Permite llegar desde el curso de la aplicación a su enlace de Classroom.
    course = db.relationship(
        "Course", backref=db.backref("google_classroom_link", uselist=False)
    )
