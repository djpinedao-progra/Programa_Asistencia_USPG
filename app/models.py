from datetime import datetime, timezone

from flask_login import UserMixin
from werkzeug.security import check_password_hash, generate_password_hash

from app import db


class User(UserMixin, db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(180), unique=True, nullable=False, index=True)
    carnet = db.Column(db.String(20), unique=True, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), nullable=False, index=True)
    created_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)


class Course(db.Model):
    __tablename__ = "courses"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    code = db.Column(db.String(30), nullable=False, unique=True)
    teacher_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    schedule = db.Column(db.String(180), nullable=False, default="")
    location_type = db.Column(db.String(20), nullable=False, default="presencial")
    classroom = db.Column(db.String(100), nullable=False, default="")
    teacher = db.relationship("User", backref="courses")
    enrollments = db.relationship(
        "CourseEnrollment", back_populates="course", cascade="all, delete-orphan"
    )
    notices = db.relationship("Notice", back_populates="course")


class CourseEnrollment(db.Model):
    __tablename__ = "course_enrollments"
    __table_args__ = (
        db.UniqueConstraint("course_id", "student_id", name="uq_course_student"),
    )

    id = db.Column(db.Integer, primary_key=True)
    course_id = db.Column(db.Integer, db.ForeignKey("courses.id"), nullable=False)
    student_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    enrolled_at = db.Column(
        db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )
    course = db.relationship("Course", back_populates="enrollments")
    student = db.relationship("User", backref="course_enrollments")


class AttendanceSession(db.Model):
    __tablename__ = "attendance_sessions"

    id = db.Column(db.Integer, primary_key=True)
    course_id = db.Column(db.Integer, db.ForeignKey("courses.id"), nullable=False)
    token_hash = db.Column(db.String(64), nullable=False, unique=True, index=True)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False)
    expires_at = db.Column(db.DateTime(timezone=True), nullable=False, index=True)
    active = db.Column(db.Boolean, nullable=False, default=True)
    closed_at = db.Column(db.DateTime(timezone=True))
    course = db.relationship("Course", backref="attendance_sessions")


class Attendance(db.Model):
    __tablename__ = "attendance"
    __table_args__ = (
        db.UniqueConstraint("session_id", "student_id", name="uq_session_student"),
    )

    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(
        db.Integer, db.ForeignKey("attendance_sessions.id"), nullable=False
    )
    student_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    recorded_at = db.Column(db.DateTime(timezone=True), nullable=False)
    status = db.Column(db.String(20), nullable=False, default="presente")
    source = db.Column(db.String(20), nullable=False, default="qr")
    modified_by_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    session = db.relationship("AttendanceSession", backref="attendances")
    student = db.relationship("User", foreign_keys=[student_id], backref="attendances")
    modified_by = db.relationship("User", foreign_keys=[modified_by_id])


class Notice(db.Model):
    __tablename__ = "notices"

    id = db.Column(db.Integer, primary_key=True)
    course_id = db.Column(db.Integer, db.ForeignKey("courses.id"), nullable=False)
    student_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    sender_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    message = db.Column(db.String(500), nullable=False)
    kind = db.Column(db.String(20), nullable=False, default="manual")
    created_at = db.Column(
        db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )
    course = db.relationship("Course", back_populates="notices")
    student = db.relationship("User", foreign_keys=[student_id])
    sender = db.relationship("User", foreign_keys=[sender_id])