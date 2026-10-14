from flask import flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required, login_user, logout_user

from app.controllers import main
from app.controllers.decorators import roles_required
from app.services import UserService


@main.route("/", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("main.dashboard"))
    if request.method == "POST":
        identifier = request.form.get("identifier", "").strip()
        password = request.form.get("password", "")
        user = UserService().find_by_login_identifier(identifier)
        from app.recovery import authenticate
        if user and UserService.email_role(user.email) == user.role and authenticate(user, password):
            login_user(user)
            next_url = request.args.get("next", "")
            if next_url.startswith("/") and not next_url.startswith("//"):
                return redirect(next_url)
            return redirect(url_for("main.dashboard"))
        flash("Correo o contraseña incorrectos.", "error")
    return render_template("auth/login.html")


@main.route("/registro", methods=["GET", "POST"])
def student_registration():
    if current_user.is_authenticated:
        return redirect(url_for("main.dashboard"))
    if request.method == "POST":
        try:
            UserService().register_student(
                request.form.get("name", ""),
                request.form.get("email", ""),
                request.form.get("carnet", ""),
                request.form.get("password", ""),
            )
            flash("Cuenta de estudiante creada. Inicia sesión para continuar.", "success")
            return redirect(url_for("main.login"))
        except ValueError as error:
            flash(str(error), "error")
    return render_template("auth/register.html")


@main.post("/salir")
@login_required
def logout():
    logout_user()
    flash("Sesión cerrada.", "success")
    return redirect(url_for("main.login"))


@main.get("/panel")
@login_required
def dashboard():
    if current_user.role == "admin":
        return redirect(url_for("main.admin_dashboard"))
    if current_user.role == "docente":
        return redirect(url_for("main.teacher_dashboard"))
    return redirect(url_for("main.student_dashboard"))


@main.route("/cuenta/seguridad", methods=["GET", "POST"])
@login_required
def account_security():
    if request.method == "POST":
        try:
            UserService().change_password(
                current_user.id,
                request.form.get("current_password", ""),
                request.form.get("new_password", ""),
                request.form.get("confirm_password", ""),
            )
            flash("Contraseña actualizada.", "success")
            return redirect(url_for("main.account_security"))
        except ValueError as error:
            flash(str(error), "error")
    return render_template("auth/account_security.html")


@main.route("/recuperar-contrasena", methods=["GET", "POST"])
def recover_password():
    if request.method == "POST":
        from app.recovery import request_replacement
        email = request.form.get("email", "").strip().lower()
        if not UserService.email_role(email):
            flash("Ingresa un correo universitario de alumno, catedrático o administrador.", "error")
        else:
            request_replacement(email)
            flash("Si el correo pertenece a una cuenta válida, recibirás una contraseña temporal. Revisa también correo no deseado.", "success")
            return redirect(url_for("main.login"))
    return render_template("auth/recover_password.html")
