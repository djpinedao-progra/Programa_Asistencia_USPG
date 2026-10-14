from sqlalchemy import func, select

from app.extensions import db
from app.models import ExpoAttendance


class ExpoRepository:
    def list_all(self):
        return db.session.scalars(
            select(ExpoAttendance).order_by(ExpoAttendance.recorded_at.desc())
        ).all()

    def count_by_category(self):
        return dict(
            db.session.execute(
                select(ExpoAttendance.category, func.count(ExpoAttendance.id))
                .group_by(ExpoAttendance.category)
            ).all()
        )
