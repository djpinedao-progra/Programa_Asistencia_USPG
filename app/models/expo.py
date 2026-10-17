from datetime import datetime, timezone

from app.extensions import db


class ExpoAttendance(db.Model):
    __tablename__ = "expo_attendance"
    __table_args__ = (
        db.CheckConstraint(
            "category IN ('estudiante', 'catedratico', 'publico')",
            name="ck_expo_category",
        ),
    )

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(254), nullable=False, unique=True, index=True)
    category = db.Column(db.String(20), nullable=False, index=True)
    participation = db.Column(db.String(500), nullable=False)
    opinion = db.Column(db.Text, nullable=False, default="")
    recorded_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
