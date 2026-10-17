from app.extensions import db


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
    modified_at = db.Column(db.DateTime(timezone=True))
    status = db.Column(db.String(20), nullable=False, default="presente")
    source = db.Column(db.String(20), nullable=False, default="qr")
    modified_by_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    session = db.relationship("AttendanceSession", backref="attendances")
    student = db.relationship("User", foreign_keys=[student_id], backref="attendances")
    modified_by = db.relationship("User", foreign_keys=[modified_by_id])
