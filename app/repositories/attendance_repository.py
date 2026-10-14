from sqlalchemy import select

from app.extensions import db
from app.models import Attendance, AttendanceSession


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
        db.session.commit()
        return attendance

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
