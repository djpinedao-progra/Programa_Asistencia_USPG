from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from app.extensions import db
from app.models import AppSetting, ExpoAttendance


class ExpoRepository:
    def get_setting(self, key):
        return db.session.get(AppSetting, key)

    def set_setting(self, key, value):
        setting = self.get_setting(key)
        if setting:
            setting.value = value
        else:
            db.session.add(AppSetting(key=key, value=value))

    def commit(self):
        db.session.commit()

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

    def list_filtered(self, category=None):
        query = select(ExpoAttendance).order_by(
            ExpoAttendance.recorded_at.desc(), ExpoAttendance.id.desc()
        )
        if category:
            query = query.where(ExpoAttendance.category == category)
        return db.session.scalars(query).all()

    def paginate(self, category=None, per_page=25):
        query = select(ExpoAttendance).order_by(
            ExpoAttendance.recorded_at.desc(), ExpoAttendance.id.desc()
        )
        if category:
            query = query.where(ExpoAttendance.category == category)
        return db.paginate(
            query, per_page=per_page, max_per_page=per_page
        )

    def count_by_category(self):
        return dict(
            db.session.execute(
                select(ExpoAttendance.category, func.count(ExpoAttendance.id))
                .group_by(ExpoAttendance.category)
            ).all()
        )
