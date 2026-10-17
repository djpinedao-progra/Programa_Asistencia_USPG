"""Reglas para matricular alumnos en cursos."""
import csv
import io

from sqlalchemy.exc import IntegrityError

from app.models import Attendance, CourseEnrollment
from app.repositories import (
    CourseEnrollmentRepository,
    CourseRepository,
    UserRepository,
)
from app.services.audit_service import AuditService


class CourseEnrollmentService:
    """Coordina matrículas y ausencias de sesiones ya cerradas."""

    def __init__(self, enrollments=None, users=None):
        self.enrollments = enrollments or CourseEnrollmentRepository()
        self.users = users or UserRepository()

    def students_from_ids(self, student_ids):
        """Valida una lista de identificadores y devuelve alumnos existentes."""
        students = []
        for raw_student_id in set(student_ids):
            try:
                student_id = int(raw_student_id)
            except (TypeError, ValueError) as error:
                raise ValueError("La lista de alumnos no es válida.") from error
            student = self.users.find_by_id(student_id)
            if not student or student.role != "alumno":
                raise ValueError("Solo puedes asignar cuentas de alumno a un curso.")
            students.append(student)
        return students

    def preview_csv(self, content):
        """Valida el formato CSV y prepara la vista previa de matrículas."""
        reader = csv.DictReader(io.StringIO(content.decode("utf-8-sig")))
        headers = {
            (header or "").strip().casefold(): header
            for header in (reader.fieldnames or [])
        }
        course_header = next(
            (
                headers[key]
                for key in ("course_code", "codigo_curso", "curso")
                if key in headers
            ),
            None,
        )
        carnet_header = headers.get("carnet")
        if not course_header or not carnet_header:
            raise ValueError(
                "El CSV debe incluir las columnas course_code y carnet."
            )
        input_rows = [
            (line_number, row.get(course_header, ""), row.get(carnet_header, ""))
            for line_number, row in enumerate(reader, start=2)
        ]
        return self.preview_rows(input_rows)

    def preview_rows(self, input_rows):
        """Valida cursos, alumnos y duplicados antes de importar matrículas."""
        courses = {
            course.code.casefold(): course
            for course in CourseRepository().list_all()
        }
        students = {
            student.carnet: student
            for student in self.users.list_students_with_carnet()
        }
        existing_enrollments = self.enrollments.list_all_pairs()
        seen = set()
        results = []
        for line_number, raw_code, raw_carnet in input_rows:
            code = (raw_code or "").strip().upper()
            carnet = (raw_carnet or "").strip()
            course = courses.get(code.casefold())
            student = students.get(carnet)
            valid = False
            if not code or not carnet:
                status = "Falta código de curso o carnet"
            elif not course:
                status = "Curso no encontrado"
            elif not course.is_active:
                status = "El curso está deshabilitado"
            elif not student:
                status = "Alumno no encontrado"
            elif (course.id, student.id) in seen:
                status = "Duplicado en el archivo"
            elif (course.id, student.id) in existing_enrollments:
                status = "Ya está matriculado"
            else:
                status = "Listo para matricular"
                valid = True
            if course and student:
                seen.add((course.id, student.id))
            results.append(
                {
                    "line": line_number,
                    "course_code": code,
                    "carnet": carnet,
                    "status": status,
                    "valid": valid,
                    "course_id": course.id if course else None,
                    "student_id": student.id if student else None,
                }
            )
        return results

    def bulk_enroll(self, enrollments, actor_id=None):
        """Agrega matrículas y registra faltas en sesiones cerradas."""
        new_pairs = set()
        for course_id, student_id in enrollments:
            course = self.enrollments.find_course(course_id)
            student = self.users.find_by_id(student_id)
            if not course or not student or student.role != "alumno":
                raise ValueError("Una de las matrículas seleccionadas ya no es válida.")
            new_pairs.add((course.id, student.id))

        existing_pairs = self.enrollments.list_existing_pairs(new_pairs)
        new_pairs -= existing_pairs
        if not new_pairs:
            return 0

        try:
            enrollment_records = [
                CourseEnrollment(course_id=course_id, student_id=student_id)
                for course_id, student_id in new_pairs
            ]
            self.enrollments.add_all(enrollment_records)
            for course_id, student_id in new_pairs:
                AuditService.record(
                    actor_id, "student_enrolled", "course_enrollment", None,
                    {"course_id": course_id, "student_id": student_id},
                )

            course_ids = {course_id for course_id, _ in new_pairs}
            closed_sessions = self.enrollments.list_closed_sessions(course_ids)
            sessions_by_course = {}
            for attendance_session in closed_sessions:
                sessions_by_course.setdefault(attendance_session.course_id, []).append(
                    attendance_session
                )
            existing_attendance = self.enrollments.list_attendance_pairs(course_ids)
            attendance_records = []
            for course_id, student_id in new_pairs:
                for attendance_session in sessions_by_course.get(course_id, []):
                    if (student_id, attendance_session.id) not in existing_attendance:
                        attendance_records.append(
                            Attendance(
                                session_id=attendance_session.id,
                                student_id=student_id,
                                recorded_at=attendance_session.closed_at,
                                status="ausente",
                                source="cierre",
                            )
                        )
            self.enrollments.add_all(attendance_records)
            self.enrollments.commit()
        except IntegrityError as error:
            self.enrollments.rollback()
            raise ValueError("No se pudieron guardar las matrículas.") from error
        return len(new_pairs)
