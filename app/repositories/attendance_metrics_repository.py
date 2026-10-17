from datetime import datetime, timezone

from sqlalchemy import and_, case, func, or_, select

from app.extensions import db
from app.models import Attendance, AttendanceSession, Course, CourseEnrollment, User


class AttendanceMetricsRepository:
    def list_teacher_history(
        self,
        course_ids,
        selected_course_id,
        date_bounds,
        invalid_date,
        student_search,
        status,
        page,
        page_size=25,
    ):
        query = select(Attendance).join(AttendanceSession).join(Course)
        if course_ids:
            query = query.where(AttendanceSession.course_id.in_(course_ids))
        if selected_course_id is not None:
            if selected_course_id == -1:
                query = query.where(AttendanceSession.course_id.not_in(course_ids or []))
            else:
                query = query.where(AttendanceSession.course_id == selected_course_id)
        if date_bounds and not invalid_date:
            start, end = date_bounds
            query = query.where(
                Attendance.recorded_at >= start,
                Attendance.recorded_at < end,
            )
        elif invalid_date:
            query = query.where(False)
        if student_search:
            query = query.join(User, Attendance.student_id == User.id).where(
                or_(
                    User.name.ilike(f"%{student_search}%"),
                    User.carnet.ilike(f"%{student_search}%"),
                )
            )
        if status:
            query = query.where(Attendance.status == status)
        query = query.order_by(Attendance.recorded_at.desc())
        total = db.session.execute(select(func.count()).select_from(query.subquery())).scalar_one()
        pages = max(1, (total + page_size - 1) // page_size)
        page = min(max(1, page), pages)
        rows = db.session.scalars(
            query.offset((page - 1) * page_size).limit(page_size)
        ).all()
        return total, pages, page, rows

    def list_admin_session_page(
        self,
        course_id=None,
        teacher_id=None,
        date_bounds=None,
        invalid_date=False,
        page=None,
        page_size=25,
    ):
        query = select(AttendanceSession).join(Course)
        if course_id is not None:
            query = query.where(AttendanceSession.course_id == course_id)
        if teacher_id is not None:
            query = query.where(Course.teacher_id == teacher_id)
        if date_bounds and not invalid_date:
            start, end = date_bounds
            query = query.where(
                AttendanceSession.created_at >= start,
                AttendanceSession.created_at < end,
            )
        query = query.order_by(AttendanceSession.created_at.desc())
        if page is None:
            return db.session.scalars(query).all(), 0
        total = db.session.execute(select(func.count()).select_from(query.subquery())).scalar_one()
        rows = db.session.scalars(query.offset((page - 1) * page_size).limit(page_size)).all()
        return rows, total

    def list_student_course_links(self):
        enrollments = db.session.execute(
            select(CourseEnrollment.student_id, CourseEnrollment.course_id)
        ).all()
        sessions = db.session.execute(
            select(Attendance.student_id, AttendanceSession.course_id)
            .join(AttendanceSession, Attendance.session_id == AttendanceSession.id)
            .distinct()
        ).all()
        return enrollments, sessions

    def list_closed_sessions_for_courses(self, course_ids, date_bounds=None, invalid_date=False):
        if not course_ids:
            return []
        query = select(AttendanceSession).where(
            AttendanceSession.course_id.in_(course_ids),
            AttendanceSession.closed_at.is_not(None),
        )
        if date_bounds and not invalid_date:
            start, end = date_bounds
            query = query.where(
                AttendanceSession.closed_at >= start,
                AttendanceSession.closed_at < end,
            )
        query = query.order_by(AttendanceSession.created_at.desc())
        return db.session.scalars(query).all()

    def list_status_counts_for_sessions(self, session_ids):
        if not session_ids:
            return []
        return db.session.execute(
            select(
                Attendance.student_id,
                AttendanceSession.course_id,
                Attendance.status,
                func.count(Attendance.id),
            )
            .join(AttendanceSession, Attendance.session_id == AttendanceSession.id)
            .where(Attendance.session_id.in_(session_ids))
            .group_by(Attendance.student_id, AttendanceSession.course_id, Attendance.status)
        ).all()

    def list_closed_sessions_for_course(self, course_id):
        return db.session.scalars(
            select(AttendanceSession)
            .where(
                AttendanceSession.course_id == course_id,
                AttendanceSession.closed_at.is_not(None),
            )
            .order_by(AttendanceSession.created_at.desc())
        ).all()

    def list_historical_student_ids_for_course(self, course_id):
        rows = db.session.execute(
            select(Attendance.student_id)
            .join(AttendanceSession, Attendance.session_id == AttendanceSession.id)
            .where(AttendanceSession.course_id == course_id)
            .distinct()
        ).scalars().all()
        return rows

    def list_status_counts_for_course(self, course_id):
        return db.session.execute(
            select(Attendance.student_id, Attendance.status, func.count(Attendance.id))
            .join(AttendanceSession, Attendance.session_id == AttendanceSession.id)
            .where(AttendanceSession.course_id == course_id)
            .group_by(Attendance.student_id, Attendance.status)
        ).all()

    def read_database(self):
        from app.extensions import db as database
        tables = {}
        for table in db.metadata.sorted_tables:
            rows = db.session.execute(select(table)).all()
            tables[table.name] = {
                "columns": [column.name for column in table.columns],
                "rows": [dict(zip((c.name for c in table.columns), row)) for row in rows],
            }
        return database.engine.dialect.name, tables

    def table_columns(self):
        return {
            table.name: [column.name for column in table.columns]
            for table in db.metadata.sorted_tables
        }

    def replace_database(self, archived_tables):
        for table in db.metadata.sorted_tables:
            db.session.execute(table.delete())
            rows = archived_tables.get(table.name, {}).get("rows", [])
            if rows:
                db.session.execute(table.insert(), rows)
        db.session.commit()
