from sqlalchemy import select, tuple_

from app.extensions import db
from app.models import Attendance, AttendanceSession, Course, CourseEnrollment


class CourseEnrollmentRepository:
    def list_all(self):
        return db.session.scalars(select(CourseEnrollment).order_by(CourseEnrollment.id)).all()

    def list_all_pairs(self):
        return {
            (enrollment.course_id, enrollment.student_id)
            for enrollment in self.list_all()
        }

    def list_for_course(self, course_id):
        return db.session.scalars(
            select(CourseEnrollment)
            .where(CourseEnrollment.course_id == course_id)
            .order_by(CourseEnrollment.enrolled_at.desc())
        ).all()

    def list_students_for_course(self, course_id):
        rows = self.list_for_course(course_id)
        return [row.student for row in rows if row.student]

    def list_course_ids_for_student(self, student_id):
        return db.session.scalars(
            select(CourseEnrollment.course_id).where(
                CourseEnrollment.student_id == student_id
            )
        ).all()

    def list_courses(self, course_ids):
        if not course_ids:
            return []
        return db.session.scalars(
            select(Course)
            .where(Course.id.in_(course_ids))
            .order_by(Course.name)
        ).all()

    def find_course(self, course_id):
        return db.session.get(Course, course_id)

    def list_existing_pairs(self, pairs):
        if not pairs:
            return set()
        return {
            (row.course_id, row.student_id)
            for row in db.session.scalars(
                select(CourseEnrollment).where(
                    tuple_(
                        CourseEnrollment.course_id,
                        CourseEnrollment.student_id,
                    ).in_(list(pairs))
                )
            ).all()
        }

    def add_all(self, records):
        db.session.add_all(records)

    def add(self, record):
        db.session.add(record)
        return record

    def commit(self):
        db.session.commit()

    def rollback(self):
        db.session.rollback()

    def list_closed_sessions(self, course_ids):
        if not course_ids:
            return []
        return db.session.scalars(
            select(AttendanceSession)
            .where(
                AttendanceSession.course_id.in_(course_ids),
                AttendanceSession.closed_at.is_not(None),
            )
            .order_by(AttendanceSession.closed_at.desc())
        ).all()

    def list_attendance_pairs(self, course_ids):
        if not course_ids:
            return set()
        return {
            (attendance.student_id, attendance.session_id)
            for attendance in db.session.scalars(
                select(Attendance)
                .join(AttendanceSession)
                .where(AttendanceSession.course_id.in_(course_ids))
            ).all()
        }
