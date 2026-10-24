EXAM_ABSENCE_LIMIT = 3


def attendance_percentage(present, justified, computable_sessions):
    """Calcula asistencia válida; devuelve 0 cuando aún no hay sesiones."""
    if computable_sessions <= 0:
        return 0
    attended = max(0, present) + max(0, justified)
    return round(attended / computable_sessions * 100, 2)


def exam_eligibility(absences):
    absences = max(0, int(absences))
    remaining = max(0, EXAM_ABSENCE_LIMIT - absences)
    return {
        "eligible": absences < EXAM_ABSENCE_LIMIT,
        "absences_remaining": remaining,
        "risk": (
            "alto" if absences >= EXAM_ABSENCE_LIMIT
            else "medio" if absences == EXAM_ABSENCE_LIMIT - 1
            else "ninguno"
        ),
    }
