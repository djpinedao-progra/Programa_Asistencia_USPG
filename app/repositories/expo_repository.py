from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from app.extensions import db
from app.models import ExpoAttendance


class ExpoRepository:
    def find_by_email(self, email):
        return db.session.scalar(
            select(ExpoAttendance.id).where(
                func.lower(func.trim(ExpoAttendance.email)) == email
            )
        )

    def add(self, attendance):
        db.session.add(attendance)
        try:
            db.session.commit()
        except IntegrityError:
            db.session.rollback()
            raise
        return attendance

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
