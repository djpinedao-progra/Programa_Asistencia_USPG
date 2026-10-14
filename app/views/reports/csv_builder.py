"""Generación de archivos CSV a partir de filas ya preparadas."""


def csv_safe(value):
    """Neutraliza valores que podrían interpretarse como fórmulas en una hoja de cálculo."""
    value = str(value or "")
    if value[:1] in {"=", "+", "-", "@", "\t", "\r"}:
        return "'" + value
    return value


def build_attendance_csv(rows):
    """Devuelve el CSV de asistencia con las filas proporcionadas."""
    lines = ["alumno,carnet,correo,curso,codigo,docente,fecha_hora"]
    for row in rows:
        lines.append(
            ",".join(
                '"' + str(value).replace('"', '""') + '"' for value in row
            )
        )
    return ("\ufeff" + "\n".join(lines)).encode("utf-8")
