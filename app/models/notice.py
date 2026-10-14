from datetime import datetime, timezone

from app.extensions import db


class Notice(db.Model):
    __tablename__ = "notices"

    id = db.Column(db.Integer, primary_key=True)
    course_id = db.Column(db.Integer, db.ForeignKey("courses.id"), nullable=False)
    student_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    sender_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    message = db.Column(db.String(500), nullable=False)
    kind = db.Column(db.String(20), nullable=False, default="manual")
    created_at = db.Column(
        db.DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    course = db.relationship("Course", back_populates="notices")
    student = db.relationship("User", foreign_keys=[student_id])
    sender = db.relationship("User", foreign_keys=[sender_id])
