from sqlalchemy import or_, select

from app.extensions import db
from app.models import Notice


class NoticeRepository:
    def add(self, notice):
        db.session.add(notice)
        db.session.commit()
        return notice

    def list_for_courses(self, course_ids, limit=None):
        query = (
            select(Notice)
            .where(Notice.course_id.in_(course_ids))
            .order_by(Notice.created_at.desc())
        )
        if limit is not None:
            query = query.limit(limit)
        return db.session.scalars(query).all()

    def list_for_student_courses(self, course_ids, student_id, limit=20):
        if not course_ids:
            return []
        query = (
            select(Notice)
            .where(
                Notice.course_id.in_(course_ids),
                or_(Notice.student_id == student_id, Notice.student_id.is_(None)),
            )
            .order_by(Notice.created_at.desc())
            .limit(limit)
        )
        return db.session.scalars(query).all()

    def list_automatic_student_ids(self, course_id):
        return db.session.scalars(
            select(Notice.student_id).where(
                Notice.course_id == course_id, Notice.kind == "automatic"
            )
        ).all()

    def add_all(self, notices):
        db.session.add_all(notices)
        db.session.commit()
