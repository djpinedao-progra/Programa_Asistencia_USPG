from app.controllers import main
from app.controllers.decorators import roles_required
from app.controllers._support import *
from app.controllers._support import _csv_safe, _preview_enrollment_rows


@main.route("/admin/cursos/importar", methods=["GET", "POST"])
@roles_required("admin")
def admin_import_course_enrollments():
    if request.method == "GET":
        return render_template("admin/admin_course_import.html")

    if request.form.get("action") in {"import", "download-errors"}:
        course_codes = request.form.getlist("course_code")
        carnets = request.form.getlist("carnet")
        if len(course_codes) != len(carnets):
            abort(400, description="Las filas del archivo no tienen el mismo formato.")
        rows = _preview_enrollment_rows(
            [
                (index + 2, code, carnet)
                for index, (code, carnet) in enumerate(zip(course_codes, carnets))
            ]
        )
        if request.form.get("action") == "download-errors":
            output = io.StringIO(newline="")
            writer = csv.writer(output)
            writer.writerow(["line", "course_code", "carnet", "error"])
            writer.writerows(
                [row["line"], _csv_safe(row["course_code"]), _csv_safe(row["carnet"]), row["status"]]
                for row in rows
                if not row["valid"] and row["status"] != "Ya está matriculado"
            )
            return Response(
                "\ufeff" + output.getvalue(),
                mimetype="text/csv",
                headers={
                    "Content-Disposition": "attachment; filename=matriculas-rechazadas.csv"
                },
            )
        enrollments = [
            (row["course_id"], row["student_id"])
            for row in rows if row["valid"]
        ]
        try:
            added = CourseService().bulk_enroll(
                enrollments, actor_id=current_user.id
            )
        except ValueError as error:
            flash(str(error), "error")
            return render_template(
                "admin/admin_course_import.html", rows=rows, preview=False, imported=0
            )
        for row in rows:
            if row["valid"]:
                row["status"] = "Matriculado"
        return render_template(
            "admin/admin_course_import.html", rows=rows, preview=False, imported=added
        )

    uploaded_file = request.files.get("file")
    if not uploaded_file or not uploaded_file.filename:
        flash("Selecciona un archivo CSV.", "error")
        return redirect(url_for("main.admin_import_course_enrollments"))
    content = uploaded_file.stream.read(2 * 1024 * 1024 + 1)
    if len(content) > 2 * 1024 * 1024:
        flash("El archivo supera el límite de 2 MB.", "error")
        return redirect(url_for("main.admin_import_course_enrollments"))
    try:
        reader = csv.DictReader(io.StringIO(content.decode("utf-8-sig")))
        headers = {
            (header or "").strip().casefold(): header
            for header in (reader.fieldnames or [])
        }
        course_header = next(
            (headers[key] for key in ("course_code", "codigo_curso", "curso") if key in headers),
            None,
        )
        carnet_header = headers.get("carnet")
        if not course_header or not carnet_header:
            raise ValueError("El CSV debe incluir las columnas course_code y carnet.")
        input_rows = [
            (line_number, row.get(course_header, ""), row.get(carnet_header, ""))
            for line_number, row in enumerate(reader, start=2)
        ]
    except (UnicodeDecodeError, csv.Error, ValueError) as error:
        flash(str(error) or "No se pudo leer el archivo CSV.", "error")
        return redirect(url_for("main.admin_import_course_enrollments"))
    rows = _preview_enrollment_rows(input_rows)
    return render_template(
        "admin/admin_course_import.html", rows=rows, preview=True, imported=0
    )


@main.get("/admin/cursos/importar/plantilla.csv")
@roles_required("admin")
def admin_course_import_template():
    output = io.StringIO(newline="")
    csv.writer(output).writerow(["course_code", "carnet"])
    return Response(
        "\ufeff" + output.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment; filename=plantilla-matriculas.csv"},
    )
