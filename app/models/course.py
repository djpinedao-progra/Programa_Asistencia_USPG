from datetime import datetime, timezone

from app.extensions import db


class Course(db.Model):
    __tablename__ = "courses"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    code = db.Column(db.String(30), nullable=False, unique=True)
    teacher_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    schedule = db.Column(db.String(180), nullable=False, default="")
    location_type = db.Column(db.String(20), nullable=False, default="presencial")
    classroom = db.Column(db.String(100), nullable=False, default="")
    is_active = db.Column(db.Boolean, nullable=False, default=True)
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
        db.DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    course = db.relationship("Course", back_populates="enrollments")
    student = db.relationship("User", backref="course_enrollments")
