from sqlalchemy import select

from app.extensions import db
from app.models import Notice


class NoticeRepository:
    def list_for_courses(self, course_ids, limit=None):
        query = (
            select(Notice)
            .where(Notice.course_id.in_(course_ids))
            .order_by(Notice.created_at.desc())
        )
        if limit is not None:
            query = query.limit(limit)
        return db.session.scalars(query).all()
