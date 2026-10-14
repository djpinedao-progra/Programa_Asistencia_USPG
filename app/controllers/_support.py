import base64
import csv
import hashlib
import io
import secrets
from datetime import datetime, timedelta, timezone
from urllib.parse import urljoin

from sqlalchemy import func, or_, select
from flask import (
    Blueprint,
    abort,
    current_app,
    flash,
    jsonify,
    redirect,
    Response,
    render_template,
    request,
    send_file,
    session,
    url_for,
)
from flask_login import current_user, login_required, login_user, logout_user
from app import db
from app.models import (
    Attendance,
    AttendanceSession,
    AuditLog,
    Course,
    CourseEnrollment,
    Notice,
    User,
)
from app.repositories import AttendanceRepository, CourseRepository, UserRepository
from app.security import csrf_token
from app.controllers.decorators import roles_required
from app.services.metrics_service import (
    admin_session_summaries,
    admin_student_summaries,
    course_roster,
    create_low_attendance_notices,
    preview_enrollment_rows,
    teacher_course_metrics,
)
from app.services import AttendanceService, AuditService, CourseService, UserService
from app.time_utils import local_date_utc_bounds, local_datetime, utc_isoformat


def _local_date_bounds_or_none(value):
    if not value:
        return None
    try:
        return local_date_utc_bounds(value, current_app.config["APP_TIMEZONE"])
    except ValueError:
        return None


def _admin_student_summaries(course_id=None, session_date=None):
    return admin_student_summaries(
        course_id, session_date, current_app.config["APP_TIMEZONE"]
    )


def _admin_session_summaries(
    course_id=None, teacher_id=None, session_date=None, page=None, page_size=25
):
    return admin_session_summaries(
        course_id, teacher_id, session_date, page, page_size,
        current_app.config["APP_TIMEZONE"],
    )


def _csv_safe(value):
    value = str(value or "")
    if value[:1] in {"=", "+", "-", "@", "\t", "\r"}:
        return "'" + value
    return value


def _preview_enrollment_rows(input_rows):
    return preview_enrollment_rows(input_rows)


def _teacher_course_metrics(course):
    return teacher_course_metrics(course)


def _course_roster(course_id):
    return course_roster(course_id)
