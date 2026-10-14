from sqlalchemy import select

from app.extensions import db
from app.models import Course


class CourseRepository:
    def list_for_teacher(self, teacher_id):
        return db.session.scalars(
            select(Course)
            .where(Course.teacher_id == teacher_id, Course.is_active.is_(True))
            .order_by(Course.name)
        ).all()

    def list_all(self):
        return db.session.scalars(select(Course).order_by(Course.name)).all()

    def get_by_id(self, course_id):
        return db.session.get(Course, course_id)

    def find_by_code(self, code):
        return db.session.scalar(select(Course).where(Course.code == code))

    def get_for_teacher(self, course_id, teacher_id):
        return db.session.scalar(
            select(Course).where(
                Course.id == course_id,
                Course.teacher_id == teacher_id,
                Course.is_active.is_(True),
            )
        )

    def add(self, course):
        db.session.add(course)
        db.session.commit()
        return course
