from sqlalchemy import func, select

from app.extensions import db
from app.models import AuditLog


class AuditRepository:
    def add(self, entry):
        db.session.add(entry)
        return entry

    def count_all(self):
        return db.session.scalar(select(func.count(AuditLog.id))) or 0

    def list_page(self, page, page_size=50):
        return db.session.scalars(
            select(AuditLog)
            .order_by(AuditLog.created_at.desc(), AuditLog.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        ).all()

    def list_recent(self, limit=None):
        query = select(AuditLog).order_by(AuditLog.created_at.desc())
        if limit is not None:
            query = query.limit(limit)
        return db.session.scalars(query).all()
