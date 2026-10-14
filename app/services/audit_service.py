from app.extensions import db
from app.models import AuditLog


class AuditService:
    @staticmethod
    def record(actor_id, action, entity_type, entity_id=None, details=None):
        db.session.add(
            AuditLog(
                actor_id=actor_id,
                action=action,
                entity_type=entity_type,
                entity_id=entity_id,
                details=details or {},
            )
        )
