from app.models import Notice
from app.repositories import NoticeRepository


class NoticeService:
    def __init__(self, notices=None):
        self.notices = notices or NoticeRepository()

    def list_for_courses(self, course_ids, limit=None):
        if not course_ids:
            return []
        return self.notices.list_for_courses(course_ids, limit=limit)

    def create_manual_notice(self, course, student_id, actor_id, message):
        if not course:
            return None
        notice = Notice(
            course_id=course.id,
            student_id=student_id if student_id else None,
            sender_id=actor_id,
            message=message,
            kind="manual",
        )
        self.notices.add(notice)
        return notice
