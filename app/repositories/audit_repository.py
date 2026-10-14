from sqlalchemy import select

from app.extensions import db
from app.models import AuditLog


class AuditRepository:
    def list_recent(self, limit=None):
        query = select(AuditLog).order_by(AuditLog.created_at.desc())
        if limit is not None:
            query = query.limit(limit)
        return db.session.scalars(query).all()
