from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.extensions import db
from app.models import (
    Attendance,
    AttendanceSession,
    CourseEnrollment,
)


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

    def find_open_session_for_course(self, course_id):
        return db.session.scalar(
            select(AttendanceSession)
            .where(
                AttendanceSession.course_id == course_id,
                AttendanceSession.active.is_(True),
                AttendanceSession.closed_at.is_(None),
            )
            .order_by(AttendanceSession.created_at.desc())
        )

    def list_student_ids_for_session(self, session_id):
        return db.session.scalars(
            select(Attendance.student_id).where(
                Attendance.session_id == session_id
            )
        ).all()

    def list_sessions_for_course(self, course_id, open_only=False):
        query = select(AttendanceSession).where(
            AttendanceSession.course_id == course_id
        )
        if open_only:
            query = query.where(AttendanceSession.closed_at.is_(None))
        return db.session.scalars(query).all()

    def list_sessions_for_courses(self, course_ids):
        if not course_ids:
            return []
        return db.session.scalars(
            select(AttendanceSession)
            .where(AttendanceSession.course_id.in_(course_ids))
            .order_by(AttendanceSession.created_at.desc())
        ).all()

    def list_attendance_pairs_for_course(self, course_id):
        return set(
            db.session.execute(
                select(Attendance.student_id, Attendance.session_id)
                .join(AttendanceSession)
                .where(AttendanceSession.course_id == course_id)
            ).all()
        )

    def add_many(self, attendances):
        db.session.add_all(attendances)

    def list_for_session(self, session_id):
        return db.session.scalars(
            select(Attendance).where(Attendance.session_id == session_id)
        ).all()

    def find_attendance_by_id(self, attendance_id):
        return db.session.get(Attendance, attendance_id)

    def find_for_session_and_student(self, session_id, student_id):
        return db.session.scalar(
            select(Attendance).where(
                Attendance.session_id == session_id,
                Attendance.student_id == student_id,
            )
        )

    def stage_attendance(self, attendance):
        db.session.add(attendance)
        db.session.flush()
        return attendance

    def commit_changes(self):
        db.session.commit()

    def save_session(self, attendance_session):
        db.session.add(attendance_session)
        db.session.commit()
        return attendance_session

    def save_session_with_attendances(self, attendance_session, attendances):
        db.session.add_all(attendances)
        db.session.add(attendance_session)
        db.session.commit()

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

    def list_for_course_without_order(self, course_id):
        return db.session.scalars(
            select(Attendance)
            .join(AttendanceSession)
            .where(AttendanceSession.course_id == course_id)
        ).all()

    def list_all(self):
        return db.session.scalars(
            select(Attendance).order_by(Attendance.recorded_at.desc())
        ).all()
