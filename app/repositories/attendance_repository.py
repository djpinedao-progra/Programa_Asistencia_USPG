from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.extensions import db
from app.models import Attendance, AttendanceSession, CourseEnrollment


class AttendanceRepository:
    def add_session(self, attendance_session):
        db.session.add(attendance_session)
        db.session.commit()
        return attendance_session

    def find_session_by_token_hash(self, token_hash):
        return db.session.scalar(
            select(AttendanceSession).where(
                AttendanceSession.token_hash == token_hash
            )
        )

    def find_session_by_id(self, session_id):
        return db.session.get(AttendanceSession, session_id)

    def record(self, attendance):
        db.session.add(attendance)
        try:
            db.session.commit()
        except IntegrityError:
            db.session.rollback()
            raise
        return attendance

    def is_student_enrolled(self, course_id, student_id):
        return db.session.scalar(
            select(CourseEnrollment.id).where(
                CourseEnrollment.course_id == course_id,
                CourseEnrollment.student_id == student_id,
            )
        ) is not None

    def list_for_student(self, student_id):
        return db.session.scalars(
            select(Attendance)
            .where(Attendance.student_id == student_id)
            .order_by(Attendance.recorded_at.desc())
        ).all()

    def list_for_course(self, course_id):
        return db.session.scalars(
            select(Attendance)
            .join(AttendanceSession)
            .where(AttendanceSession.course_id == course_id)
            .order_by(Attendance.recorded_at.desc())
        ).all()

    def list_all(self):
        return db.session.scalars(
            select(Attendance).order_by(Attendance.recorded_at.desc())
        ).all()
