from datetime import UTC, datetime

from app.extensions import db


class GoogleOAuthConnection(db.Model):
    __tablename__ = "google_oauth_connections"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(
        db.Integer, db.ForeignKey("users.id"), nullable=False, unique=True
    )
    google_email = db.Column(db.String(180), nullable=False, default="")
    encrypted_credentials = db.Column(db.Text, nullable=False)
    scopes = db.Column(db.JSON, nullable=False, default=list)
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
    user = db.relationship("User")


class GoogleIdentity(db.Model):
    __tablename__ = "google_identities"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(
        db.Integer, db.ForeignKey("users.id"), nullable=False, unique=True
    )
    google_user_id = db.Column(db.String(100), nullable=False, unique=True)
    email = db.Column(db.String(180), nullable=False)
    synced_at = db.Column(
        db.DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )
    user = db.relationship("User", backref=db.backref("google_identity", uselist=False))


class GoogleClassroomCourseLink(db.Model):
    __tablename__ = "google_classroom_course_links"

    id = db.Column(db.Integer, primary_key=True)
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
    course = db.relationship(
        "Course", backref=db.backref("google_classroom_link", uselist=False)
    )
