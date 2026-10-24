def attendance_percentage(present, justified, computable_sessions):
    """Calcula asistencia válida; devuelve 0 cuando aún no hay sesiones."""
    if computable_sessions <= 0:
        return 0
    attended = max(0, present) + max(0, justified)
    return round(attended / computable_sessions * 100, 2)
