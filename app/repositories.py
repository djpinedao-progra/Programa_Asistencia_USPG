from sqlalchemy import or_, select

from app import db
from app.models import Attendance, AttendanceSession, Course, User


class UserRepository:
    def find_by_email(self, email):
        return db.session.scalar(select(User).where(User.email == email.lower()))

    def find_by_login_identifier(self, identifier):
        normalized = identifier.strip().lower()
        return db.session.scalar(
            select(User).where(
                or_(User.email == normalized, User.carnet == identifier.strip())
            )
        )

    def find_by_carnet(self, carnet):
        return db.session.scalar(select(User).where(User.carnet == carnet))

    def find_by_id(self, user_id):
        return db.session.get(User, user_id)

    def list_all(self):
        return db.session.scalars(select(User).order_by(User.name)).all()

    def add(self, user):
        db.session.add(user)
        db.session.commit()
        return user

    def save(self, user):
        db.session.add(user)
        db.session.commit()
        return user


class CourseRepository:
    def list_for_teacher(self, teacher_id):
        return db.session.scalars(
            select(Course).where(Course.teacher_id == teacher_id).order_by(Course.name)
        ).all()

    def list_all(self):
        return db.session.scalars(select(Course).order_by(Course.name)).all()

    def get_for_teacher(self, course_id, teacher_id):
        return db.session.scalar(
            select(Course).where(
                Course.id == course_id, Course.teacher_id == teacher_id
            )
        )

    def add(self, course):
        db.session.add(course)
        db.session.commit()
        return course


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