from app.models import AuditLog
from app.repositories import AuditRepository


class AuditService:
    def __init__(self, repository=None):
        self.repository = repository or AuditRepository()

    @staticmethod
    def record(actor_id, action, entity_type, entity_id=None, details=None):
        AuditRepository().add(
            AuditLog(
                actor_id=actor_id,
                action=action,
                entity_type=entity_type,
                entity_id=entity_id,
                details=details or {},
            )
        )

    def count_all(self):
        return self.repository.count_all()

    def list_page(self, page, page_size=50):
        return self.repository.list_page(page, page_size)
